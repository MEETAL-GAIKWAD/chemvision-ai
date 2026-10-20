"""Validate all COCO samples and report split/label coverage without training."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from dataset import CANONICAL_MAP

ROOT = Path(__file__).resolve().parent.parent


def audit_split(root: Path, split: str) -> dict:
    folder = root / split
    annotation_file = folder / "_annotations.coco.json"
    data = json.loads(annotation_file.read_text(encoding="utf-8"))
    categories = {item["id"]: item["name"] for item in data.get("categories", [])}
    images = {item["id"]: item for item in data.get("images", [])}
    by_image: dict[int, list[dict]] = defaultdict(list)
    for ann in data.get("annotations", []):
        by_image[ann.get("image_id")].append(ann)

    labels: Counter[str] = Counter()
    raw_labels: Counter[str] = Counter()
    hashes: dict[str, list[str]] = defaultdict(list)
    issues: list[dict[str, str]] = []
    sample_records = []
    for image_id, image_info in images.items():
        filename = image_info.get("file_name", "")
        path = folder / filename
        anns = by_image.get(image_id, [])
        reasons = []
        raw = ""
        canonical = ""
        if len(anns) != 1:
            reasons.append(f"expected exactly one annotation, found {len(anns)}")
        else:
            category_id = anns[0].get("category_id")
            raw = categories.get(category_id, "")
            if not raw:
                reasons.append(f"unknown category_id {category_id}")
            else:
                canonical = CANONICAL_MAP.get(raw, raw)
                raw_labels[raw] += 1
                labels[canonical] += 1
        if not path.is_file():
            reasons.append("image file missing")
        else:
            try:
                with Image.open(path) as im:
                    im.verify()
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                hashes[digest].append(filename)
            except (OSError, UnidentifiedImageError) as exc:
                reasons.append(f"invalid image: {exc}")
        record = {"image": filename, "label": canonical or None, "status": "excluded" if reasons else "included"}
        record["source_group"] = source_group(filename)
        if path.is_file() and not reasons:
            record["sha256"] = digest
        if reasons:
            record["exclusion_reasons"] = reasons
            issues.append({"image": filename, "reasons": "; ".join(reasons)})
        sample_records.append(record)

    unreferenced_annotations = sorted(set(by_image) - set(images))
    duplicate_image_ids = [image_id for image_id, anns in by_image.items() if len(anns) > 1]
    return {
        "manifest_images": len(images),
        "annotations": len(data.get("annotations", [])),
        "included_samples": sum(record["status"] == "included" for record in sample_records),
        "excluded_samples": len(issues),
        "raw_label_count": len(raw_labels),
        "canonical_label_count": len(labels),
        "raw_class_counts": dict(sorted(raw_labels.items())),
        "canonical_class_counts": dict(sorted(labels.items())),
        "invalid_or_missing": issues,
        "duplicate_image_ids": duplicate_image_ids,
        "annotations_with_unknown_image_id": unreferenced_annotations,
        "exact_duplicate_groups": [group for group in hashes.values() if len(group) > 1],
        "source_groups": sorted({source_group(image.get("file_name", "")) for image in images.values()}),
        "samples": sample_records,
    }


def source_group(filename: str) -> str:
    """Group image crops by the original source document/page stem."""
    stem = filename.split(".rf.", 1)[0]
    if "-pdf_page_" in stem:
        return stem.split("-pdf_page_", 1)[0]
    if "_page-" in stem:
        return stem.split("_page-", 1)[0]
    return stem


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=ROOT / "CHEMVISION.v7i.coco")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/dataset_report.json")
    args = parser.parse_args()

    splits = {split: audit_split(args.dataset, split) for split in ("train", "valid", "test")}
    train_labels = set(splits["train"]["canonical_class_counts"])
    for split in ("valid", "test"):
        counts = splits[split]["canonical_class_counts"]
        unseen = sorted(set(counts) - train_labels)
        splits[split]["unseen_class_counts"] = {label: counts[label] for label in unseen}
        splits[split]["samples_with_unseen_classes"] = sum(counts[label] for label in unseen)

    source_sets = {
        split: {record["source_group"] for record in data["samples"] if record["status"] == "included"}
        for split, data in splits.items()
    }
    hash_to_splits: dict[str, set[str]] = defaultdict(set)
    hash_to_names: dict[str, list[str]] = defaultdict(list)
    for split, data in splits.items():
        for record in data["samples"]:
            if record["status"] != "included":
                continue
            hash_to_splits[record["sha256"]].add(split)
            hash_to_names[record["sha256"]].append(record["image"])

    all_samples = sum(split["manifest_images"] for split in splits.values())
    accounted = sum(split["included_samples"] + split["excluded_samples"] for split in splits.values())
    report = {
        "dataset": str(args.dataset),
        "source": "Roboflow Universe CHEMVISION.v7i.coco (provided dataset README; CC BY 4.0)",
        "all_samples_accounted_for": all_samples == accounted,
        "total_manifest_images": all_samples,
        "total_included": sum(split["included_samples"] for split in splits.values()),
        "total_excluded": sum(split["excluded_samples"] for split in splits.values()),
        "split_label_overlap_with_train": {
            split: sorted(train_labels & set(splits[split]["canonical_class_counts"]))
            for split in ("valid", "test")
        },
        "source_group_overlap_between_splits": {
            f"{left}__{right}": sorted(source_sets[left] & source_sets[right])
            for index, left in enumerate(("train", "valid", "test"))
            for right in ("train", "valid", "test")[index + 1:]
        },
        "exact_duplicate_groups_across_splits": [
            hash_to_names[digest] for digest, split_names in hash_to_splits.items()
            if len(split_names) > 1
        ],
        "splits": splits,
        "interpretation": (
            "This dataset cannot support a valid held-out classifier evaluation as arranged: "
            "validation and test contain classes missing from training. Do not report a metric "
            "on only the overlapping subset as full-split performance."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("all_samples_accounted_for", "total_manifest_images", "total_included", "total_excluded", "split_label_overlap_with_train")}, indent=2))
    print(f"Report written to {args.output}")


if __name__ == "__main__":
    main()
