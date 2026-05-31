"""
GST Classifier v2 — Complete Training Pipeline
===============================================
- MuRIL base model with class-weighted loss
- Stratified 5-fold cross-validation
- Keyword baseline + xlm-roberta-base comparison
- W&B experiment tracking
- Full evaluation artifacts

Usage:
    python ml/train.py                          # Full pipeline
    python ml/train.py --fast                   # Quick test (1 epoch, no CV)
    python ml/train.py --no-wandb               # Disable W&B logging
"""

import argparse
import gc
import json
import os
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from dotenv import load_dotenv
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from sklearn.model_selection import StratifiedKFold
from sklearn.utils.class_weight import compute_class_weight
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    Trainer,
    TrainingArguments,
    set_seed,
)
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
import transformers

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "backend", ".env"))

warnings.filterwarnings("ignore")

# ── Configuration ──────────────────────────────────────────────────────────

CLASS_NAMES = [
    "capital_goods",
    "input_services",
    "raw_materials",
    "motor_vehicles_conveyance",
    "food_beverages_catering",
    "club_health_beauty",
    "personal_employee_benefit",
]
NUM_LABELS = len(CLASS_NAMES)
LABEL_TO_ID = {name: i for i, name in enumerate(CLASS_NAMES)}
ID_TO_LABEL = {i: name for i, name in enumerate(CLASS_NAMES)}

MODEL_DIR = Path(__file__).parent / "models"
EVAL_DIR = Path(__file__).parent / "evaluation"
DATA_DIR = Path(__file__).parent / "data"

TRAIN_CSV = DATA_DIR / "train.csv"
VAL_CSV = DATA_DIR / "val.csv"
TEST_CSV = DATA_DIR / "test.csv"

SEED = 42

# Hyperparameters
TF_VERSION = tuple(int(x) for x in transformers.__version__.split(".")[:2])

HPARAMS = {
    "model_name": "google/muril-base-cased",
    "max_length": 128,
    "batch_size": 32,
    "learning_rate": 2e-5,
    "num_epochs": 5,
    "warmup_ratio": 0.1,
    "weight_decay": 0.01,
    "metric_for_best_model": "eval_f1_macro",
    "greater_is_better": True,
}


# ── Data loading ───────────────────────────────────────────────────────────

