"""
ChemVision AI — Model definition.

Architecture: EfficientNet-B0 with transfer learning.
Chosen because:
  - Very small dataset (153 train images) → heavy pretrained features essential
  - EfficientNet-B0 is lightweight (5.3M params) but accurate
  - torchvision has pretrained weights (ImageNet) — no extra download needed
  - Top-1 ~77% on ImageNet with only 5.3M params

For a dataset this small we:
  1. Freeze all backbone layers initially
  2. Fine-tune only the classifier head for N epochs
  3. Unfreeze all and fine-tune at a lower LR for remaining epochs
"""

from __future__ import annotations

import json
from pathlib import Path

import torch
import torch.nn as nn
from torchvision import models


def build_model(num_classes: int, pretrained: bool = True, dropout: float = 0.3) -> nn.Module:
    """Return an EfficientNet-B0 adapted for num_classes."""
    weights = models.EfficientNet_B0_Weights.IMAGENET1K_V1 if pretrained else None
    model = models.efficientnet_b0(weights=weights)

    # Replace classifier head
    in_features = model.classifier[1].in_features
    model.classifier = nn.Sequential(
        nn.Dropout(p=dropout, inplace=True),
        nn.Linear(in_features, num_classes),
    )
    return model


def freeze_backbone(model: nn.Module) -> None:
    """Freeze all layers except the classifier head."""
    for name, param in model.named_parameters():
        if "classifier" not in name:
            param.requires_grad = False


def unfreeze_all(model: nn.Module) -> None:
    """Unfreeze all parameters for fine-tuning."""
    for param in model.parameters():
        param.requires_grad = True


def count_params(model: nn.Module) -> tuple[int, int]:
    total     = sum(p.numel() for p in model.parameters())
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    return total, trainable


def save_checkpoint(
    model: nn.Module,
    optimizer: torch.optim.Optimizer,
    epoch: int,
    val_acc: float,
    class_map: dict[str, int],
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "epoch":         epoch,
            "val_acc":       val_acc,
            "model_state":   model.state_dict(),
            "optimizer_state": optimizer.state_dict(),
            "num_classes":   len(class_map),
        },
        path,
    )


def load_model_for_inference(
    checkpoint_path: Path,
    class_map_path: Path,
    device: str = "cpu",
) -> tuple[nn.Module, dict[int, str], dict[str, int]]:
    """
    Load a trained model and its class mapping.
    Returns (model, idx_to_class, class_to_idx).
    Raises FileNotFoundError if checkpoint is missing.
    """
    if not checkpoint_path.exists():
        raise FileNotFoundError(
            f"Model checkpoint not found: {checkpoint_path}. "
            "Run ml/train.py first to train the model."
        )
    if not class_map_path.exists():
        raise FileNotFoundError(
            f"Class map not found: {class_map_path}. "
            "Run ml/train.py first."
        )

    with open(class_map_path) as f:
        class_to_idx: dict[str, int] = json.load(f)

    idx_to_class: dict[int, str] = {v: k for k, v in class_to_idx.items()}
    num_classes = len(class_to_idx)

    ckpt  = torch.load(checkpoint_path, map_location=device, weights_only=True)
    model = build_model(num_classes=num_classes, pretrained=False)
    model.load_state_dict(ckpt["model_state"])
    model.to(device)
    model.eval()

    return model, idx_to_class, class_to_idx
