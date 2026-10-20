# ChemVision AI ML and dataset audit

Audit date: 2026-10-20

## Scope and evidence

This audit inspected the COCO manifests and image files in `CHEMVISION.v7i.coco`, the EfficientNet-B0 training and evaluation scripts, inference transforms, the saved class map, and the saved checkpoint/report. The dataset audit was run with `backend/.venv` using `ml/audit_dataset.py`. No model was retrained.

## Model status

**Experimental; not suitable for reaction identification.** The saved classifier is a 32-output EfficientNet-B0 that predicts a reaction category. It cannot transcribe arbitrary equations, identify structures, infer products, or validate reaction chemistry. Inference and training both resize to 224×224 and normalize with ImageNet mean/std, but this consistent preprocessing does not remedy dataset/split defects.

The saved legacy `eval_report.json` reports 1/21 top-1 (4.76%) and 4/21 top-3 (19.05%). The complete test manifest has 54 images. The prior evaluation silently filtered labels absent from the training class map; only the 21 examples whose canonical labels overlapped the training set were scored. Thus 21 was not complete held-out test coverage.

I updated the evaluator to cover the full manifest, count unseen classes as incorrect, report exclusions, class-map coverage, macro-F1, balanced accuracy, a confusion matrix, per-class metrics, and confidence threshold coverage. Running it on the existing checkpoint evaluated all 54 images with 0 exclusions: top-1 **1/54 (1.85%)**, top-3 **4/54 (7.41%)**, macro-F1 **0.009**, balanced accuracy **0.021**, and only **34.0%** of canonical test labels present in its class map. The weak performance and invalid class coverage mean the model remains experimental. Per-class results and errors are saved in [complete_test_evaluation.json](complete_test_evaluation.json). This is an audit evaluation only; it was not used for model selection.

The bundled checkpoint is 49,051,256 bytes. It is loadable only in an environment with compatible PyTorch/torchvision. The current environment has CPU-only PyTorch 2.14.0 and torchvision 0.29.0 in `backend/.venv`; CUDA is unavailable. The saved result is not evidence that the checkpoint can generalize to the manifest labels.

## Dataset findings