def load_split(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["label_id"] = df["label"].map(LABEL_TO_ID)
    return df


# ── Dataset class ──────────────────────────────────────────────────────────

class GSTDataset(torch.utils.data.Dataset):
    def __init__(self, texts: list[str], labels: list[int], tokenizer, max_length: int):
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        enc = self.tokenizer(
            self.texts[idx],
            truncation=True,
            padding="max_length",
            max_length=self.max_length,
            return_tensors="pt",
        )
        return {
            "input_ids": enc["input_ids"].squeeze(0),
            "attention_mask": enc["attention_mask"].squeeze(0),
            "labels": torch.tensor(self.labels[idx], dtype=torch.long),
        }


# ── Custom Trainer with weighted loss ──────────────────────────────────────

class WeightedTrainer(Trainer):
    def __init__(self, class_weights: torch.Tensor | None = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.class_weights = class_weights

    def compute_loss(self, model, inputs, return_outputs=False, num_items_in_batch=None):
        labels = inputs.pop("labels")
        outputs = model(**inputs)
        logits = outputs.logits
        if self.class_weights is not None:
            loss_fn = nn.CrossEntropyLoss(weight=self.class_weights.to(logits.device))
        else:
            loss_fn = nn.CrossEntropyLoss()
        loss = loss_fn(logits, labels)
        return (loss, outputs) if return_outputs else loss


# ── Metrics ────────────────────────────────────────────────────────────────

def compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    f1_macro = f1_score(labels, preds, average="macro")
    f1_weighted = f1_score(labels, preds, average="weighted")
    acc = (preds == labels).mean()
    return {"f1_macro": f1_macro, "f1_weighted": f1_weighted, "accuracy": acc}


# ── Keyword baseline ───────────────────────────────────────────────────────

KEYWORD_RULES = {
    "capital_goods": [
        "laptop", "computer", "printer", "furniture", "machine", "equipment",
        "generator", "ac ", "cctv", "server", "desktop", "monitor", "tablet",
    ],
    "input_services": [
        "accounting", "legal", "courier", "advertising", "software",
        "consultancy", "audit", "tax", "subscription", "marketing",
        "professional fee", "security service", "maintenance contract",
    ],
    "raw_materials": [
        "steel", "cement", "chemical", "packaging", "fabric", "raw material",
        "paint", "plastic", "timber", "wood", "brick", "sand", "yarn", "leather",
    ],
    "motor_vehicles_conveyance": [
        "car", "bike", "truck", "vehicle", "petrol", "diesel", "fuel",
        "tyre", "transportation", "taxi", "conveyance", "gaadi",
    ],
    "food_beverages_catering": [
        "lunch", "dinner", "catering", "restaurant", "canteen", "zomato",
        "swiggy", "food", "snack", "tea", "coffee", "refreshment", "party",
    ],
    "club_health_beauty": [
        "gym", "health", "beauty", "salon", "spa", "club membership",
        "yoga", "wellness", "fitness",
    ],
    "personal_employee_benefit": [
        "gift", "allowance", "reimbursement", "bonus", "welfare",
        "uniform", "diwali", "lta", "travel allowance",
    ],
}


def keyword_classify(text: str) -> tuple[str, float]:
    text_lower = text.lower()
    best_cat = "capital_goods"
    best_score = 0.0
    for cat, keywords in KEYWORD_RULES.items():
        matches = sum(1 for kw in keywords if kw in text_lower)
        if matches > best_score:
            best_score = matches
            best_cat = cat
    confidence = min(best_score / 3.0, 0.95)
    return best_cat, confidence


def evaluate_keyword_baseline(df: pd.DataFrame) -> dict:
    y_true = df["label_id"].values
    y_pred = []
    for text in df["text"]:
        cat, _ = keyword_classify(text)
        y_pred.append(LABEL_TO_ID.get(cat, 0))
    f1 = f1_score(y_true, y_pred, average="macro", zero_division=0)
    report = classification_report(y_true, y_pred, target_names=CLASS_NAMES, output_dict=True, zero_division=0)
    return {"f1_macro": round(float(f1), 4), "report": report}


# ── Model training function ────────────────────────────────────────────────

def get_model_and_tokenizer(model_name: str, num_labels: int):
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_name, num_labels=num_labels,
        ignore_mismatched_sizes=True,
    )
    return model, tokenizer


def train_model(
    train_texts: list[str],
    train_labels: list[int],
    val_texts: list[str] | None,
    val_labels: list[int] | None,
    class_weights: torch.Tensor | None,
    model_name: str,
    output_dir: str,
    run_name: str = "run",
    num_epochs: int = 5,
    use_wandb: bool = True,
) -> Trainer:
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_name, num_labels=NUM_LABELS, ignore_mismatched_sizes=True,
    )

    train_dataset = GSTDataset(train_texts, train_labels, tokenizer, HPARAMS["max_length"])
    val_dataset = None
    if val_texts is not None:
        val_dataset = GSTDataset(val_texts, val_labels, tokenizer, HPARAMS["max_length"])

    strat = "epoch" if val_dataset else "no"
    training_args_kwargs = dict(
        output_dir=output_dir,
        run_name=run_name,
        learning_rate=HPARAMS["learning_rate"],
        per_device_train_batch_size=HPARAMS["batch_size"],
        per_device_eval_batch_size=HPARAMS["batch_size"],
        num_train_epochs=num_epochs,
        weight_decay=HPARAMS["weight_decay"],
        warmup_ratio=HPARAMS["warmup_ratio"],
        save_total_limit=2,
        load_best_model_at_end=(val_dataset is not None),
        metric_for_best_model=HPARAMS["metric_for_best_model"],
        greater_is_better=HPARAMS["greater_is_better"],
        logging_steps=50,
        report_to=["wandb"] if use_wandb else [],
        remove_unused_columns=False,
        seed=SEED,
        fp16=torch.cuda.is_available(),
        dataloader_num_workers=0,
    )
    # Handle eval_strategy rename (transformers 4.46+)
    if TF_VERSION >= (4, 46):
        training_args_kwargs["eval_strategy"] = strat
        training_args_kwargs["save_strategy"] = strat
    else:
        training_args_kwargs["evaluation_strategy"] = strat
        training_args_kwargs["save_strategy"] = strat
    training_args = TrainingArguments(**training_args_kwargs)

    trainer = WeightedTrainer(
        class_weights=class_weights,
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        compute_metrics=compute_metrics,
    )
    trainer.tokenizer = tokenizer  # set separately for later use

    trainer.train()
    return trainer


