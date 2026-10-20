"""
Reaction processor for ChemVision AI.

Full pipeline:
  1. Save the uploaded image.
  2. Custom ML classifier (EfficientNet-B0) → optional suggestion metadata.
  3. OpenCV multi-strategy preprocessing → EasyOCR extraction.
  4. OCR text normalisation (subscripts, arrows, OCR errors).
  5. Equation parsing – split on arrow, parse tokens (coefficient + formula).
  6. Match against COMMON_REACTIONS registry using exact species and
     stoichiometry when an equation was parsed. Filename/text aliases remain
     unverified clues; the classifier cannot decide reaction identity.
  7. Build visualization data via molecule_service.
  8. Return result dict compatible with the Reaction model.
"""

from __future__ import annotations

import logging
import re
import threading
from collections import Counter
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status

from app.core.config import get_settings
from app.services.common_reactions import COMMON_REACTIONS
from app.services.molecule_service import build_visualization_data

logger = logging.getLogger(__name__)

ALLOWED_CONTENT_TYPES = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}


# ─────────────────────────────────────────────────────────────────────────────
# EasyOCR singleton  (initialise once per process, reuse)
# ─────────────────────────────────────────────────────────────────────────────

_ocr_reader = None
_ocr_lock   = threading.Lock()


def _get_ocr_reader():
    global _ocr_reader
    if _ocr_reader is not None:
        return _ocr_reader
    with _ocr_lock:
        if _ocr_reader is not None:        # double-checked
            return _ocr_reader
        try:
            import easyocr                  # type: ignore
            logger.info("Initialising EasyOCR reader (first use) …")
            _ocr_reader = easyocr.Reader(
                ["en"], gpu=False, verbose=False,
                # Disable the download banner / progress bar in production
                download_enabled=True,
            )
            logger.info("EasyOCR reader ready.")
        except Exception as exc:
            logger.warning("EasyOCR unavailable: %s", exc)
            _ocr_reader = None
        return _ocr_reader


# ─────────────────────────────────────────────────────────────────────────────
# File I/O
# ─────────────────────────────────────────────────────────────────────────────

def save_upload(file: UploadFile) -> tuple[Path, str]:
    settings = get_settings()
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload a PNG, JPG, or WEBP image.",
        )

    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    extension = ALLOWED_CONTENT_TYPES[file.content_type]
    safe_name = f"{uuid4().hex}{extension}"
    destination = settings.upload_dir / safe_name
    max_bytes = settings.max_upload_mb * 1024 * 1024

    size = 0
    with destination.open("wb") as buffer:
        while chunk := file.file.read(1024 * 1024):
            size += len(chunk)
            if size > max_bytes:
                destination.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"Image too large. Maximum is {settings.max_upload_mb} MB.",
                )
            buffer.write(chunk)

    file.file.seek(0)
    # Content-Type is supplied by the client and is not proof that the bytes
    # are an image. Verify the actual image before retaining it or passing it
    # into OpenCV / EasyOCR.
    try:
        from PIL import Image, UnidentifiedImageError

        with Image.open(destination) as image:
            image.verify()
    except (ImportError, UnidentifiedImageError, OSError, ValueError) as exc:
        destination.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is not a valid PNG, JPG, or WEBP image.",
        ) from exc
    return destination, safe_name


# ─────────────────────────────────────────────────────────────────────────────
# Image preprocessing — produce multiple candidate images for OCR
# ─────────────────────────────────────────────────────────────────────────────

def _preprocess_images(path: Path) -> list:
    """
    Return a list of numpy image arrays to try OCR on.
    Falls back to empty list if OpenCV is unavailable.
    """
    try:
        import cv2                          # type: ignore
        import numpy as np                  # type: ignore
    except ImportError:
        return []

    bgr = cv2.imread(str(path))
    if bgr is None:
        return []

    results = []

    # 1. Original colour image
    results.append(bgr)

    # 2. Grayscale
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    results.append(gray)

    # 3. Otsu threshold (good for printed text on white background)
    _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    results.append(otsu)

    # 4. Inverted Otsu (handles white text on dark background)
    results.append(cv2.bitwise_not(otsu))

    # 5. CLAHE contrast enhancement
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    results.append(enhanced)

    # 6. Upscaled (2×) for small images – helps OCR on low-resolution scans
    h, w = gray.shape[:2]
    if max(h, w) < 800:
        upscaled = cv2.resize(bgr, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)
        results.append(upscaled)

    # 7. Morphological dilation to thicken thin characters
    kernel = np.ones((2, 2), np.uint8)
    dilated = cv2.dilate(otsu, kernel, iterations=1)
    results.append(dilated)

    return results


