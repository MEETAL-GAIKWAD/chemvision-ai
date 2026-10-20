"""
ChemVision AI — Dataset loader for COCO-format reaction classification dataset.

The chemvision.v7i.coco dataset uses COCO annotation format but is actually
an image classification dataset:
  - Each image has exactly ONE annotation
  - The bounding box covers the entire image (100% coverage)
  - The category name IS the reaction type label

This module normalises reviewed aliases and builds PyTorch Datasets. Unknown
labels and invalid samples are errors by default: they must not disappear from
training or evaluation metrics.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import torch
from PIL import Image, UnidentifiedImageError
from torch.utils.data import Dataset


# ── canonical class mapping (merges duplicate/misspelled labels) ──────────────
# Maps every raw category name → canonical class name
CANONICAL_MAP: dict[str, str] = {
    # Keep as-is (39 unique canonical classes)
    "Addition Anti-Markovnikov":            "Addition Anti-Markovnikov",
    "Addition Dihydroxylation":             "Addition Dihydroxylation",
    "Addition Hydration":                   "Addition Hydration",
    "Addition Hydrohalogenation":           "Addition Hydrohalogenation",
    "Addition Markovnikov":                 "Addition Markovnikov",
    "AdditionHalogenation":                 "Addition Halogenation",
    "AdditionHydrogenation":                "Addition Hydrogenation",
    "Aldol Condensation":                   "Aldol Condensation",
    "Cannizzaro Reaction":                  "Cannizzaro Reaction",
    "Carbamine Reaction":                   "Carbylamine Reaction",   # merge
    "Carbylamine Reaction":                 "Carbylamine Reaction",
    "Clamensen Reduction":                  "Clemmensen Reduction",   # merge
    "Clemmensen Reduction":                 "Clemmensen Reduction",
    "Colbe-Schmitt Reaction":               "Kolbe-Schmitt Reaction", # merge
    "Combustion of Ethane":                 "Combustion of Ethane",
    "Combustion of Ethene":                 "Combustion of Ethene",
    "Combustion of Ethyne":                 "Combustion of Ethyne",
    "Combustion of Methane":                "Combustion of Methane",
    "Coupling Reaction":                    "Coupling Reaction",
    "Decarboxylation Reaction":             "Decarboxylation Reaction",
    "Decarboxylation Soda Lime":            "Decarboxylation Reaction", # merge
    "Diazotisation Reaction":               "Diazotization Reaction",  # merge
    "Diazotization":                        "Diazotization Reaction",  # merge
    "Diazotization Reaction":               "Diazotization Reaction",
    "Esterification":                       "Esterification Reaction", # merge
    "Esterification Acetylation":           "Esterification Reaction", # merge
    "Esterification Reaction":              "Esterification Reaction",
    "Etard Reaction":                       "Etard Reaction",
    "Finkelstein Reaction":                 "Finkelstein Reaction",
    "Fittig Reaction":                      "Fittig Reaction",
    "Friedel Crafts Acylation":             "Friedel-Crafts Acylation",
    "FriedelCrafts Aclylation":             "Friedel-Crafts Acylation", # merge typo
    "Friedel Crafts Alkylation":            "Friedel-Crafts Alkylation",
    "Friedel Crafts Methylation":           "Friedel-Crafts Alkylation", # merge
    "FriedelCrafts Alkylation":             "Friedel-Crafts Alkylation", # merge
    "Fries rearrangement":                  "Fries Rearrangement",
    "Gabriel Phthalimide Reaction":         "Gabriel Synthesis",       # merge
    "Gabriel Phthalimide Synthesis":        "Gabriel Synthesis",       # merge
    "Gabriel Synthesis":                    "Gabriel Synthesis",
    "Gatterman Reaction":                   "Gattermann Reaction",     # merge
    "Gatterman ReactionGabriel Phthalimide Reaction": "Gattermann Reaction", # merge
    "Gattermann Reaction":                  "Gattermann Reaction",
    "GattermannKoch Reaction":              "Gattermann-Koch Reaction",
    "Grignard Reagent Formation":           "Grignard Reagent Formation",
    "Haloform Reaction":                    "Haloform Reaction",
    "Halogenation of Benzene":              "Halogenation of Benzene",
    "HellVolhard Zelinsky Reaction":        "Hell-Volhard-Zelinsky Reaction",
    "Hofmann Bromamide Reaction":           "Hofmann Bromamide Reaction",
    "Holmann Ammonolysis":                  "Hofmann Ammonolysis",     # typo merge
    "Hunsdicker Reaction":                  "Hunsdiecker Reaction",    # merge
    "Hydration of Alkyne":                  "Hydration of Alkyne",
    "Hydrolysis of Ester Acidic":           "Hydrolysis of Ester",     # merge
    "Hydrolysis of Ester Basic":            "Hydrolysis of Ester",     # merge
    "Iodoform Reaction":                    "Iodoform Reaction",
    "Kolbe Electrolysis":                   "Kolbe Electrolysis",
    "KolbeSchmitt Reaction":                "Kolbe-Schmitt Reaction",  # merge
    "Kolbes Reaction":                      "Kolbe-Schmitt Reaction",  # merge
    "Liebermannsnitroso Reaction":          "Liebermann-Nitroso Reaction",
    "Mendius Reaction":                     "Mendius Reaction",
    "Nitration of Benzene":                 "Nitration of Benzene",
    "Nucleophilic Substitution":            "Nucleophilic Substitution",
    "Oxidation Alcohol to Acid":            "Oxidation Alcohol to Acid",
    "Oxidation Alcohol to Aldehyde":        "Oxidation Alcohol to Aldehyde",
    "Oxidation Alkene to Diol":             "Oxidation Alkene to Diol",
    "Ozonolysis":                           "Ozonolysis",
    "Perkin Reaction":                      "Perkin Reaction",
    "Polymerization":                       "Polymerization",
    "Reaction with CO2 Grignard":           "Reaction with CO2 Grignard",
    "Reduction Alkyne to Alkane":           "Reduction Alkyne to Alkane",
    "Reduction Alkyne to Alkene":           "Reduction Alkyne to Alkene",
    "Reduction of Nitrobenzene":            "Reduction of Nitrobenzene",
    "Reimer Tiemann Reaction":              "Reimer-Tiemann Reaction",  # merge
    "Reimer-TiemannReaction":               "Reimer-Tiemann Reaction",  # merge
    "ReimerTiemann Reaction":               "Reimer-Tiemann Reaction",  # merge
    "ReimerTiemannReaction":                "Reimer-Tiemann Reaction",  # merge
    "Rosenmund Reaction":                   "Rosenmund Reaction",
    "Sandmeyer Reaction":                   "Sandmeyer Reaction",
    "Sandmeyers Reaction":                  "Sandmeyer Reaction",       # merge
    "Saponification":                       "Saponification",
    "Schotten Baumann Reaction":            "Schotten-Baumann Reaction",
    "Stephen Reaction":                     "Stephen Reaction",
    "Substitution Alkane Halogenation":     "Substitution Alkane Halogenation",
    "Sulphonation of Benzene":              "Sulphonation of Benzene",
    "Swarts Reaction":                      "Swarts Reaction",
    "Williamson Ether Synthesis":           "Williamson Ether Synthesis",
    "WolffKishner Reduction":               "Wolff-Kishner Reduction",
    "Wurtz Reaction":                       "Wurtz Reaction",
    "WurtzFittig Reaction":                 "Wurtz-Fittig Reaction",
}


def build_class_map(train_annotation_path: str | Path) -> tuple[list[str], dict[str, int], dict[int, str]]:
    """
    Build class index mapping from training annotations.
    Only includes classes that actually appear in training data.
    Returns:
        class_names  – sorted list of canonical class names
        class_to_idx – name → integer index
        idx_to_class – integer index → name
    """
    with open(train_annotation_path) as f:
        data = json.load(f)

    raw_cat_names = {c["id"]: c["name"] for c in data["categories"]}
    if len(raw_cat_names) != len(data["categories"]):
        raise ValueError(f"Duplicate category IDs in {train_annotation_path}")
    seen: set[str] = set()
    for ann in data["annotations"]:
        if ann.get("category_id") not in raw_cat_names:
            raise ValueError(f"Unknown category_id in {train_annotation_path}: {ann.get('category_id')}")
        raw = raw_cat_names[ann["category_id"]]
        canonical = CANONICAL_MAP.get(raw, raw)
        seen.add(canonical)

    class_names  = sorted(seen)
    class_to_idx = {name: idx for idx, name in enumerate(class_names)}
    idx_to_class = {idx: name for name, idx in class_to_idx.items()}
    return class_names, class_to_idx, idx_to_class


class ReactionDataset(Dataset):
    """
    PyTorch Dataset for the CHEMVISION COCO reaction classification dataset.

    Treats each image as belonging to the single category annotated for it.
    """

    def __init__(
        self,
        image_dir: str | Path,
        annotation_file: str | Path,
        class_to_idx: dict[str, int],
        transform=None,
    ) -> None:
        self.image_dir   = Path(image_dir)
        self.transform   = transform
        self.class_to_idx = class_to_idx

        with open(annotation_file) as f:
            coco = json.load(f)

        raw_cat_names = {c["id"]: c["name"] for c in coco["categories"]}
        id_to_filename = {img["id"]: img["file_name"] for img in coco["images"]}
        if len(id_to_filename) != len(coco["images"]):
            raise ValueError(f"Duplicate image IDs in {annotation_file}")
        if len(raw_cat_names) != len(coco["categories"]):
            raise ValueError(f"Duplicate category IDs in {annotation_file}")

        annotations_by_image: dict[int, list[dict[str, Any]]] = {}
        for ann in coco["annotations"]:
            annotations_by_image.setdefault(ann.get("image_id"), []).append(ann)

        errors: list[str] = []
        for image_id, filename in id_to_filename.items():
            anns = annotations_by_image.get(image_id, [])
            if len(anns) != 1:
                errors.append(f"{filename}: expected exactly one class annotation, found {len(anns)}")
                continue
            ann = anns[0]
            category_id = ann.get("category_id")
            if category_id not in raw_cat_names:
                errors.append(f"{filename}: unknown category_id {category_id}")
                continue
            raw = raw_cat_names[category_id]
            canonical = CANONICAL_MAP.get(raw, raw)
            if canonical not in class_to_idx:
                errors.append(f"{filename}: label {raw!r} ({canonical!r}) is absent from the training class map")
                continue
            img_path = self.image_dir / filename
            if not img_path.is_file():
                errors.append(f"{filename}: image file is missing")
                continue
            try:
                with Image.open(img_path) as image:
                    image.verify()
            except (OSError, UnidentifiedImageError) as exc:
                errors.append(f"{filename}: invalid image ({exc})")

        extra_ids = set(annotations_by_image) - set(id_to_filename)
        if extra_ids:
            errors.append(f"{len(extra_ids)} annotation(s) reference unknown image IDs: {sorted(extra_ids)[:10]}")
        if errors:
            sample = "\n  - ".join(errors[:20])
            suffix = f"\n  ... and {len(errors) - 20} more" if len(errors) > 20 else ""
            raise ValueError(f"Dataset validation failed for {annotation_file}:\n  - {sample}{suffix}")

        self.samples: list[tuple[Path, int]] = []
        for image_id, filename in id_to_filename.items():
            ann = annotations_by_image[image_id][0]
            raw = raw_cat_names[ann["category_id"]]
            canonical = CANONICAL_MAP.get(raw, raw)
            self.samples.append((self.image_dir / filename, class_to_idx[canonical]))
        if len(self.samples) != len(coco["images"]):
            raise AssertionError("Dataset accounting invariant failed: not every manifest image became a sample")

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> tuple[Any, int]:
        img_path, label = self.samples[idx]
        img = Image.open(img_path).convert("RGB")
        if self.transform:
            img = self.transform(img)
        return img, label

    def class_distribution(self) -> dict[str, int]:
        from collections import Counter
        idx_to_name = {v: k for k, v in self.class_to_idx.items()}
        return dict(Counter(idx_to_name[lbl] for _, lbl in self.samples))