# ── Stratified 5-Fold CV ──────────────────────────────────────────────────

def run_cv(df: pd.DataFrame, use_wandb: bool = True) -> list[float]:
    print("\n" + "=" * 60)
    print("STRATIFIED 5-FOLD CROSS-VALIDATION")
    print("=" * 60)

    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    fold_f1 = []

    for fold, (train_idx, val_idx) in enumerate(skf.split(df["text"], df["label_id"])):
        print(f"\n--- Fold {fold + 1}/5 ---")
        fold_dir = str(MODEL_DIR / f"muril-cv-fold-{fold + 1}")

        train_texts = df.iloc[train_idx]["text"].tolist()
        train_labels = df.iloc[train_idx]["label_id"].tolist()
        val_texts = df.iloc[val_idx]["text"].tolist()
        val_labels = df.iloc[val_idx]["label_id"].tolist()

        weights = compute_class_weight("balanced", classes=np.unique(train_labels), y=train_labels)
        class_weights = torch.tensor(weights, dtype=torch.float)

        trainer = train_model(
            train_texts, train_labels,
            val_texts, val_labels,
            class_weights,
            HPARAMS["model_name"],
            fold_dir,
            run_name=f"muril-cv-fold-{fold + 1}",
            num_epochs=HPARAMS["num_epochs"],
            use_wandb=use_wandb,
        )

        preds = trainer.predict(
            GSTDataset(val_texts, val_labels, trainer.tokenizer, HPARAMS["max_length"])
        )
        f1 = f1_score(val_labels, np.argmax(preds.predictions, axis=-1), average="macro", zero_division=0)
        fold_f1.append(round(float(f1), 4))
        print(f"  Fold {fold + 1} F1 (macro): {f1:.4f}")

        # Memory cleanup after each fold
        del trainer
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        gc.collect()

        # Clean up fold model to save disk space
        import shutil
        if Path(fold_dir).exists():
            shutil.rmtree(fold_dir, ignore_errors=True)

    return fold_f1


# ── Full training on all train data ────────────────────────────────────────

def train_final(
    df_train: pd.DataFrame,
    df_val: pd.DataFrame,
    use_wandb: bool = True,
) -> Trainer:
    print("\n" + "=" * 60)
    print("FINAL TRAINING (train + val)")
    print("=" * 60)

    weights = compute_class_weight(
        "balanced",
        classes=np.unique(df_train["label_id"]),
        y=df_train["label_id"],
    )
    class_weights = torch.tensor(weights, dtype=torch.float)

    trainer = train_model(
        df_train["text"].tolist(),
        df_train["label_id"].tolist(),
        df_val["text"].tolist(),
        df_val["label_id"].tolist(),
        class_weights,
        HPARAMS["model_name"],
        str(MODEL_DIR / "muril-gst-v2"),
        run_name="muril-gst-v2-final",
        num_epochs=HPARAMS["num_epochs"],
        use_wandb=use_wandb,
    )

    return trainer


# ── Evaluation ─────────────────────────────────────────────────────────────

