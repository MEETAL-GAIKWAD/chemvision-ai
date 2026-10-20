"""
ChemVision AI — ML Classifier Service
Wraps the trained EfficientNet-B0 reaction type classifier.

The classifier returns experimental reaction-class suggestions. The saved
held-out evaluation is too weak for these suggestions to establish reaction
identity, so the reaction processor does not use them to select a reaction.
The adapter provides confidence metadata and fails gracefully if unavailable.

The model is loaded once per process (lazy singleton).
"""
from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── paths ─────────────────────────────────────────────────────────────────────
_BASE   = Path(__file__).resolve().parents[3]   # project root
_ML_DIR = _BASE / "ml"
_CKPT   = _BASE / "backend" / "models" / "chemvision_classifier" / "best_model.pth"
_CMAP   = _BASE / "backend" / "models" / "chemvision_classifier" / "class_map.json"

# ── singleton ─────────────────────────────────────────────────────────────────
_state: dict | None = None
_lock  = threading.Lock()


def _load() -> dict:
    """Load model once; return state dict."""
    global _state
    if _state is not None:
        return _state
    with _lock:
        if _state is not None:
            return _state

        import sys
        sys.path.insert(0, str(_ML_DIR))

        try:
            import torch
            from torchvision import transforms
            from model import load_model_for_inference  # type: ignore

            model, idx_to_class, class_to_idx = load_model_for_inference(
                _CKPT, _CMAP, "cpu"
            )
            tf = transforms.Compose([
                transforms.Resize((224, 224)),
                transforms.ToTensor(),
                transforms.Normalize(
                    mean=[0.485, 0.456, 0.406],
                    std =[0.229, 0.224, 0.225],
                ),
            ])
            _state = {
                "ok": True,
                "model": model, "transform": tf,
                "idx_to_class": idx_to_class,
                "class_to_idx": class_to_idx,
            }
            logger.info("ChemVision ML classifier loaded (%d classes)", len(class_to_idx))

        except FileNotFoundError as exc:
            logger.warning("ML model not available (not trained yet): %s", exc)
            _state = {"ok": False, "reason": "Model not trained yet. Run ml/train.py first."}

        except Exception as exc:
            logger.warning("ML model load failed: %s", exc)
            _state = {"ok": False, "reason": str(exc)}

        return _state


def model_available() -> bool:
    return _load().get("ok", False)


def classify_image(image_path: str | Path, top_k: int = 3) -> dict[str, Any]:
    """
    Predict reaction type from image.

    Returns
    -------
    {
        "success":      bool,
        "model_used":   "chemvision_classifier" | "none",
        "top_reaction": str | None,   # best prediction
        "confidence":   float | None, # 0-1
        "predictions":  [{reaction_type, confidence}, ...]  # top_k
        "error":        str | None
    }
    """
    st = _load()
    if not st.get("ok"):
        return {
            "success": False, "model_used": "none",
            "top_reaction": None, "confidence": None,
            "predictions": [], "error": st.get("reason", "unavailable"),
        }

    try:
        import torch
        from PIL import Image

        img    = Image.open(image_path).convert("RGB")
        tensor = st["transform"](img).unsqueeze(0)

        with torch.no_grad():
            logits = st["model"](tensor)
            probs  = torch.softmax(logits, dim=1)[0]

        k = min(top_k, probs.shape[0])
        top_p, top_i = torch.topk(probs, k)
        preds = [
            {
                "reaction_type": st["idx_to_class"][i.item()],
                "confidence":    round(p.item(), 4),
            }
            for p, i in zip(top_p, top_i)
        ]

        return {
            "success":      True,
            "model_used":   "chemvision_classifier",
            "top_reaction": preds[0]["reaction_type"] if preds else None,
            "confidence":   preds[0]["confidence"]    if preds else None,
            "predictions":  preds,
            "error":        None,
        }

    except Exception as exc:
        logger.error("ML inference error: %s", exc)
        return {
            "success": False, "model_used": "none",
            "top_reaction": None, "confidence": None,
            "predictions": [], "error": str(exc),
        }


def reset_cache() -> None:
    """Force reload on next call (useful after retraining)."""
    global _state
    _state = None
