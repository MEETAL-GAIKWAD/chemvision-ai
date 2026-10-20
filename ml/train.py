"""
ChemVision AI — Training Script (EfficientNet-B0 reaction type classifier)
Usage:  cd backend && .venv/Scripts/python ../ml/train.py --epochs 40
"""
from __future__ import annotations
import argparse, json, random, sys, time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torchvision import transforms

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ml"))
from dataset import ReactionDataset, build_class_map
from model   import build_model, count_params, freeze_backbone, unfreeze_all

MEAN = [0.485, 0.456, 0.406]
STD  = [0.229, 0.224, 0.225]

def set_seed(s=42):
    random.seed(s); np.random.seed(s); torch.manual_seed(s)

def get_transforms(sz=224):
    tr = transforms.Compose([
        transforms.Resize((sz+32, sz+32)), transforms.RandomCrop(sz),
        transforms.RandomHorizontalFlip(0.5), transforms.RandomVerticalFlip(0.3),
        transforms.RandomRotation(15),
        transforms.ColorJitter(brightness=0.25, contrast=0.25),
        transforms.ToTensor(), transforms.Normalize(MEAN, STD),
    ])
    vl = transforms.Compose([
        transforms.Resize((sz, sz)), transforms.ToTensor(), transforms.Normalize(MEAN, STD)
    ])
    return tr, vl

def run_epoch(model, loader, crit, opt, device, phase="train"):
    is_train = phase == "train"
    model.train() if is_train else model.eval()
    tl = correct = total = 0
    predictions, targets = [], []
    ctx = torch.enable_grad() if is_train else torch.no_grad()
    with ctx:
        for imgs, lbls in loader:
            imgs, lbls = imgs.to(device), lbls.to(device)
            logits = model(imgs); loss = crit(logits, lbls)
            if is_train:
                opt.zero_grad(); loss.backward(); opt.step()
            tl      += loss.item() * imgs.size(0)
            correct += (logits.argmax(1) == lbls).sum().item()
            total   += imgs.size(0)
            predictions.extend(logits.argmax(1).detach().cpu().tolist())
            targets.extend(lbls.detach().cpu().tolist())
    if not total:
        raise ValueError(f"The {phase} loader contains no samples")
    supports = [sum(target == cls for target in targets) for cls in range(logits.shape[1])]
    present = [i for i, support in enumerate(supports) if support]
    recalls, f1s = [], []
    for cls, support in enumerate(supports):
        tp = sum(pred == cls and target == cls for pred, target in zip(predictions, targets))
        predicted = sum(pred == cls for pred in predictions)
        recall = tp / support if support else 0.0
        precision = tp / predicted if predicted else 0.0
        recalls.append(recall)
        f1s.append(2 * precision * recall / (precision + recall) if precision + recall else 0.0)
    macro_f1 = sum(f1s[i] for i in present) / len(present)
    balanced_accuracy = sum(recalls[i] for i in present) / len(present)
    return tl / total, correct / total, macro_f1, balanced_accuracy

def save_ckpt(model, opt, ep, val_acc, val_macro_f1, c2i, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"epoch": ep, "val_acc": val_acc, "val_macro_f1": val_macro_f1,
                "model_state": model.state_dict(),
                "optimizer_state": opt.state_dict(),
                "num_classes": len(c2i)}, path)