Source stated by the bundled Roboflow README: [CHEMVISION on Roboflow Universe](https://universe.roboflow.com/resqpetai/chemvision). The README states CC BY 4.0 and attributes the dataset to a Roboflow user. The local copy is COCO JSON with one full-image category annotation per image, not equation transcription or atom/bond graph ground truth.

| Split | Images | Valid image/annotation records | Canonical labels in split | Classes absent from train | Samples with absent classes |
|---|---:|---:|---:|---:|---:|
| Train | 153 | 153 | 32 | 0 | 0 |
| Validation | 14 | 14 | 7 | 4 | 8 |
| Test | 54 | 54 | 47 | 31 | 33 |

All 221 manifest images decoded successfully; all 221 have exactly one annotation and an existing image file. There are 89 raw category names across the manifests. The canonical alias map does not normalize every spelling variant; the class counts above reflect only the explicit `CANONICAL_MAP` entries. The test split maps to 47 canonical labels; 31 labels (33 images) are absent from training. Filenames identify source-document groups shared between splits, so source leakage is plausible; exact duplicate hashes are separately reported. See [dataset_report.json](dataset_report.json) for raw and canonical class counts, every sample, source overlap, and validation/exclusion records.

The splits are not suitable for model selection or an unbiased complete test. Validation has only 6 examples with train-seen labels. The test set has exactly 21 examples whose labels overlap training, matching the historical report's sample count; the remaining 33 were silently excluded by the old dataset loader. Filenames show the source document `pdf1` occurs in train, validation, and test; exact image hashes show no cross-split duplicates, but the document-level source is shared. Rebuild a source-grouped split from a licensed, reviewed source collection, and hold a final test group aside before model selection.

### Independently checked dataset statistics

Run:

```powershell
cd backend
.\.venv\Scripts\python.exe ..\ml\audit_dataset.py
```

The command writes `docs/dataset_report.json`. It records every manifest image as included or excluded with exact reasons. No exclusions occurred in this audit. The training dataset loader now raises on missing files, corrupt images, unknown labels, duplicate IDs, labels outside the training class map, or multiple/no class annotations instead of silently dropping examples.

## Root causes and limitations

1. **Class-disjoint splits:** most validation and test labels do not occur in training. The train-derived class map has 39 classes while the manifests span 89 raw labels.
2. **Silent sample filtering:** `ReactionDataset` used to skip missing files and labels outside the map. This made evaluation appear complete while scoring only an overlap subset.
3. **Tiny support:** most training classes have 3–6 examples; validation has 14 total; test has many singleton classes. Metrics would be extremely unstable even after correcting labels/splits.
4. **Training checkpoint selection bug:** the old script could save on training loss, later validation accuracy, and then unconditionally overwrite the selected checkpoint with the final epoch. This did not preserve a best-validation checkpoint.
5. **Ontology ambiguity:** category typos and aliases need review. Similar but distinct labels must not be merged without dataset-owner confirmation.
6. **Task mismatch:** reaction-type labels do not supervise equation OCR, molecular graph recognition, product generation, or 3D structure accuracy.

The model was **not retrained**. Training is blocked by invalid split coverage; running the current trainer after the loader change will fail before fitting. No new accuracy is claimed. Establish a class-balanced, source-grouped, licensed dataset with sufficient examples per class, then define target thresholds before training. Suggested minimum release gate (to be preregistered and revised with domain owners): macro-F1 ≥0.80 and balanced accuracy ≥0.80 on a representative untouched source-grouped test set, plus per-class recall ≥0.70 and a calibration/abstention review. This dataset cannot validate those targets.

## Other recognition models and data resources checked

| Resource | Actual task / interface | License and size evidence | Decision |
|---|---|---|---|
| [MolScribe](https://github.com/thomas0809/MolScribe) | Molecular diagram image to SMILES plus atom/bond coordinates and confidence; project documents CPU inference. | GitHub project and Hugging Face model card state MIT. Main checkpoint is 1.13 GB; model repository lists 6.49 GB total. | Strong candidate for a separately benchmarked molecular structure path. Not downloaded/integrated because of checkpoint size, incompatible task scope for complete reaction equations, and no labeled structure-image set in this project. |
| [DECIMER](https://github.com/Kohulan/DECIMER-Image_Transformer) | Chemical structure image to SMILES via `DECIMER.predict_SMILES(image_path)`. | Repository declares MIT; documentation says `pip install decimer`. Current README shows a Python 3.10 environment; checkpoint size was not established in this audit. | Candidate for isolated comparison against MolScribe on labeled molecular diagrams. Not integrated or benchmarked; keep existing EasyOCR as the OCR baseline. |
| [USPTO-50K raw on Figshare](https://figshare.com/articles/dataset/USPTO-50K_raw_/25459573) | About 50K reaction records (reaction data, not input reaction images). | Figshare page lists 19.02 MB and MIT; metadata says sourced from GLN. | Could help chemistry/reaction classification research if labels and provenance are checked. It cannot evaluate OCR or diagram understanding without paired images. Not downloaded. |
| Bundled CHEMVISION Roboflow data | 221 cropped/classified reaction images. | Local README states CC BY 4.0. | Available locally, but split label coverage is invalid and examples are too sparse for reliable generalization. |

The MolScribe project also documents that its published training setup uses large datasets, a one-GPU evaluation configuration, and four A100 GPUs for roughly a day of training. These are not necessary for CPU inference, but demonstrate why replacing the current classifier without measuring actual deployment needs would be premature. DECIMER and MolScribe are structure recognizers, not equation transcription or reaction product generators. None of the candidates was benchmarked on this application's expected image types. Equation OCR, reaction identification, and molecular graph recognition require distinct labeled test sets and task-specific metrics (exact equation transcription/parsing; graph atoms, connectivity, bonds, and stereochemistry).

## Required next data work

- Obtain a licensed dataset whose usage and redistribution terms are recorded per source.
- Have chemistry reviewers verify each label and aliases; retain source document and page/group IDs.
- Deduplicate by exact hash and near-duplicate visual/source grouping before splitting.
- Use train/validation/test groups with all target classes represented, enough validation/test support per class, and no source overlap.
- Record every corrupt or excluded sample with a reason; never tune on the final test group.
- Benchmark OCR, reaction classification, molecular structure recognition, and chemistry parsing separately.
