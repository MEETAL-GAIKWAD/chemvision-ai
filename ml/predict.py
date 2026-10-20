"""
ChemVision AI — Prediction Interface
Reusable inference module used by both the backend integration and standalone CLI.

Usage (CLI):
    python ml/predict.py path/to/image.jpg
    python ml/predict.py path/to/image.jpg --top_k 5
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ml"))


# ── lazy-loaded global model state ────────────────────────────────────────────
_model_state: dict[str, Any] | None = None


def _get_model_state(device: str = "cpu") -> dict[str, Any] | None:
    """
    Load and cache the model. Returns None if checkpoint not found.
    Thread-safe (called once; FastAPI workers reuse the cached state).
    """
    global _model_state
    if _model_state is not None:
        return _model_state

    ckpt_dir       = ROOT / "backend" / "models" / "chemvision_classifier"
    ckpt_path      = ckpt_dir / "best_model.pth"
    class_map_path = ckpt_dir / "class_map.json"

    try:
        import torch
        from torchvision import transforms
        from model import load_model_for_inference

        model, idx_to_class, class_to_idx = load_model_for_inference(
            ckpt_path, class_map_path, device
        )

        val_tf = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std =[0.229, 0.224, 0.225],
            ),
        ])

        _model_state = {
            "model":       model,
            "transform":   val_tf,
            "idx_to_class": idx_to_class,
            "class_to_idx": class_to_idx,
            "device":      device,
            "loaded":      True,
        }
        print(f"[ChemVision ML] Reaction classifier loaded from {ckpt_path}")

    except FileNotFoundError as exc:
        print(f"[ChemVision ML] Model not available: {exc}")
        _model_state = {"loaded": False, "reason": str(exc)}

    except Exception as exc:
        print(f"[ChemVision ML] Model load error: {exc}")
        _model_state = {"loaded": False, "reason": str(exc)}

    return _model_state


def predict_reaction_type(
    image_path: str | Path,
    top_k: int = 3,
    device: str = "cpu",
) -> dict[str, Any]:
    """
    Predict the reaction type from an image.

    Returns:
    {
        "success":     bool,
        "model_used":  "chemvision_classifier" | "none",
        "predictions": [
            {"reaction_type": str, "confidence": float},
            ...  (top_k entries, sorted by confidence)
        ],
        "top_reaction":   str | None,
        "confidence":     float | None,
        "error":          str | None   (only on failure)
    }
    """
    import torch
    from PIL import Image

    state = _get_model_state(device)

    if not state or not state.get("loaded"):
        return {
            "success":    False,
            "model_used": "none",
            "predictions": [],
            "top_reaction": None,
            "confidence":   None,
            "error": state.get("reason", "Model not loaded") if state else "Model not loaded",
        }

    try:
        img = Image.open(image_path).convert("RGB")
        tensor = state["transform"](img).unsqueeze(0).to(state["device"])

        with torch.no_grad():
            logits = state["model"](tensor)
            probs  = torch.softmax(logits, dim=1)[0]

        k = min(top_k, probs.shape[0])
        top_probs, top_idxs = torch.topk(probs, k)

        predictions = [
            {
                "reaction_type": state["idx_to_class"][idx.item()],
                "confidence":    round(prob.item(), 4),
            }
            for prob, idx in zip(top_probs, top_idxs)
        ]

        return {
            "success":      True,
            "model_used":   "chemvision_classifier",
            "predictions":  predictions,
            "top_reaction": predictions[0]["reaction_type"] if predictions else None,
            "confidence":   predictions[0]["confidence"]    if predictions else None,
            "error":        None,
        }

    except Exception as exc:
        return {
            "success":      False,
            "model_used":   "none",
            "predictions":  [],
            "top_reaction": None,
            "confidence":   None,
            "error":        str(exc),
        }


def reset_model_cache() -> None:
    """Force reload of the model on next call (useful after training)."""
    global _model_state
    _model_state = None


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Predict reaction type from image")
    parser.add_argument("image", help="Path to image file")
    parser.add_argument("--top_k",  type=int, default=3)
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda"])
    args = parser.parse_args()

    result = predict_reaction_type(args.image, args.top_k, args.device)

    if result["success"]:
        print(f"\nTop-{args.top_k} predictions for: {args.image}")
        for i, pred in enumerate(result["predictions"], 1):
            bar = "█" * int(pred["confidence"] * 20)
            print(f"  {i}. {pred['reaction_type']:<45}  {pred['confidence']:.1%}  {bar}")
    else:
        print(f"\nPrediction failed: {result['error']}")
        print("Have you trained the model? Run: python ml/train.py")