# ─────────────────────────────────────────────────────────────────────────────
# OCR
# ─────────────────────────────────────────────────────────────────────────────

def extract_text_from_image(path: Path) -> tuple[str, float]:
    """
    Run EasyOCR on multiple preprocessed versions of the image.
    Returns (best_text, confidence) or ("", 0.0) if OCR is unavailable.
    """
    reader = _get_ocr_reader()
    if reader is None:
        return "", 0.0

    candidates = _preprocess_images(path)
    if not candidates:
        # No OpenCV – try the raw file bytes directly with EasyOCR
        try:
            results = reader.readtext(str(path))
            if results:
                texts = [r[1] for r in results if len(r) >= 2]
                confs = [float(r[2]) for r in results if len(r) >= 3]
                conf  = sum(confs) / len(confs) if confs else 0.0
                return " ".join(texts), round(conf, 3)
        except Exception:
            pass
        return "", 0.0

    best_text  = ""
    best_conf  = 0.0
    best_score = -1.0     # score = length × confidence

    for img in candidates:
        try:
            results = reader.readtext(img)
        except Exception:
            continue

        if not results:
            continue

        texts = [r[1] for r in results if len(r) >= 2]
        confs = [float(r[2]) for r in results if len(r) >= 3]
        conf  = sum(confs) / len(confs) if confs else 0.0
        text  = " ".join(texts)
        score = len(text) * conf

        if score > best_score:
            best_score = score
            best_text  = text
            best_conf  = conf

    return best_text, round(best_conf, 3)


# ─────────────────────────────────────────────────────────────────────────────
# OCR text normalisation
# ─────────────────────────────────────────────────────────────────────────────

# Unicode subscript characters → ASCII digits
_UNICODE_SUBSCRIPTS = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")
# Unicode superscripts → ASCII digits
_UNICODE_SUPERSCRIPTS = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789")


def normalize_ocr_text(raw: str) -> str:
    """
    Normalise raw OCR output into clean chemical equation text.

    Steps
    -----
    1. Unicode subscripts / superscripts → ASCII digits.
    2. Reaction arrow variants → " -> ".
    3. Collapse whitespace.
    4. Chemical formula OCR corrections (common misreads like 202→2O2, H20→H2O).
    """
    if not raw:
        return ""

    text = raw

    # 1. Unicode subscripts / superscripts
    text = text.translate(_UNICODE_SUBSCRIPTS)
    text = text.translate(_UNICODE_SUPERSCRIPTS)

    # 2. Reaction arrows – normalise all variants to " -> "
    #    Order matters: longer/more specific patterns first.
    for pat in ["==>", "-->", "=>", "→", "⟶", "⟹", "—>", ">>"]:
        text = text.replace(pat, " -> ")
    # Also catch spaced/garbled arrows: "- >", "~ >", "—>", etc.
    text = re.sub(r"\s*[-~=—]+\s*>\s*", " -> ", text)

    # 3. Collapse whitespace
    text = re.sub(r"[ \t]+", " ", text).strip()

    # 4. Chemical formula OCR corrections
    # These are applied token-by-token to be safe.
    # We split on spaces, fix each token, then rejoin.
    tokens = text.split()
    fixed_tokens = []
    for tok in tokens:
        fixed_tokens.append(_fix_formula_token(tok))
    text = " ".join(fixed_tokens)

    # Final whitespace cleanup
    text = re.sub(r"[ \t]+", " ", text).strip()
    return text


def _fix_formula_token(tok: str) -> str:
    """
    Fix common OCR misreads in a single formula token.

    Handles:
    - "202"  → "2O2"   (O read as zero, e.g. "2O2" OCR'd as "202")
    - "02"   → "O2"    (element O with subscript, prefix zero)
    - "H20"  → "H2O"   (trailing O read as zero)
    - "C02"  → "CO2"   (O read as zero between letter and digit)
    - "0"    → "O"     isolated oxygen
    - Preserves "Cl", "NaOH", coefficients like "2", "3", etc.
    """
    # Skip the arrow token and "+" separator
    if tok in ("->", "+"):
        return tok

    t = tok

    # ── Pure-digit tokens that might be mis-OCR'd formulas ────────────────
    # "202" → "2O2",  "02" → "O2",  "0" → "O"
    if re.fullmatch(r"\d+", t):
        # Isolated single zero = oxygen atom
        if t == "0":
            return "O"
        # Leading zero only: "02", "03" etc. → "O2", "O3"
        if t.startswith("0") and len(t) >= 2:
            return "O" + t[1:]
        # Middle zero: "202" → "2O2", "103" → "1O3", etc.
        m = re.fullmatch(r"(\d+?)0(\d+)", t)
        if m:
            return m.group(1) + "O" + m.group(2)
        # Leave other pure numbers alone (real coefficients: 2, 3, …)
        return t

    # ── Mixed letter+digit tokens ──────────────────────────────────────────

    # "H20" → "H2O"  (trailing zero that should be O)
    t = re.sub(r"([A-Z][a-z]?\d+)0$", lambda m: m.group(0)[:-1] + "O", t)

    # "C02" → "CO2", "N0" → "NO", etc. (zero directly after capital letter)
    t = re.sub(r"([A-Z])0(\d)", lambda m: m.group(1) + "O" + m.group(2), t)

    # "Na0H" → "NaOH" style (zero between lowercase and uppercase)
    t = re.sub(r"([a-z])0([A-Z])", lambda m: m.group(1) + "O" + m.group(2), t)

    return t