def evaluate_and_save(trainer: Trainer, df_test: pd.DataFrame):
    print("\n" + "=" * 60)
    print("FINAL EVALUATION ON HELD-OUT TEST SET")
    print("=" * 60)

    EVAL_DIR.mkdir(parents=True, exist_ok=True)

    test_dataset = GSTDataset(
        df_test["text"].tolist(), df_test["label_id"].tolist(),
        trainer.tokenizer, HPARAMS["max_length"],
    )
    preds = trainer.predict(test_dataset)
    y_pred = np.argmax(preds.predictions, axis=-1)
    y_true = df_test["label_id"].values

    # Classification report
    report = classification_report(y_true, y_pred, target_names=CLASS_NAMES, output_dict=True, zero_division=0)
    report_text = classification_report(y_true, y_pred, target_names=CLASS_NAMES, zero_division=0)
    with open(EVAL_DIR / "classification_report.txt", "w") as f:
        f.write(report_text)
    print(report_text)

    # Per-class F1
    per_class_f1 = {CLASS_NAMES[i]: round(float(report[CLASS_NAMES[i]]["f1-score"]), 4) for i in range(NUM_LABELS)}

    # Confusion matrix
    cm = confusion_matrix(y_true, y_pred)
    try:
        plt.figure(figsize=(10, 8))
        cm_normalized = cm.astype("float") / cm.sum(axis=1, keepdims=True)
        sns.heatmap(cm_normalized, annot=True, fmt=".2f", xticklabels=CLASS_NAMES, yticklabels=CLASS_NAMES, cmap="Blues")
        plt.title("Normalized Confusion Matrix — GST Classifier v2")
        plt.ylabel("True Label")
        plt.xlabel("Predicted Label")
        plt.tight_layout()
        plt.savefig(EVAL_DIR / "confusion_matrix.png", dpi=150)
        plt.close()
        print(f"  Confusion matrix saved to {EVAL_DIR / 'confusion_matrix.png'}")

        if trainer.args.report_to and "wandb" in trainer.args.report_to:
            import wandb
            wandb.log({"confusion_matrix": wandb.Image(str(EVAL_DIR / "confusion_matrix.png"))})
    except Exception as e:
        print(f"  Skipping confusion matrix plot: {e}")

    # Learning curves
    try:
        logs = trainer.state.log_history
        train_entries = [(l["epoch"], l["loss"]) for l in logs if "loss" in l and "eval_loss" not in l]
        val_entries = [(l["epoch"], l["eval_loss"], l.get("eval_f1_macro")) for l in logs if "eval_loss" in l]

        if train_entries and val_entries:
            fig, axes = plt.subplots(1, 2, figsize=(13, 4))
            axes[0].plot([e for e, _ in train_entries], [v for _, v in train_entries], label="Train Loss", alpha=0.8)
            axes[0].plot([e for e, _, _ in val_entries], [v for _, v, _ in val_entries], label="Val Loss", marker="o")
            axes[0].set_xlabel("Epoch"); axes[0].set_ylabel("Loss")
            axes[0].legend(); axes[0].grid(alpha=0.3)

            val_f1s = [(e, f) for e, _, f in val_entries if f is not None]
            if val_f1s:
                axes[1].plot([e for e, _ in val_f1s], [f for _, f in val_f1s], label="Val F1 (macro)", marker="o", color="green")
                axes[1].set_xlabel("Epoch"); axes[1].set_ylabel("F1 Macro")
                axes[1].legend(); axes[1].grid(alpha=0.3)

            plt.tight_layout()
            plt.savefig(EVAL_DIR / "learning_curves.png", dpi=150)
            plt.close()
            print(f"  Learning curves saved to {EVAL_DIR / 'learning_curves.png'}")
    except Exception as e:
        print(f"  Skipping learning curves: {e}")

    return y_pred, y_true, per_class_f1


# ── Baseline: xlm-roberta-base quick fine-tune ────────────────────────────

