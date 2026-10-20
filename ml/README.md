# ChemVision AI — ML Model

## Architecture
**EfficientNet-B0** (transfer learning, ImageNet pretrained)
- Task: Reaction Type Classification
- Input: Chemistry image (224×224 RGB)
- Output: One of 32 canonical reaction class names
- Parameters: ~4M (EfficientNet-B0)

## Dataset: CHEMVISION.v7i.coco
- Source: Roboflow (CC BY 4.0)
- Format: COCO JSON object-detection annotations (one annotation per image in the supplied split manifests)
- Supplied totals: 221 images → 153 train / 14 valid / 54 test
- Raw category names: 89; classifier class map: 32 classes
- The saved evaluation report covers 21 test examples, not all 54 supplied test images.
- This dataset labels reaction classes/regions, not atom-level structures or SMILES.

## Classes (32 canonical)
Aldol Condensation, Cannizzaro Reaction, Carbylamine Reaction,
Clemmensen Reduction, Coupling Reaction, Decarboxylation Reaction,
Diazotization Reaction, Esterification Reaction, Etard Reaction,
Finkelstein Reaction, Fittig Reaction, Friedel-Crafts Acylation,
Friedel-Crafts Alkylation, Fries Rearrangement, Gabriel Synthesis,
Gattermann Reaction, Gattermann-Koch Reaction, Hell-Volhard-Zelinsky Reaction,
Hofmann Bromamide Reaction, Hunsdiecker Reaction, Iodoform Reaction,
Kolbe-Schmitt Reaction, Liebermann-Nitroso Reaction, Mendius Reaction,
Perkin Reaction, Reimer-Tiemann Reaction, Rosenmund Reaction,
Sandmeyer Reaction, Swarts Reaction, Williamson Ether Synthesis,
Wolff-Kishner Reduction, Wurtz-Fittig Reaction

## Training Results
| Metric | Value |
|--------|-------|
| Saved checkpoint evaluation set | 21 images |
| Top-1 accuracy | 4.76% (1/21) |
| Top-3 accuracy | 19.05% (4/21) |
| Training-log best validation accuracy | 0.0% |

## Known Limitations
- Dataset is very small (153 train samples across 32 classes = ~5 per class)
- Many classes have only 3 samples → not enough for reliable classification
- Training accuracy improves but test accuracy remains low (expected with this dataset size)
- The model is not reliable enough to identify reactions or disambiguate OCR/filename matches; treat its output as an experimental suggestion only.
- **For production accuracy, the dataset needs at least 50-100 samples per class**

## How to Train
```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python ..\ml\train.py --epochs 40 --device cpu
# With GPU (if available):
python ..\ml\train.py --epochs 100 --device cuda
```

## How to Evaluate
```powershell
cd backend
.\.venv\Scripts\python.exe ..\ml\evaluate.py --split test
```

## Google Colab Training (recommended for better results)
For better results, train on Colab with GPU:
1. Upload the `CHEMVISION.v7i.coco/` folder to Google Drive
2. Upload `ml/` folder to Colab
3. Run: `python train.py --epochs 100 --device cuda`
4. Download `best_model.pth` → place in `backend/models/chemvision_classifier/`

## Integration
The model is integrated into `backend/app/services/ml_classifier.py`.
It is called automatically in `reaction_processor.py` during image upload.
Falls back gracefully to OCR+filename matching when unavailable.