# ─────────────────────────────────────────────────────────────────────────────
# Equation parsing
# ─────────────────────────────────────────────────────────────────────────────

# Recognised formula tokens (extended as needed)
_KNOWN_FORMULAS: dict[str, str] = {
    # formula (normalised) → canonical SMILES key used in COMMON_REACTIONS
    "CH4":      "C",
    "O2":       "O=O",
    "CO2":      "O=C=O",
    "H2O":      "O",
    "H2":       "[H][H]",
    "HCL":      "Cl",        # OCR may produce uppercase
    "HCl":      "Cl",
    "NAOH":     "[Na+].[OH-]",
    "NaOH":     "[Na+].[OH-]",
    "NACL":     "[Na+].[Cl-]",
    "NaCl":     "[Na+].[Cl-]",
    "CH3COOH":  "CC(=O)O",
    "C2H5OH":   "CCO",
    "CH3COOC2H5": "CC(=O)OCC",
}

# Pattern: optional coefficient (int), then formula (letters + digits)
_TOKEN_RE = re.compile(r"(\d+)?\s*([A-Za-z][A-Za-z0-9\[\]\+\-\.]*)")


def _parse_side(side_str: str) -> list[tuple[int, str]]:
    """
    Parse one side of a reaction equation (e.g. "CH4 + 2O2") into a list of
    (coefficient, formula) pairs.
    """
    tokens = []
    for part in re.split(r"\s*\+\s*", side_str.strip()):
        part = part.strip()
        if not part:
            continue
        m = re.match(r"^(\d+)?\s*([A-Z][A-Za-z0-9\[\]\+\-\.]*(?:\([A-Za-z0-9]+\))?)$", part)
        if m:
            coeff   = int(m.group(1)) if m.group(1) else 1
            formula = m.group(2).strip()
            tokens.append((coeff, formula))
        else:
            # Try splitting leading digit from formula
            m2 = re.match(r"^(\d+)([A-Z][A-Za-z0-9\[\]\+\-\.]*)$", part)
            if m2:
                tokens.append((int(m2.group(1)), m2.group(2)))
    return tokens