def train(args):
    if args.epochs < 2 or args.patience < 1:
        raise ValueError("--epochs must be at least 2 and --patience must be positive")
    set_seed(args.seed)
    DS   = ROOT / "CHEMVISION.v7i.coco"
    CDIR = ROOT / "backend" / "models" / "chemvision_classifier"
    CDIR.mkdir(parents=True, exist_ok=True)
    CKPT = CDIR / "best_model.pth"

    ann = DS / "train" / "_annotations.coco.json"
    if not ann.exists():
        print(f"ERROR: dataset not found at {DS}"); sys.exit(1)

    class_names, c2i, i2c = build_class_map(ann)
    nc = len(class_names)
    print(f"Classes: {nc}")
    tr_tf, vl_tf = get_transforms(args.image_size)
    tr_ds = ReactionDataset(DS/"train", ann, c2i, tr_tf)
    vl_ds = ReactionDataset(DS/"valid", DS/"valid"/"_annotations.coco.json", c2i, vl_tf)
    te_ds = ReactionDataset(DS/"test",  DS/"test" /"_annotations.coco.json", c2i, vl_tf)
    print(f"Train:{len(tr_ds)} Valid:{len(vl_ds)} Test:{len(te_ds)}")

    with open(CDIR / "class_map.json", "w") as f:
        json.dump(c2i, f, indent=2, ensure_ascii=False)

    tr_ld = DataLoader(tr_ds, batch_size=args.batch_size, shuffle=True,  num_workers=0)
    vl_ld = DataLoader(vl_ds, batch_size=args.batch_size, shuffle=False, num_workers=0)

    dev = args.device
    if dev == "cuda" and not torch.cuda.is_available():
        dev = "cpu"

    model = build_model(nc, pretrained=True, dropout=0.3)
    model.to(dev)
    crit  = nn.CrossEntropyLoss(label_smoothing=0.1)
    total, _ = count_params(model)
    print(f"EfficientNet-B0 | {total:,} params | {dev}")

    P1 = min(10, max(1, args.epochs // 4))
    P2 = args.epochs - P1
    log = []; best_va = -1.0; pat = 0

    # Phase 1 — frozen backbone
    print(f"\n[Phase 1] frozen backbone {P1} epochs")
    freeze_backbone(model)
    opt   = torch.optim.Adam(filter(lambda p: p.requires_grad, model.parameters()), lr=args.lr, weight_decay=args.weight_decay)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=P1)
    for ep in range(1, P1+1):
        t0 = time.time()
        tl, ta, _, _ = run_epoch(model, tr_ld, crit, opt, dev, "train")
        vl, va, vmf1, vba = run_epoch(model, vl_ld, crit, None, dev, "val")
        sched.step()
        print(f"  E{ep:2d}/{P1} loss={tl:.4f} train_acc={ta:.3f} val_acc={va:.3f} val_macro_f1={vmf1:.3f} val_bal_acc={vba:.3f} {time.time()-t0:.1f}s")
        log.append({"epoch":ep,"phase":1,"train_loss":round(tl,4),"train_acc":round(ta,4),"val_acc":round(va,4),"val_macro_f1":round(vmf1,4),"val_balanced_accuracy":round(vba,4)})
        if vmf1 > best_va:
            best_va = vmf1
            save_ckpt(model, opt, ep, va, vmf1, c2i, CKPT)
            print(f"    saved best validation macro-F1={vmf1:.3f}")

    # Phase 2 — full fine-tune
    print(f"\n[Phase 2] full fine-tune {P2} epochs")
    unfreeze_all(model)
    opt   = torch.optim.Adam(model.parameters(), lr=args.lr*0.1, weight_decay=args.weight_decay)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=P2)
    for ep_off in range(1, P2+1):
        ep = P1 + ep_off
        t0 = time.time()
        tl, ta, _, _ = run_epoch(model, tr_ld, crit, opt, dev, "train")
        vl, va, vmf1, vba = run_epoch(model, vl_ld, crit, None, dev, "val")
        sched.step()
        print(f"  E{ep:2d}/{args.epochs} loss={tl:.4f} train_acc={ta:.3f} val_acc={va:.3f} val_macro_f1={vmf1:.3f} val_bal_acc={vba:.3f} {time.time()-t0:.1f}s")
        log.append({"epoch":ep,"phase":2,"train_loss":round(tl,4),"train_acc":round(ta,4),"val_acc":round(va,4),"val_macro_f1":round(vmf1,4),"val_balanced_accuracy":round(vba,4)})
        if vmf1 > best_va:
            best_va = vmf1; pat = 0
            save_ckpt(model, opt, ep, va, vmf1, c2i, CKPT)
            print(f"    saved best validation macro-F1={vmf1:.3f}")
        else:
            pat += 1
        if pat >= args.patience:
            print(f"  Early stop (patience={args.patience})"); break

    if not CKPT.exists():
        raise RuntimeError("Training ended without a validation-selected checkpoint")

    with open(CDIR/"training_log.json","w") as f:
        json.dump({"config":vars(args),"selection_metric":"validation_macro_f1","log":log,"best_val_macro_f1":round(best_va,4)},f,indent=2)
    print(f"\nCheckpoint: {CKPT}")

    # Test evaluation
    print("\n[Test set evaluation]")
    from model import load_model_for_inference
    bm, i2c2, _ = load_model_for_inference(CKPT, CDIR/"class_map.json", dev)
    from evaluate import evaluate_model
    rep = evaluate_model(bm, te_ds, i2c2, dev, args.batch_size)
    with open(CDIR/"eval_report.json","w") as f:
        json.dump(rep, f, indent=2)
    print(f"Test accuracy: {rep['accuracy']:.3f} ({rep['correct']}/{rep['total']})")
    print(f"Top-3 accuracy: {rep['top3_accuracy']:.3f}")

    print(f"\n{'='*50}")
    print(f"DONE  best_val_macro_f1={best_va:.3f}  test_acc={rep['accuracy']:.3f}")
    print(f"{'='*50}")

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--epochs",      type=int,   default=40)
    p.add_argument("--batch_size",  type=int,   default=8)
    p.add_argument("--lr",          type=float, default=5e-4)
    p.add_argument("--weight_decay",type=float, default=1e-4)
    p.add_argument("--image_size",  type=int,   default=224)
    p.add_argument("--patience",    type=int,   default=12)
    p.add_argument("--seed",        type=int,   default=42)
    p.add_argument("--device",      type=str,   default="cpu")
    train(p.parse_args())