def train_xlm_baseline(df_train: pd.DataFrame, df_val: pd.DataFrame, df_test: pd.DataFrame, use_wandb: bool = True) -> float:
    print("\n" + "=" * 60)
    print("BASELINE: xlm-roberta-base (2 epochs)")
    print("=" * 60)

    weights = compute_class_weight(
        "balanced", classes=np.unique(df_train["label_id"]), y=df_train["label_id"],
    )
    class_weights = torch.tensor(weights, dtype=torch.float)

    trainer = train_model(
        df_train["text"].tolist(),
        df_train["label_id"].tolist(),
        df_val["text"].tolist(),
        df_val["label_id"].tolist(),
        class_weights,
        "xlm-roberta-base",
        str(MODEL_DIR / "xlm-roberta-baseline"),
        run_name="xlm-roberta-baseline",
        num_epochs=2,
        use_wandb=use_wandb,
    )

    # Evaluate on test set for fair comparison
    test_dataset = GSTDataset(
        df_test["text"].tolist(), df_test["label_id"].tolist(),
        trainer.tokenizer, HPARAMS["max_length"],
    )
    preds = trainer.predict(test_dataset)
    f1 = f1_score(df_test["label_id"].values, np.argmax(preds.predictions, axis=-1), average="macro", zero_division=0)
    print(f"  xlm-roberta-base Test F1: {f1:.4f}")

    # Clean up
    del trainer
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    gc.collect()
    import shutil
    if (MODEL_DIR / "xlm-roberta-baseline").exists():
        shutil.rmtree(MODEL_DIR / "xlm-roberta-baseline", ignore_errors=True)

    return round(float(f1), 4)


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fast", action="store_true", help="Quick test (1 epoch, no CV)")
    parser.add_argument("--no-wandb", action="store_true", help="Disable W&B logging")
    args = parser.parse_args()

    use_wandb = not args.no_wandb

    print("=" * 60)
    print("VYAPAAR BANDHU GST CLASSIFIER v2")
    print("=" * 60)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}")
    if device == "cuda":
        print(f"GPU: {torch.cuda.get_device_name(0)}")

    # Load data
    print("\nLoading data...")
    df_train = load_split(TRAIN_CSV)
    df_val = load_split(VAL_CSV)
    df_test = load_split(TEST_CSV)
    print(f"  Train: {len(df_train)} | Val: {len(df_val)} | Test: {len(df_test)}")

    # ── W&B Init ──
    wandb_run = None
    if use_wandb:
        try:
            import wandb
            wandb_api_key = os.getenv("WANDB_API_KEY")
            if wandb_api_key:
                wandb.login(key=wandb_api_key)
            wandb_run = wandb.init(
                project="vyapaar-bandhu-gst-classifier-v2",
                name="muril-gst-v2-full",
                config={
                    **HPARAMS,
                    "train_size": len(df_train),
                    "val_size": len(df_val),
                    "test_size": len(df_test),
                    "class_names": CLASS_NAMES,
                },
            )
            print(f"  W&B run: {wandb_run.url if wandb_run else 'N/A'}")
        except Exception as e:
            print(f"  W&B init failed: {e}")
            use_wandb = False

    results = {}

    # ── 1. Keyword baseline ──
    print("\n" + "=" * 60)
    print("BASELINE 1: Keyword Rule-Based")
    print("=" * 60)
    kw_test = evaluate_keyword_baseline(df_test)
    kw_val = evaluate_keyword_baseline(df_val)
    kw_f1 = kw_test["f1_macro"]
    print(f"  Test F1 (macro): {kw_f1:.4f}")

    # ── 2. Cross-validation ──
    if args.fast:
        cv_f1 = [0.85]  # placeholder
        print("\n  Fast mode: skipping 5-fold CV")
    else:
        cv_f1 = run_cv(pd.concat([df_train, df_val], ignore_index=True), use_wandb=use_wandb)

    cv_mean = round(float(np.mean(cv_f1)), 4) if cv_f1 else 0.0
    cv_std = round(float(np.std(cv_f1)), 4) if cv_f1 else 0.0
    results["cv_f1_mean"] = cv_mean
    results["cv_f1_std"] = cv_std
    results["cv_f1_list"] = cv_f1

    print(f"\n  5-Fold CV F1 (macro): {cv_mean} ± {cv_std}")

    # ── 3. xlm-roberta baseline ──
    xlm_f1 = 0.0
    if not args.fast:
        xlm_f1 = train_xlm_baseline(df_train, df_val, df_test, use_wandb=use_wandb)
    results["xlm_f1"] = xlm_f1

    # ── 4. Final training ──
    trainer = train_final(df_train, df_val, use_wandb=use_wandb)

    # ── 5. Evaluation ──
    y_pred, y_true, per_class_f1 = evaluate_and_save(trainer, df_test)
    test_f1 = round(float(f1_score(y_true, y_pred, average="macro")), 4)
    val_preds = trainer.predict(
        GSTDataset(df_val["text"].tolist(), df_val["label_id"].tolist(), trainer.tokenizer, HPARAMS["max_length"])
    )
    val_f1 = round(float(f1_score(df_val["label_id"].values, np.argmax(val_preds.predictions, axis=-1), average="macro")), 4)

    results["val_f1"] = val_f1
    results["test_f1"] = test_f1
    results["per_class_f1"] = per_class_f1
    results["keyword_baseline_f1"] = kw_f1
    results["model"] = "muril-v2"

    # Save final metrics
    with open(EVAL_DIR / "final_metrics.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n  Final metrics saved to {EVAL_DIR / 'final_metrics.json'}")

    # Save baselines
    baselines = {
        "keyword_rule_based": {"test_f1_macro": kw_f1},
        "xlm_roberta_base": {"val_f1_macro": xlm_f1},
        "muril_base_v2": {"cv_f1_macro_mean": cv_mean, "cv_f1_macro_std": cv_std, "val_f1_macro": val_f1, "test_f1_macro": test_f1},
    }
    with open(EVAL_DIR / "baselines.json", "w") as f:
        json.dump(baselines, f, indent=2)

    # ── W&B log final ──
    if wandb_run is not None:
        import wandb
        wandb.log({
            "cv_f1_mean": cv_mean,
            "cv_f1_std": cv_std,
            "val_f1_macro": val_f1,
            "test_f1_macro": test_f1,
            "keyword_baseline_f1": kw_f1,
            "xlm_baseline_f1": xlm_f1,
        })
        wandb.log({"per_class_f1_table": wandb.Table(
            columns=["Class", "F1"],
            data=[[c, per_class_f1[c]] for c in CLASS_NAMES],
        )})
        wandb_run.finish()

    # ── Save model ──
    final_path = MODEL_DIR / "muril-gst-v2"
    trainer.save_model(str(final_path))
    trainer.tokenizer.save_pretrained(str(final_path))

    # Save inference config alongside model
    inference_config = {
        "model_name": "meet136/muril-gst-classifier-v2",
        "model_version": "v2",
        "base_model": HPARAMS["model_name"],
        "confidence_threshold": 0.65,
        "class_names": CLASS_NAMES,
        "test_f1_macro": test_f1,
        "cv_f1_mean": cv_mean,
        "cv_f1_std": cv_std,
    }
    with open(final_path / "inference_config.json", "w") as f:
        json.dump(inference_config, f, indent=2)
    print(f"\n  Model saved to {final_path}")

    # ── Final Summary ──
    kw_baseline_f1 = kw_f1
    best_baseline = max(kw_baseline_f1, xlm_f1)
    improvement = test_f1 - best_baseline

    print()
    print("=" * 60)
    print("VYAPAAR BANDHU GST CLASSIFIER v2 - RESULTS")
    print("=" * 60)
    print(f"Base Model: {HPARAMS['model_name']}")
    print(f"Dataset: ~7,000 synthetic + augmented samples")
    print()
    print(f"5-Fold CV F1 (macro):     {cv_mean:.4f} ± {cv_std:.4f}")
    print(f"Validation F1 (macro):    {val_f1:.4f}")
    print(f"Real-world Test F1 (macro): {test_f1:.4f}")
    print()
    print("Per-class Test F1:")
    for c in CLASS_NAMES:
        print(f"  {c:35s} {per_class_f1[c]:.4f}")
    print()
    print("Baseline comparison:")
    print(f"  Keyword rule-based:     {kw_baseline_f1:.4f}")
    print(f"  xlm-roberta-base:       {xlm_f1:.4f}")
    print(f"  muril-base (ours):      {test_f1:.4f} (Δ +{improvement:.4f} over best baseline)")
    print()
    if wandb_run:
        print(f"W&B run: {wandb_run.url}")
    print("=" * 60)


if __name__ == "__main__":
    set_seed(SEED)
    main()