def parse_equation(text: str) -> dict[str, Any] | None:
    """
    Try to find a chemical equation in `text` and parse it.

    Returns None if no equation is found, otherwise:
    {
        "equation": "CH4 + 2O2 -> CO2 + 2H2O",   # reconstructed
        "reactants": [{"coefficient": 1, "formula": "CH4"}, …],
        "products":  [{"coefficient": 1, "formula": "CO2"}, …],
    }
    """
    # Find the arrow separator (normalised to " -> " by this point)
    arrow_match = re.search(r"\s*->\s*", text)
    if not arrow_match:
        return None

    left  = text[:arrow_match.start()].strip()
    right = text[arrow_match.end():].strip()

    if not left or not right:
        return None

    reactant_tokens = _parse_side(left)
    product_tokens  = _parse_side(right)

    if not reactant_tokens or not product_tokens:
        return None

    def fmt_side(tokens: list[tuple[int, str]]) -> str:
        return " + ".join(
            (f"{c}{f}" if c > 1 else f) for c, f in tokens
        )

    equation = f"{fmt_side(reactant_tokens)} -> {fmt_side(product_tokens)}"

    return {
        "equation":  equation,
        "reactants": [{"coefficient": c, "formula": f} for c, f in reactant_tokens],
        "products":  [{"coefficient": c, "formula": f} for c, f in product_tokens],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Reaction matching
# ─────────────────────────────────────────────────────────────────────────────

def _normalize(value: str) -> str:
    """Lowercase + keep only alphanumeric + spaces."""
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _filename_stem(filename: str | None) -> str:
    if not filename:
        return ""
    stem = Path(filename).stem
    return _normalize(stem.replace("-", " ").replace("_", " "))


def _formulas_match(parsed: dict[str, Any], reaction: dict[str, Any]) -> bool:
    """
    Check whether parsed formulas and stoichiometric coefficients match a
    COMMON_REACTIONS entry. Comparison is order-independent but does not ignore
    extra species or coefficient differences.
    """
    smiles = reaction.get("smiles") or {}
    coefficients = reaction.get("coefficients") or {}

    # Derive formulas from the same validated chemistry toolkit used to
    # construct the geometry; never use a fallback coordinate table as a
    # substitute chemical registry.
    def smiles_to_formula(s: str) -> str | None:
        try:
            from rdkit import Chem
            from rdkit.Chem import rdMolDescriptors

            molecule = Chem.MolFromSmiles(s)
            return rdMolDescriptors.CalcMolFormula(molecule).upper() if molecule else None
        except Exception:
            return None

    def expected_side(side: str) -> Counter:
        expected = Counter()
        sides = smiles.get(side, [])
        side_coefficients = coefficients.get(side, [])
        for index, value in enumerate(sides):
            formula = smiles_to_formula(value)
            if formula is None:
                return Counter()
            coefficient = side_coefficients[index] if index < len(side_coefficients) else 1
            expected[(formula, int(coefficient))] += 1
        return expected

    def parsed_side(side: str) -> Counter:
        return Counter(
            (item["formula"].upper(), int(item.get("coefficient", 1)))
            for item in parsed.get(side, [])
        )

    expected_r = expected_side("reactants")
    expected_p = expected_side("products")
    if not expected_r or not expected_p:
        return False
    return expected_r == parsed_side("reactants") and expected_p == parsed_side("products")


def match_common_reaction(
    extracted_text: str,
    original_filename: str | None,
    parsed_equation: dict[str, Any] | None = None,
    ml_reaction_type: str | None = None,
    ml_confidence: float = 0.0,
) -> dict[str, Any] | None:
    """
    Identify the best matching reaction from COMMON_REACTIONS.

    Priority order:
      1. Parsed equation formula match (score +1000)
      2. Alias in filename (score +100 per alias)
      3. Alias in OCR text  (score +80 per alias)
      4. Key-term scoring, equation tokens, reactant/product names

    The bundled image classifier is retained as a suggestion only. Its saved
    held-out evaluation is too weak to identify reactions reliably.
    """
    filename_norm = _filename_stem(original_filename)
    ocr_norm      = _normalize(extracted_text)
    haystack      = (filename_norm + " " + ocr_norm).strip()
    parsed_formula_names = {
        _normalize(item.get("formula", ""))
        for side in (parsed_equation or {}).values()
        if isinstance(side, list)
        for item in side
        if isinstance(item, dict)
    }

    best_score    = 0
    best_reaction = None

    for reaction in COMMON_REACTIONS:
        score = 0

        # 1. Parsed equation formula match
        if parsed_equation and _formulas_match(parsed_equation, reaction):
            score += 1000

        # 2. Alias in filename
        for alias in reaction.get("aliases", []):
            alias_norm = _normalize(alias)
            if alias_norm and alias_norm in filename_norm:
                score += 100

        # 3. Alias in OCR text
        for alias in reaction.get("aliases", []):
            alias_norm = _normalize(alias)
            if parsed_equation and any(
                alias_norm in formula or formula in alias_norm
                for formula in parsed_formula_names
            ):
                continue
            if alias_norm and alias_norm in ocr_norm:
                score += 80

        # 4. Weak token overlap is useful only when there was no parseable
        # equation. Once the OCR parser found an equation, a different
        # stoichiometry must not be promoted by shared formula tokens.
        if not parsed_equation:
            for term in reaction["key"].split():
                if len(term) >= 2 and term in haystack:
                    score += 1

            for token in _normalize(reaction["equation"]).split():
                if len(token) >= 2 and token in haystack:
                    score += 1

            for name in (reaction.get("reactants") or []) + (reaction.get("products") or []):
                if _normalize(name) in haystack:
                    score += 2

        if score > best_score:
            best_score    = score
            best_reaction = reaction

    if best_score < 3:
        return None

    return best_reaction


# ─────────────────────────────────────────────────────────────────────────────
# Result builders
# ─────────────────────────────────────────────────────────────────────────────

def _unverified_result(
    extracted_text: str,
    ocr_confidence: float,
    reason: str = "",
) -> dict[str, Any]:
    summary = (
        "ChemVision saved the image but could not confidently identify a known reaction. "
        "For best results, name the file after the reaction (e.g. 'methane_combustion.png') "
        "or upload a clear printed/digital image of the equation."
    )
    if reason:
        summary = f"{reason} {summary}"

    return {
        "reaction_name": "Unverified reaction upload",
        "equation": extracted_text or None,
        "reaction_type": "Requires review",
        "summary": summary,
        "mechanism": "No mechanism generated until the reaction is verified.",
        "reactants": [],
        "products":  [],
        "conditions": [],
        "catalyst":  None,
        "temperature": None,
        "safety_notes": (
            "Review the source image and confirm the reaction before "
            "using this result for laboratory decisions."
        ),
        "extracted_text":       extracted_text,
        "ocr_confidence":       ocr_confidence,
        "requires_verification": True,
        "visualization_data": {
            "engine": "unavailable",
            "molecules": {"reactants": [], "products": []},
        },
    }


def _matched_result(
    matched: dict[str, Any],
    extracted_text: str,
    ocr_confidence: float,
    identified_via: str = "matched",
) -> dict[str, Any]:
    skip = {"key", "aliases", "smiles", "coefficients"}
    result: dict[str, Any] = {k: v for k, v in matched.items() if k not in skip}

    # Only an equation parsed from OCR with reasonable OCR confidence is
    # treated as identified. A filename, classifier suggestion, or keyword
    # overlap alone is not evidence that the image depicts this reaction.
    requires_verification = not (
        identified_via == "formula_match" and ocr_confidence >= 0.55
    )

    result.update({
        "extracted_text":       extracted_text,
        "ocr_confidence":       ocr_confidence,
        "requires_verification": requires_verification,
        "visualization_data":   build_visualization_data(matched),
    })
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────

def process_reaction_image(
    path: Path,
    original_filename: str | None,
) -> dict[str, Any]:
    """
    Full pipeline: image → ML classifier + OCR → parse → match → molecule data.
    """
    # Step 1: Try custom ML classifier first
    ml_result = None
    ml_reaction_type = None
    ml_confidence    = 0.0
    try:
        from app.services.ml_classifier import classify_image, model_available
        if model_available():
            ml_result = classify_image(path, top_k=3)
            if ml_result.get("success") and ml_result.get("confidence", 0) >= 0.25:
                ml_reaction_type = ml_result["top_reaction"]
                ml_confidence    = ml_result["confidence"]
                logger.info(
                    "ML classifier: %s (conf=%.3f) for %s",
                    ml_reaction_type, ml_confidence, original_filename
                )
        else:
            logger.info("ML classifier not available (not trained yet) — using OCR only")
    except Exception as exc:
        logger.warning("ML classifier error (non-fatal): %s", exc)

    # Step 2: OCR
    raw_text, ocr_confidence = extract_text_from_image(path)
    logger.info(
        "OCR for '%s': conf=%.3f text=%r",
        original_filename, ocr_confidence, raw_text[:100],
    )

    # Step 3: Normalise OCR text
    normalized_text = normalize_ocr_text(raw_text)

    # Step 4: Parse equation from OCR text
    parsed = parse_equation(normalized_text) if normalized_text else None
    if parsed:
        logger.info("Parsed equation: %s", parsed.get("equation"))

    # Step 5: Match using the equation and textual evidence. The classifier
    # output is not used to decide identity because its held-out accuracy is
    # currently inadequate.
    matched = match_common_reaction(
        extracted_text    = normalized_text,
        original_filename = original_filename,
        parsed_equation   = parsed,
        ml_reaction_type  = ml_reaction_type,
        ml_confidence     = ml_confidence,
    )

    if matched is None:
        reason = ""
        if raw_text and not parsed:
            reason = "OCR extracted text but could not parse a chemical equation."
        elif not raw_text and not ml_reaction_type:
            reason = "OCR could not extract text from this image."
        return _unverified_result(normalized_text or raw_text, ocr_confidence, reason)

    # Determine verification flag
    if parsed and _formulas_match(parsed, matched):
        via = "formula_match"
    elif _filename_stem(original_filename):
        via = "filename"
    else:
        via = "ocr"

    result = _matched_result(matched, normalized_text or raw_text, ocr_confidence, via)

    # Attach ML metadata to the result
    if ml_result and ml_result.get("success"):
        result["ml_predictions"] = ml_result.get("predictions", [])
        result["ml_model_used"]  = ml_result.get("model_used", "none")
    else:
        result["ml_predictions"] = []
        result["ml_model_used"]  = "none"

    return result
