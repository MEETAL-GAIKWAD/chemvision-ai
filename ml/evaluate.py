"""
ChemVision AI — Evaluation Script
Reports accuracy, per-class metrics, and representative errors on the test set.

Usage:
    cd ml
    python evaluate.py                              # uses saved checkpoint
    python evaluate.py --split test                 # explicit split
    python evaluate.py --split valid                # validate set
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import torch
from PIL import Image, UnidentifiedImageError
from torch.utils.data import DataLoader
from torchvision import transforms

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ml"))

from dataset import ReactionDataset, build_class_map
from dataset import CANONICAL_MAP
from model   import load_model_for_inference

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD  = [0.229, 0.224, 0.225]


def evaluate_model(model, dataset, idx_to_class: dict[int, str],
                   device: str = "cpu", batch_size: int = 8) -> dict:
    """Run evaluation and return a metrics report dict."""
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=False, num_workers=0)
    model.eval()

    all_preds  = []
    all_labels = []
    all_probs  = []

    with torch.no_grad():
        for images, labels in loader:
            images = images.to(device)
            logits = model(images)
            probs  = torch.softmax(logits, dim=1)
            preds  = logits.argmax(dim=1)
            all_preds.extend(preds.cpu().tolist())
            all_labels.extend(labels.tolist())
            all_probs.extend(probs.cpu().tolist())

    total   = len(all_labels)
    correct = sum(p == l for p, l in zip(all_preds, all_labels))
    accuracy = correct / total if total else 0.0

    # Per-class stats
    class_correct   = defaultdict(int)
    class_total     = defaultdict(int)
    class_predicted = defaultdict(int)

    for pred, label in zip(all_preds, all_labels):
        class_total[label]    += 1
        class_predicted[pred] += 1
        if pred == label:
            class_correct[label] += 1

    per_class = {}
    for cls_idx in sorted(class_total.keys()):
        name      = idx_to_class.get(cls_idx, f"class_{cls_idx}")
        tp        = class_correct[cls_idx]
        support   = class_total[cls_idx]
        predicted = class_predicted[cls_idx]
        precision = tp / predicted if predicted else 0.0
        recall    = tp / support   if support   else 0.0
        f1 = (2 * precision * recall / (precision + recall)
              if (precision + recall) > 0 else 0.0)
        per_class[name] = {
            "support":   support,
            "correct":   tp,
            "precision": round(precision, 3),
            "recall":    round(recall, 3),
            "f1":        round(f1, 3),
        }

    observed_classes = sorted(class_total)
    macro_f1 = (
        sum(per_class[idx_to_class.get(i, f"class_{i}")]["f1"] for i in observed_classes)
        / len(observed_classes)
        if observed_classes else 0.0
    )
    balanced_accuracy = (
        sum(class_correct[i] / class_total[i] for i in observed_classes)
        / len(observed_classes)
        if observed_classes else 0.0
    )
    confusion = {
        idx_to_class.get(actual, f"class_{actual}"): {
            idx_to_class.get(predicted, f"class_{predicted}"): sum(
                1 for pred, label in zip(all_preds, all_labels)
                if label == actual and pred == predicted
            )
            for predicted in sorted(set(all_preds))
        }
        for actual in observed_classes
    }

    # Top-3 accuracy
    top3_correct = 0
    for true_label, probs in zip(all_labels, all_probs):
        top3 = sorted(range(len(probs)), key=lambda i: -probs[i])[:3]
        if true_label in top3:
            top3_correct += 1
    top3_acc = top3_correct / total if total else 0.0

    confidence_analysis = {}
    for threshold in (0.5, 0.7, 0.9):
        selected = [
            (pred, label) for pred, label, probs in zip(all_preds, all_labels, all_probs)
            if max(probs, default=0.0) >= threshold
        ]
        confidence_analysis[str(threshold)] = {
            "coverage": round(len(selected) / total, 4) if total else 0.0,
            "accuracy": round(sum(pred == label for pred, label in selected) / len(selected), 4)
            if selected else None,
            "selected": len(selected),
        }

    # Representative errors (up to 5)
    errors = []
    idx_to_filename = {i: str(dataset.samples[i][0].name) for i in range(len(dataset))}
    for i, (pred, label) in enumerate(zip(all_preds, all_labels)):
        if pred != label and len(errors) < 5:
            errors.append({
                "image":     idx_to_filename.get(i, ""),
                "true_class": idx_to_class.get(label, str(label)),
                "pred_class": idx_to_class.get(pred, str(pred)),
                "confidence": round(all_probs[i][pred], 3),
            })

    return {
        "total":      total,
        "correct":    correct,
        "accuracy":   round(accuracy, 4),
        "top3_accuracy": round(top3_acc, 4),
        "macro_f1": round(macro_f1, 4),
        "balanced_accuracy": round(balanced_accuracy, 4),
        "confusion_matrix": confusion,
        "confidence_threshold_analysis": confidence_analysis,
        "per_class":  per_class,
        "errors":     errors,
    }


class ManifestSamples(torch.utils.data.Dataset):
    def __init__(self, samples, transform):
        self.samples = samples
        self.transform = transform

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, index):
        path, label = self.samples[index]
        with Image.open(path) as image:
            tensor = self.transform(image.convert("RGB"))
        return tensor, label, path.name


def evaluate_complete_manifest(model, split_dir: Path, class_map: dict[str, int], device: str, batch_size: int) -> dict:
    """Evaluate every valid manifest image; unseen training labels count as incorrect."""
    annotation_file = split_dir / "_annotations.coco.json"
    coco = json.loads(annotation_file.read_text(encoding="utf-8"))
    categories = {item["id"]: item["name"] for item in coco.get("categories", [])}
    images = {item["id"]: item for item in coco.get("images", [])}
    by_image: dict[int, list[dict]] = defaultdict(list)
    for annotation in coco.get("annotations", []):
        by_image[annotation.get("image_id")].append(annotation)

    samples, exclusions = [], []
    for image_id, info in images.items():
        filename = info.get("file_name", "")
        path = split_dir / filename
        reasons = []
        annotations = by_image.get(image_id, [])
        if len(annotations) != 1:
            reasons.append(f"expected one annotation, found {len(annotations)}")
        category_id = annotations[0].get("category_id") if len(annotations) == 1 else None
        raw_label = categories.get(category_id)
        if raw_label is None:
            reasons.append(f"unknown category_id {category_id}")
        if not path.is_file():
            reasons.append("image file missing")
        else:
            try:
                with Image.open(path) as image:
                    image.verify()
            except (OSError, UnidentifiedImageError) as exc:
                reasons.append(f"invalid image: {exc}")
        if reasons:
            exclusions.append({"image": filename, "reasons": reasons})
        else:
            samples.append((path, CANONICAL_MAP.get(raw_label, raw_label)))
    for image_id in sorted(set(by_image) - set(images)):
        exclusions.append({"image": f"image_id:{image_id}", "reasons": ["annotation references unknown image id"]})

    tf = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
    ])
    loader = DataLoader(ManifestSamples(samples, tf), batch_size=batch_size, shuffle=False, num_workers=0)
    model.eval()
    truths, predictions, confidences, topk_names, filenames = [], [], [], [], []
    with torch.no_grad():
        for tensors, labels, names in loader:
            probs = torch.softmax(model(tensors.to(device)), dim=1).cpu()
            k = min(3, probs.shape[1])
            values, indices = probs.topk(k, dim=1)
            for row, truth in enumerate(labels):
                truths.append(truth)
                predictions.append(idx_to_name := next((name for name, idx in class_map.items() if idx == indices[row, 0].item()), f"class_{indices[row, 0].item()}"))
                confidences.append(float(values[row, 0]))
                topk_names.append([next((name for name, idx in class_map.items() if idx == item.item()), f"class_{item.item()}") for item in indices[row]])
                filenames.append(names[row])

    total_manifest = len(coco.get("images", []))
    total = len(samples)
    correct = sum(pred == truth for pred, truth in zip(predictions, truths))
    topk_correct = sum(truth in names for truth, names in zip(truths, topk_names))
    true_classes = sorted(set(truths))
    predicted_classes = sorted(set(predictions))
    per_class = {}
    for label in true_classes:
        tp = sum(pred == label and truth == label for pred, truth in zip(predictions, truths))
        support = sum(truth == label for truth in truths)
        predicted_count = sum(pred == label for pred in predictions)
        precision = tp / predicted_count if predicted_count else 0.0
        recall = tp / support if support else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[label] = {"support": support, "correct": tp, "precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4)}
    confusion = {}
    for truth, pred in zip(truths, predictions):
        confusion.setdefault(truth, {})[pred] = confusion.setdefault(truth, {}).get(pred, 0) + 1
    confidence_analysis = {}
    for threshold in (0.5, 0.7, 0.9):
        chosen = [(truth, pred) for truth, pred, conf in zip(truths, predictions, confidences) if conf >= threshold]
        confidence_analysis[str(threshold)] = {
            "selected": len(chosen),
            "coverage": round(len(chosen) / total_manifest, 4) if total_manifest else 0.0,
            "accuracy": round(sum(truth == pred for truth, pred in chosen) / len(chosen), 4) if chosen else None,
        }
    errors = [
        {"image": filename, "true_class": truth, "pred_class": pred, "confidence": round(conf, 4)}
        for filename, truth, pred, conf in zip(filenames, truths, predictions, confidences)
        if truth != pred
    ][:20]
    return {
        "total": total_manifest,
        "evaluated": total,
        "excluded": len(exclusions),
        "exclusions": exclusions,
        "correct": correct,
        "accuracy": round(correct / total_manifest, 4) if total_manifest else 0.0,
        "top3_accuracy": round(topk_correct / total_manifest, 4) if total_manifest else 0.0,
        "macro_f1": round(sum(metrics["f1"] for metrics in per_class.values()) / len(per_class), 4) if per_class else 0.0,
        "balanced_accuracy": round(sum(metrics["recall"] for metrics in per_class.values()) / len(per_class), 4) if per_class else 0.0,
        "class_map_coverage": round(len(set(truths) & set(class_map)) / len(set(truths)), 4) if truths else 0.0,
        "per_class": per_class,
        "confusion_matrix": confusion,
        "confidence_threshold_analysis": confidence_analysis,
        "errors": errors,
    }


def main(args) -> None:
    CKPT_DIR = ROOT / "backend" / "models" / "chemvision_classifier"
    ckpt_path     = CKPT_DIR / "best_model.pth"
    class_map_path = CKPT_DIR / "class_map.json"

    if not ckpt_path.exists():
        print(f"ERROR: No trained checkpoint found at {ckpt_path}")
        print("Run: python ml/train.py   to train the model first.")
        sys.exit(1)

    print(f"Loading model from {ckpt_path}")
    model, idx_to_class, class_to_idx = load_model_for_inference(
        ckpt_path, class_map_path, args.device
    )

    DATASET_ROOT = ROOT / "CHEMVISION.v7i.coco"
    split_dir = DATASET_ROOT / args.split
    print(f"Evaluating complete '{args.split}' manifest (unseen labels count as incorrect)")
    report = evaluate_complete_manifest(model, split_dir, class_to_idx, args.device, args.batch_size)

    print(f"\n=== Results on '{args.split}' split ===")
    print(f"  Coverage     : {report['evaluated']}/{report['total']} evaluated; {report['excluded']} excluded")
    print(f"  Accuracy     : {report['accuracy']:.3f}  ({report['correct']}/{report['total']})")
    print(f"  Top-3 Acc    : {report['top3_accuracy']:.3f}")
    print(f"  Macro-F1     : {report['macro_f1']:.3f}")
    print(f"  Balanced acc : {report['balanced_accuracy']:.3f}")
    print(f"  Label coverage: {report['class_map_coverage']:.3f}")
    print()
    print("  Per-class performance (sorted by F1):")
    for name, stats in sorted(report["per_class"].items(), key=lambda x: -x[1]["f1"]):
        print(f"    {name:<45} P={stats['precision']:.2f} R={stats['recall']:.2f} "
              f"F1={stats['f1']:.2f}  support={stats['support']}")

    if report["errors"]:
        print("\n  Representative errors:")
        for err in report["errors"]:
            print(f"    TRUE={err['true_class']:<40} PRED={err['pred_class']:<40} "
                  f"conf={err['confidence']:.2f}")

    out = ROOT / "docs" / ("complete_test_evaluation.json" if args.split == "test" else f"eval_{args.split}.json")
    with open(out, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nReport saved: {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--split",      default="test", choices=["train", "valid", "test"])
    parser.add_argument("--device",     default="cpu",  choices=["cpu", "cuda"])
    parser.add_argument("--batch_size", default=8, type=int)
    main(parser.parse_args())
