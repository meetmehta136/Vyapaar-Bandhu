## VYAPAAR BANDHU — GST CLASSIFIER v2 — COMPLETE COLAB PIPELINE
## Upload this file to Google Colab and run each cell top-to-bottom
## Estimated time: 60-80 min on T4 GPU (free Colab tier)
"""
BEFORE RUNNING:
  1. Runtime -> Change runtime type -> T4 GPU
  2. Sidebar key icon -> Add secrets:
       ANTHROPIC_API_KEY  (for data generation)
       WANDB_API_KEY      (for experiment tracking)
       HF_TOKEN           (for HuggingFace upload)
"""

# ── BUGS FIXED vs ORIGINAL train.py ────────────────────────────
# 1. Learning curves x-axis: was using step-count offset (wrong),
#    now reads epoch numbers directly from log_history entries.
# 2. CV memory leak: added del trainer + torch.cuda.empty_cache()
#    + gc.collect() after each fold to prevent T4 OOM.
# 3. matplotlib scope: moved imports to top level; original had
#    plt defined inside a try block making it undefined later.
# 4. eval_strategy rename: transformers >=4.46 renamed
#    evaluation_strategy -> eval_strategy; handled with version check.
# 5. metric_for_best_model: must include "eval_" prefix in newer
#    transformers; fixed to always prefix correctly.
# 6. Unused imports removed.
# 7. load_dotenv crash in Colab: wrapped in try/except.
# 8. inference_config.json added after model save.
# 9. WeightedTrainer: added proper CUDA device handling for
#    class_weights tensor to avoid device mismatch on GPU.
# 10. xlm-roberta baseline: now evaluates on test set (not val)
#     for fair comparison in the baselines.json table.

# =============================================================
# CELL 1 — Install dependencies
# =============================================================
import subprocess, sys

def install(pkg):
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", pkg])

for p in [
    "transformers>=4.46.0", "datasets", "wandb", "scikit-learn",
    "seaborn", "matplotlib", "anthropic", "huggingface_hub",
    "accelerate>=0.26.0", "python-dotenv", "pandas", "numpy", "torch", "tqdm",
]:
    install(p)
print("Done. Restart runtime, then continue from Cell 2.")

# =============================================================
# CELL 2 — Imports and secrets
# =============================================================
import gc, json, os, time, warnings
from pathlib import Path
from collections import Counter
import torch, torch.nn as nn
import numpy as np, pandas as pd
import matplotlib, matplotlib.pyplot as plt
matplotlib.use("Agg")
import seaborn as sns
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.utils.class_weight import compute_class_weight
from transformers import (
    AutoModelForSequenceClassification, AutoTokenizer, Trainer,
    TrainingArguments, set_seed,
)
import transformers
import huggingface_hub
warnings.filterwarnings("ignore")

# ── Colab secrets ──
try:
    from google.colab import userdata
    for key in ("ANTHROPIC_API_KEY", "WANDB_API_KEY", "HF_TOKEN"):
        val = userdata.get(key)
        if val: os.environ[key] = val
    print("Secrets loaded from Colab secret store.")
except Exception:
    print("Not in Colab. Set API keys via environment variables or .env.")

# ── Paths ──
BASE_DIR = Path("/content/vyapaar-bandhu")
ML_DIR = BASE_DIR / "ml"
DATA_DIR = ML_DIR / "data"
MODEL_DIR = ML_DIR / "models"
EVAL_DIR = ML_DIR / "evaluation"
for d in [DATA_DIR, MODEL_DIR, EVAL_DIR]:
    d.mkdir(parents=True, exist_ok=True)

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Device: {DEVICE}")
if DEVICE == "cuda":
    print(f"GPU: {torch.cuda.get_device_name(0)}")

SEED = 42
set_seed(SEED)

TF_VERSION = tuple(int(x) for x in transformers.__version__.split(".")[:2])
print(f"transformers {transformers.__version__}")

# =============================================================
# CELL 3 — Configuration
# =============================================================
CLASS_NAMES = [
    "capital_goods", "input_services", "raw_materials",
    "motor_vehicles_conveyance", "food_beverages_catering",
    "club_health_beauty", "personal_employee_benefit",
]
NUM_LABELS = len(CLASS_NAMES)
LABEL_TO_ID = {n: i for i, n in enumerate(CLASS_NAMES)}
ID_TO_LABEL = {i: n for i, n in enumerate(CLASS_NAMES)}

HPARAMS = {
    "model_name": "google/muril-base-cased",
    "max_length": 128,
    "batch_size": 16,
    "learning_rate": 2e-5,
    "num_epochs": 5,
    "warmup_ratio": 0.1,
    "weight_decay": 0.01,
    "confidence_threshold": 0.65,
}

# transformers >=5.0 renamed tokenizer kwarg to processing_class
TOK_KWARG = "processing_class" if TF_VERSION >= (5, 0) else "tokenizer"
# ============================================================
# CELL 4 REPLACEMENT — Template-based data generation (FREE)
# No API key needed. Generates ~6,300 samples in <10 seconds.
# Replace Cell 4 entirely with this cell and run it.
# ============================================================

import random
import itertools
import pandas as pd
from pathlib import Path

random.seed(42)

# ── Shared vocabulary ─────────────────────────────────────
AMOUNTS = [
    "₹500", "₹1200", "₹2500", "₹4500", "₹8000", "₹12000", "₹25000",
    "₹45000", "Rs.750", "Rs.3500", "2500/-", "8000/-", "15000/-",
    "₹1,20,000", "₹5,00,000",
]
UNITS = [
    "1 pc", "2 pcs", "3 units", "5 kg", "10 kg", "50 kg", "100 kg",
    "1 month", "3 months", "6 months", "1 year", "12 nos",
    "500 ml", "1 ltr", "50 mtrs", "1 box", "1 set",
]
TAX_SUFFIXES = ["+ GST", "+ 18% GST", "incl GST", "excl tax", "+ IGST", ""]

def pick(*args):
    """Randomly pick one item from args."""
    return random.choice(args)

def maybe(val, prob=0.4):
    """Return val with probability prob, else empty string."""
    return val if random.random() < prob else ""

def amt():
    return maybe(random.choice(AMOUNTS), 0.45)

def unit():
    return maybe(random.choice(UNITS), 0.35)

def tax():
    return maybe(random.choice(TAX_SUFFIXES), 0.25)

def ocr_noise(text, rate=0.08):
    """Simulate OCR typos in a fraction of samples."""
    if random.random() > rate:
        return text
    chars = list(text)
    noise_map = {'o': '0', 'O': '0', 'l': '1', 'i': 'l', 'a': '@', ' ': '  '}
    idx = random.randint(0, len(chars) - 1)
    chars[idx] = noise_map.get(chars[idx], chars[idx])
    return ''.join(chars)


# ── Per-class template functions ───────────────────────────

def gen_capital_goods():
    templates = [
        # English Indian
        lambda: f"Laptop purchase {maybe('HP', 0.5) or pick('Dell', 'Lenovo', 'Asus')} {amt()} {tax()}",
        lambda: f"Desktop computer {pick('Core i5', 'Core i7', 'Ryzen 5')} {amt()}",
        lambda: f"Printer {pick('laser', 'inkjet', 'thermal')} {pick('Epson', 'HP', 'Canon')} {amt()}",
        lambda: f"Office furniture {pick('chairs', 'tables', 'almirah', 'workstation')} {unit()} {amt()}",
        lambda: f"Generator {pick('5 KVA', '10 KVA', '7.5 KVA')} {pick('Kirloskar', 'Mahindra')} {amt()}",
        lambda: f"CCTV camera {pick('set', 'installation')} {unit()} {amt()}",
        lambda: f"Air conditioner {pick('1.5 ton', '2 ton')} {pick('Voltas', 'Daikin', 'LG')} {amt()}",
        lambda: f"Server {pick('rack', 'tower')} {pick('Dell PowerEdge', 'HP ProLiant')} {amt()}",
        lambda: f"Projector {pick('Epson', 'BenQ')} {pick('HD', 'Full HD')} {amt()}",
        lambda: f"Scanner {pick('flatbed', 'document')} {pick('Canon', 'Fujitsu')} {amt()}",
        lambda: f"UPS {pick('1 KVA', '2 KVA', '650VA')} {pick('APC', 'Luminous')} {amt()}",
        lambda: f"Machine purchase {pick('cutting', 'drilling', 'welding', 'stitching')} {amt()}",
        lambda: f"Factory equipment {pick('conveyor belt', 'hydraulic press', 'compressor')} {amt()}",
        lambda: f"Weighing machine {pick('digital', 'platform')} {unit()} {amt()}",
        # Hindi Roman
        lambda: f"Office ke liye laptop {pick('HP', 'Dell', 'Lenovo')} kharida {amt()}",
        lambda: f"Furniture kharida {pick('2 kursi', '1 table', '3 chairs')} {amt()}",
        lambda: f"CCTV camera lagaya {pick('4 cameras', '8 cameras')} {amt()}",
        lambda: f"AC liya {pick('1.5 ton', '2 ton')} {pick('split', 'window')} {amt()}",
        lambda: f"Machine kharidi {pick('printing', 'cutting', 'packing')} ke liye {amt()}",
        lambda: f"Server kharida office ke liye {amt()}",
        lambda: f"Printer liya {pick('laser', 'inkjet')} {amt()}",
        lambda: f"Generator kharida {pick('5KVA', '10KVA')} backup ke liye {amt()}",
        # Code-mixed
        lambda: f"Office laptop purchase kiya {pick('HP', 'Dell')} {amt()} {tax()}",
        lambda: f"Factory machine kharidi {pick('packing', 'cutting')} {amt()}",
        lambda: f"Computer system liya {unit()} {amt()}",
        lambda: f"Furniture order kiya office ke liye {amt()}",
        # Gujarati-style
        lambda: f"Laptop kharido {pick('office', 'shop')} mate {amt()}",
        lambda: f"Machine kharidi factory mate {pick('cutting', 'stitching')} {amt()}",
        lambda: f"Computer system {pick('1 set', '2 set')} kharido {amt()}",
    ]
    return ocr_noise(random.choice(templates)().strip())


def gen_input_services():
    templates = [
        lambda: f"CA fees {pick('GST filing', 'audit', 'tax return', 'ITR filing')} {pick('FY24', 'FY25', 'quarterly')} {amt()}",
        lambda: f"Legal consultation {pick('contract review', 'property', 'labour')} {amt()}",
        lambda: f"Courier charges {pick('Blue Dart', 'DTDC', 'Delhivery', 'FedEx')} {unit()} {amt()}",
        lambda: f"Advertising {pick('Google Ads', 'Facebook', 'newspaper', 'hoarding')} {amt()} {tax()}",
        lambda: f"Software subscription {pick('Tally Prime', 'Zoho Books', 'QuickBooks', 'Microsoft 365')} {unit()} {amt()}",
        lambda: f"Security guard service {pick('monthly', 'yearly')} contract {amt()}",
        lambda: f"Maintenance contract {pick('AC', 'lift', 'CCTV', 'generator')} AMC {amt()}",
        lambda: f"Marketing agency fees {pick('monthly', 'campaign')} {amt()}",
        lambda: f"Audit fees {pick('statutory', 'internal', 'tax')} {pick('FY24', 'FY25')} {amt()}",
        lambda: f"Professional fees {pick('architect', 'consultant', 'designer')} {amt()}",
        lambda: f"Internet lease line {pick('50 Mbps', '100 Mbps')} {pick('monthly', 'yearly')} {amt()}",
        lambda: f"Cloud hosting {pick('AWS', 'Azure', 'GCP', 'DigitalOcean')} {unit()} {amt()}",
        lambda: f"Pest control service {pick('annual', 'quarterly')} contract {amt()}",
        lambda: f"Payroll processing fees {pick('monthly', 'annual')} {amt()}",
        lambda: f"Website development charges {amt()} {tax()}",
        # Hindi Roman
        lambda: f"CA ko fees diya GST filing ke liye {amt()}",
        lambda: f"Courier charges diya {pick('Blue Dart', 'DTDC')} ko {amt()}",
        lambda: f"Software subscription liya {pick('Tally', 'Zoho')} {pick('1 saal', '1 mahina')} {amt()}",
        lambda: f"Security service ka bill {pick('monthly', 'mahina')} {amt()}",
        lambda: f"Advertising ka kharcha {pick('Google', 'Facebook')} {amt()}",
        lambda: f"Legal fees diya {pick('advocate', 'lawyer')} ko {amt()}",
        lambda: f"Maintenance ka kaam karaya {pick('AC', 'generator')} {amt()}",
        # Code-mixed
        lambda: f"CA fees paid GST return ke liye {amt()}",
        lambda: f"Software subscription renew kiya {pick('Tally Prime', 'Zoho')} {amt()}",
        lambda: f"Courier send kiya {pick('Blue Dart', 'Delhivery')} through {amt()}",
        lambda: f"Security contract renew kiya {unit()} {amt()}",
        # Gujarati-style
        lambda: f"CA ni fees aapi GST bharva mate {amt()}",
        lambda: f"Software subscription lidhu {pick('Tally', 'Zoho')} {amt()}",
        lambda: f"Jaher kharchu {pick('newspaper', 'hoarding')} mate {amt()}",
    ]
    return ocr_noise(random.choice(templates)().strip())


def gen_raw_materials():
    templates = [
        lambda: f"Steel {pick('HR sheet', 'MS rod', 'angle iron', 'pipe')} {unit()} {amt()}",
        lambda: f"Cotton fabric {pick('grey', 'dyed', 'printed')} {unit()} {amt()}",
        lambda: f"Cement {pick('OPC 53', 'PPC', 'white')} {pick('Ultratech', 'ACC', 'Ambuja')} {unit()} {amt()}",
        lambda: f"Chemical {pick('HCl', 'caustic soda', 'solvent', 'acid')} {unit()} {amt()}",
        lambda: f"Packaging material {pick('carton boxes', 'HDPE bags', 'bubble wrap', 'stretch film')} {unit()} {amt()}",
        lambda: f"Timber {pick('teak', 'pine', 'sal')} wood {unit()} {amt()}",
        lambda: f"Paint {pick('Asian Paints', 'Berger', 'Nerolac')} {pick('interior', 'exterior')} {unit()} {amt()}",
        lambda: f"Plastic {pick('granules', 'sheets', 'pipes')} {unit()} {amt()}",
        lambda: f"Yarn {pick('cotton', 'polyester', 'nylon')} {unit()} {amt()}",
        lambda: f"Leather {pick('genuine', 'PU', 'synthetic')} {unit()} {amt()}",
        lambda: f"Sand {pick('river', 'M-sand', 'quarry')} {unit()} {amt()}",
        lambda: f"Raw material purchase {pick('wheat', 'rice', 'dal', 'sugar')} {unit()} {amt()}",
        lambda: f"Copper wire {pick('1.5 sqmm', '2.5 sqmm', '4 sqmm')} {pick('Finolex', 'Havells')} {unit()} {amt()}",
        lambda: f"Aluminium {pick('sheet', 'extrusion', 'ingot')} {unit()} {amt()}",
        lambda: f"PVC {pick('pipe', 'sheet', 'compound')} {unit()} {amt()}",
        # Hindi Roman
        lambda: f"Steel kharida {pick('MS rod', 'HR sheet')} {unit()} {amt()}",
        lambda: f"Kapda liya {pick('cotton', 'polyester', 'silk')} {unit()} {amt()}",
        lambda: f"Cement kharida {pick('50 bags', '100 bags')} {pick('Ultratech', 'ACC')} {amt()}",
        lambda: f"Packing material liya {pick('boxes', 'bags', 'tape')} {unit()} {amt()}",
        lambda: f"Kaccha maal kharida {pick('factory', 'manufacturing')} ke liye {amt()}",
        lambda: f"Lakdi kharidi {pick('teak', 'pine')} {unit()} {amt()}",
        # Code-mixed
        lambda: f"Steel rod purchase kiya {unit()} {amt()} {tax()}",
        lambda: f"Raw material order diya {pick('factory', 'production')} ke liye {amt()}",
        lambda: f"Fabric kharida {pick('cotton', 'synthetic')} {unit()} {amt()}",
        lambda: f"Packaging boxes order kiya {unit()} {amt()}",
        # Gujarati-style
        lambda: f"Kacho maal kharido {pick('cotton', 'steel')} {unit()} {amt()}",
        lambda: f"Packing material lidhu {unit()} {amt()}",
        lambda: f"Cement kharido {pick('Ultratech', 'ACC')} {unit()} {amt()}",
    ]
    return ocr_noise(random.choice(templates)().strip())


def gen_motor_vehicles():
    templates = [
        lambda: f"Petrol {pick('company car', 'bike', 'scooter')} {unit()} {amt()}",
        lambda: f"Diesel {pick('truck', 'tempo', 'jeep')} {unit()} {amt()}",
        lambda: f"Vehicle insurance {pick('car', 'truck', 'bike')} {pick('annual', 'comprehensive')} premium {amt()}",
        lambda: f"Tyre purchase {pick('MRF', 'Apollo', 'CEAT', 'Bridgestone')} {unit()} {amt()}",
        lambda: f"Car service {pick('Honda City', 'Maruti Swift', 'Hyundai i20')} {pick('3000 km', '10000 km')} {amt()}",
        lambda: f"Fuel bill {pick('HPCL', 'BPCL', 'Indian Oil')} pump {amt()}",
        lambda: f"Cab hire {pick('Uber', 'Ola', 'local taxi')} {unit()} {amt()}",
        lambda: f"Auto rickshaw charges {pick('daily', 'weekly', 'monthly')} {amt()}",
        lambda: f"Vehicle repair {pick('engine', 'body', 'denting painting')} {amt()}",
        lambda: f"Car purchase {pick('Maruti Dzire', 'Honda Amaze', 'Hyundai Aura')} {amt()}",
        lambda: f"Two-wheeler fuel {pick('petrol', 'diesel')} {unit()} {amt()}",
        lambda: f"Conveyance charges {pick('local', 'outstation')} {amt()}",
        lambda: f"Driver salary {pick('monthly', 'daily')} {amt()}",
        lambda: f"Parking charges {pick('monthly', 'daily')} {amt()}",
        lambda: f"Transportation freight {pick('Bluedart', 'local transporter')} {amt()}",
        # Hindi Roman
        lambda: f"Petrol bhara gaadi mein {unit()} {amt()}",
        lambda: f"Car ka insurance bhara {pick('annual', 'comprehensive')} {amt()}",
        lambda: f"Taxi ka kiraya {pick('Uber', 'Ola', 'local')} {amt()}",
        lambda: f"Gaadi ka service karaya {pick('3000 km', '10000 km')} {amt()}",
        lambda: f"Tyre kharida {pick('MRF', 'Apollo')} {unit()} {amt()}",
        lambda: f"Auto ka kharcha {pick('daily', 'monthly')} {amt()}",
        lambda: f"Diesel bhara truck mein {unit()} {amt()}",
        # Code-mixed
        lambda: f"Petrol fill kiya company car mein {amt()}",
        lambda: f"Vehicle insurance renew kiya {pick('car', 'truck')} ka {amt()}",
        lambda: f"Cab hire kiya {pick('Uber', 'Ola')} {amt()}",
        lambda: f"Car service karaya {pick('Honda', 'Maruti')} service center mein {amt()}",
        # Gujarati-style
        lambda: f"Gaadi no petrol bharyun {unit()} {amt()}",
        lambda: f"Vahan vima bharyu {pick('annual', 'comprehensive')} {amt()}",
        lambda: f"Tyre kharida {pick('MRF', 'Apollo')} {unit()} {amt()}",
    ]
    return ocr_noise(random.choice(templates)().strip())


def gen_food_beverages():
    templates = [
        lambda: f"Staff lunch {pick('catering', 'canteen', 'mess')} {unit()} {amt()}",
        lambda: f"Office snacks {pick('biscuits', 'namkeen', 'chips', 'dry fruits')} {unit()} {amt()}",
        lambda: f"Tea coffee supplies {pick('Tata Tea', 'Nescafe', 'Bru')} {unit()} {amt()}",
        lambda: f"Restaurant bill {pick('team lunch', 'client dinner', 'office party')} {amt()}",
        lambda: f"Zomato order {pick('team lunch', 'office dinner', 'snacks')} {amt()}",
        lambda: f"Swiggy order {pick('lunch', 'dinner', 'snacks')} {unit()} {amt()}",
        lambda: f"Canteen expenses {pick('monthly', 'weekly')} {amt()}",
        lambda: f"Food and beverages {pick('office', 'client entertainment')} {amt()}",
        lambda: f"Drinking water {pick('Bisleri', 'Kinley', 'Aquafina')} {unit()} {amt()}",
        lambda: f"Catering for {pick('company meeting', 'annual day', 'office party')} {amt()}",
        lambda: f"Refreshments provided to {pick('clients', 'staff', 'visitors')} {amt()}",
        lambda: f"Birthday cake {pick('office', 'team')} celebration {amt()}",
        lambda: f"Tea expenses {pick('daily', 'monthly')} {amt()}",
        lambda: f"Lunch box {pick('staff', 'employees')} {unit()} {amt()}",
        # Hindi Roman
        lambda: f"Staff ka khana {pick('catering', 'canteen')} {unit()} {amt()}",
        lambda: f"Office mein chai paani ka kharcha {pick('monthly', 'daily')} {amt()}",
        lambda: f"Lunch order kiya Zomato se {amt()}",
        lambda: f"Party ka khana {pick('birthday', 'farewell', 'celebration')} {amt()}",
        lambda: f"Nashta kharida {pick('biscuit', 'namkeen')} staff ke liye {amt()}",
        lambda: f"Restaurant ka bill {pick('team lunch', 'meeting')} ke baad {amt()}",
        lambda: f"Canteen bill {pick('weekly', 'monthly')} {amt()}",
        # Code-mixed
        lambda: f"Staff lunch order kiya Zomato se {amt()}",
        lambda: f"Office canteen ka bill {pick('monthly', 'weekly')} {amt()}",
        lambda: f"Tea coffee kharida office ke liye {unit()} {amt()}",
        lambda: f"Client ko dinner karaya {pick('restaurant', 'hotel')} mein {amt()}",
        # Gujarati-style
        lambda: f"Staff no khavano kharach {pick('monthly', 'weekly')} {amt()}",
        lambda: f"Chai paani no kharach {pick('office', 'dukan')} {amt()}",
        lambda: f"Lunch order karyu Zomato thi {amt()}",
    ]
    return ocr_noise(random.choice(templates)().strip())


def gen_club_health_beauty():
    templates = [
        lambda: f"Gym membership {pick('Gold\'s Gym', 'Cult.fit', 'local gym')} {pick('monthly', 'annual')} {amt()}",
        lambda: f"Health insurance premium {pick('Star Health', 'HDFC Ergo', 'Niva Bupa')} {pick('annual', 'monthly')} {amt()}",
        lambda: f"Beauty salon {pick('haircut', 'facial', 'manicure', 'treatment')} {amt()}",
        lambda: f"Spa treatment {pick('massage', 'body wrap', 'relaxation')} {amt()}",
        lambda: f"Club membership {pick('Lions Club', 'Rotary', 'golf club', 'sports club')} {pick('annual', 'life')} {amt()}",
        lambda: f"Yoga classes {pick('monthly', 'yearly')} {pick('Cult.fit', 'local studio')} {amt()}",
        lambda: f"Wellness program {pick('meditation', 'stress management')} {amt()}",
        lambda: f"Fitness equipment {pick('treadmill', 'cycle')} personal use {amt()}",
        lambda: f"Medical checkup {pick('annual', 'routine')} {pick('personal', 'family')} {amt()}",
        lambda: f"Salon charges {pick('haircut', 'colour', 'treatment')} {amt()}",
        lambda: f"Wellness subscription {pick('Cult.fit', 'HealthifyMe')} {unit()} {amt()}",
        lambda: f"Swimming pool membership {pick('annual', 'quarterly')} {amt()}",
        # Hindi Roman
        lambda: f"Gym membership li {pick('monthly', 'yearly')} {amt()}",
        lambda: f"Health insurance ka premium bhara {amt()}",
        lambda: f"Salon mein kaam karaya {pick('haircut', 'facial')} {amt()}",
        lambda: f"Club membership li {pick('Lions', 'Rotary')} {pick('annual', 'life')} {amt()}",
        lambda: f"Yoga class join ki {pick('monthly', 'yearly')} {amt()}",
        lambda: f"Spa treatment liya {pick('massage', 'facial')} {amt()}",
        # Code-mixed
        lambda: f"Gym membership renew kiya {pick('annual', 'monthly')} {amt()}",
        lambda: f"Health insurance premium paid {pick('Star Health', 'HDFC')} {amt()}",
        lambda: f"Salon visit kiya {pick('haircut', 'treatment')} ke liye {amt()}",
        lambda: f"Club membership fee bhari {pick('annual', 'quarterly')} {amt()}",
        # Gujarati-style
        lambda: f"Gym membership lidhu {pick('annual', 'monthly')} {amt()}",
        lambda: f"Health insurance premium bharyu {amt()}",
        lambda: f"Salon maa gaya {pick('haircut', 'facial')} mate {amt()}",
    ]
    return ocr_noise(random.choice(templates)().strip())


def gen_personal_benefit():
    templates = [
        lambda: f"Diwali gift {pick('employees', 'staff')} {unit()} {amt()}",
        lambda: f"LTA travel allowance {pick('annual', 'quarterly')} {pick('employee', 'staff')} {amt()}",
        lambda: f"Mobile phone reimbursement {pick('personal use', 'employee')} {amt()}",
        lambda: f"Home internet reimbursement {pick('staff', 'employee', 'WFH')} {pick('monthly', 'quarterly')} {amt()}",
        lambda: f"Employee welfare {pick('festival gift', 'birthday gift', 'anniversary gift')} {unit()} {amt()}",
        lambda: f"Uniform allowance {pick('staff', 'employees')} {unit()} {amt()}",
        lambda: f"Personal mobile bill {pick('reimbursed', 'claimed')} {amt()}",
        lambda: f"Conveyance allowance personal {pick('monthly', 'daily')} {amt()}",
        lambda: f"Holi gift {pick('employees', 'staff')} {unit()} {amt()}",
        lambda: f"Christmas gift staff {unit()} {amt()}",
        lambda: f"Employee outing {pick('picnic', 'team trip', 'dinner party')} {amt()}",
        lambda: f"Personal accident insurance {pick('staff', 'employee')} {pick('annual', 'monthly')} {amt()}",
        lambda: f"Work from home {pick('internet', 'furniture', 'electricity')} reimbursement {amt()}",
        lambda: f"Birthday celebration {pick('employee', 'staff')} {amt()}",
        # Hindi Roman
        lambda: f"Diwali par gift diya {pick('employees', 'staff')} ko {unit()} {amt()}",
        lambda: f"Mobile ka bill reimburse kiya {pick('employee', 'staff')} ka {amt()}",
        lambda: f"LTA diya {pick('annual', 'quarterly')} {pick('employee', 'staff')} ko {amt()}",
        lambda: f"Ghar ka internet bill reimburse kiya {pick('WFH', 'staff')} {amt()}",
        lambda: f"Uniform diya {pick('staff', 'employees')} ko {unit()} {amt()}",
        lambda: f"Festival gift diya {pick('Diwali', 'Holi', 'Eid')} par {unit()} {amt()}",
        # Code-mixed
        lambda: f"Employee ko Diwali gift diya {unit()} {amt()}",
        lambda: f"Mobile reimbursement diya {pick('staff', 'employee')} ko {amt()}",
        lambda: f"LTA claim kiya {pick('annual', 'quarterly')} {amt()}",
        lambda: f"WFH internet bill reimburse kiya {unit()} {amt()}",
        # Gujarati-style
        lambda: f"Diwali ni bhent aapi {pick('employees', 'staff')} ne {unit()} {amt()}",
        lambda: f"Mobile bill reimburse karyu {pick('staff', 'employee')} nu {amt()}",
        lambda: f"Festival gift apyu {pick('Diwali', 'Holi')} na {unit()} {amt()}",
    ]
    return ocr_noise(random.choice(templates)().strip())


# ── Generation ─────────────────────────────────────────────

CLASS_GENERATORS = {
    "capital_goods": gen_capital_goods,
    "input_services": gen_input_services,
    "raw_materials": gen_raw_materials,
    "motor_vehicles_conveyance": gen_motor_vehicles,
    "food_beverages_catering": gen_food_beverages,
    "club_health_beauty": gen_club_health_beauty,
    "personal_employee_benefit": gen_personal_benefit,
}

SAMPLES_PER_CLASS = 900   # 900 × 7 = 6,300 total

print(f"Generating {SAMPLES_PER_CLASS} samples per class × {len(CLASS_GENERATORS)} classes...")

all_rows = []
for class_name, gen_fn in CLASS_GENERATORS.items():
    samples = [gen_fn() for _ in range(SAMPLES_PER_CLASS)]
    for text in samples:
        all_rows.append({"text": text, "label": class_name, "is_synthetic": True})
    print(f"  ✅ {class_name}: {SAMPLES_PER_CLASS} samples")

df_raw = pd.DataFrame(all_rows).sample(frac=1, random_state=42).reset_index(drop=True)
raw_path = DATA_DIR / "raw_synthetic.csv"
df_raw.to_csv(raw_path, index=False)

print(f"\n✅ Generated {len(df_raw)} total samples → {raw_path}")
print("\nClass distribution:")
print(df_raw["label"].value_counts().to_string())
print("\nSample rows per class:")
for cls in CLASS_GENERATORS:
    sample = df_raw[df_raw["label"] == cls]["text"].iloc[0]
    print(f"  {cls}: {sample}")

# =============================================================
# CELL 5 — Data preparation
# =============================================================
if not (DATA_DIR / "train.csv").exists():
    df = pd.read_csv(DATA_DIR / "raw_synthetic.csv")
    df = df.drop_duplicates(subset=["text"])
    df = df[df["text"].str.split().str.len().between(2, 35)]
    df = df[~df["text"].str.match(r"^[\d\sRs./,-]+$")]
    df["text"] = df["text"].str.strip()
    df = df.dropna(subset=["text", "label"])
    df = df[df["label"].isin(CLASS_NAMES)]

    test_rows, remain_rows = [], []
    for cn in CLASS_NAMES:
        cd = df[df["label"] == cn].sample(frac=1, random_state=SEED)
        ts = min(100, len(cd) // 6)
        test_rows.append(cd.iloc[:ts])
        remain_rows.append(cd.iloc[ts:])

    df_test = pd.concat(test_rows, ignore_index=True)
    df_remain = pd.concat(remain_rows, ignore_index=True)
    df_train, df_val = train_test_split(df_remain, test_size=0.18, random_state=SEED, stratify=df_remain["label"])

    for n, d in [("train", df_train), ("val", df_val), ("test", df_test)]:
        d.to_csv(DATA_DIR / f"{n}.csv", index=False)
    print(f"Train: {len(df_train)}  Val: {len(df_val)}  Test: {len(df_test)}")
else:
    print("Splits exist. Skipping.")

# =============================================================
# CELL 6 — Dataset, Trainer, Utilities
# =============================================================
def load_split(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["label_id"] = df["label"].map(LABEL_TO_ID).astype(int)
    return df

class GSTDataset(torch.utils.data.Dataset):
    def __init__(self, texts, labels, tokenizer, max_len):
        self.texts, self.labels, self.tokenizer, self.max_len = texts, labels, tokenizer, max_len
    def __len__(self): return len(self.texts)
    def __getitem__(self, idx):
        enc = self.tokenizer(self.texts[idx], truncation=True, padding="max_length", max_length=self.max_len, return_tensors="pt")
        return {"input_ids": enc["input_ids"].squeeze(0), "attention_mask": enc["attention_mask"].squeeze(0), "labels": torch.tensor(self.labels[idx], dtype=torch.long)}

class WeightedTrainer(Trainer):
    def __init__(self, class_weights=None, **kwargs):
        super().__init__(**kwargs)
        self.class_weights = class_weights
    def compute_loss(self, model, inputs, return_outputs=False, num_items_in_batch=None):
        labels = inputs.pop("labels")
        outputs = model(**inputs)
        if self.class_weights is not None:
            loss_fn = nn.CrossEntropyLoss(weight=self.class_weights.to(outputs.logits.device))
        else:
            loss_fn = nn.CrossEntropyLoss()
        loss = loss_fn(outputs.logits, labels)
        return (loss, outputs) if return_outputs else loss

def compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, -1)
    return {"f1_macro": f1_score(labels, preds, average="macro", zero_division=0), "accuracy": float((preds == labels).mean())}

def make_args(out_dir, run_name, epochs, use_wandb):
    common = dict(
        output_dir=out_dir, run_name=run_name,
        learning_rate=HPARAMS["learning_rate"],
        per_device_train_batch_size=HPARAMS["batch_size"],
        per_device_eval_batch_size=HPARAMS["batch_size"],
        num_train_epochs=epochs, weight_decay=HPARAMS["weight_decay"],
        warmup_ratio=HPARAMS["warmup_ratio"], save_total_limit=2,
        load_best_model_at_end=True, metric_for_best_model="eval_f1_macro",
        greater_is_better=True, logging_steps=50,
        report_to=["wandb"] if use_wandb else [],
        remove_unused_columns=False, seed=SEED,
        fp16=(DEVICE == "cuda"), dataloader_num_workers=0,
    )
    strat = "epoch"
    if TF_VERSION >= (4, 46):
        common["eval_strategy"] = strat
        common["save_strategy"] = strat
        if "evaluation_strategy" in common: del common["evaluation_strategy"]
    else:
        common["evaluation_strategy"] = strat
        common["save_strategy"] = strat
    return TrainingArguments(**common)

def build_weights(labels):
    classes = np.unique(labels)
    w = compute_class_weight("balanced", classes=classes, y=labels)
    return torch.tensor(w, dtype=torch.float)

def train_run(train_texts, train_labels, val_texts, val_labels, model_name, out_dir, run_name, epochs, use_wandb):
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(model_name, num_labels=NUM_LABELS, ignore_mismatched_sizes=True, id2label=ID_TO_LABEL, label2id=LABEL_TO_ID)
    train_ds = GSTDataset(train_texts, train_labels, tokenizer, HPARAMS["max_length"])
    val_ds = GSTDataset(val_texts, val_labels, tokenizer, HPARAMS["max_length"])
    cw = build_weights(train_labels)
    args = make_args(out_dir, run_name, epochs, use_wandb)
    trainer = WeightedTrainer(class_weights=cw, model=model, args=args, train_dataset=train_ds, eval_dataset=val_ds, **{TOK_KWARG: tokenizer}, compute_metrics=compute_metrics)
    trainer.train()
    return trainer, tokenizer

# =============================================================
# CELL 7 — Keyword baseline
# =============================================================
KEYWORD_RULES = {
    "capital_goods": ["laptop","computer","printer","furniture","machine","equipment","generator","cctv","server","desktop","monitor","tablet","scanner","projector","machinery"],
    "input_services": ["accounting","legal","courier","advertising","software","consultancy","audit","tax","subscription","marketing","professional fee","security service","ca fee","gst filing","tally"],
    "raw_materials": ["steel","cement","chemical","packaging","fabric","raw material","paint","plastic","timber","wood","brick","sand","yarn","leather","cotton","granule"],
    "motor_vehicles_conveyance": ["car","bike","truck","vehicle","petrol","diesel","fuel","tyre","transportation","taxi","conveyance","gaadi","uber","ola","auto rickshaw","scooter"],
    "food_beverages_catering": ["lunch","dinner","catering","restaurant","canteen","zomato","swiggy","food","snack","tea","coffee","refreshment","khana"],
    "club_health_beauty": ["gym","health","beauty","salon","spa","club membership","yoga","wellness","fitness","insurance premium"],
    "personal_employee_benefit": ["gift","allowance","reimbursement","welfare","uniform","diwali","lta","travel allowance","mobile reimbursement"],
}
def kw_classify(text):
    tl = text.lower()
    best, best_s = "capital_goods", 0
    for c, kws in KEYWORD_RULES.items():
        s = sum(1 for kw in kws if kw in tl)
        if s > best_s: best, best_s = c, s
    return LABEL_TO_ID[best]

def eval_kw(df):
    yt = df["label_id"].values
    yp = [kw_classify(t) for t in df["text"]]
    f1 = f1_score(yt, yp, average="macro", zero_division=0)
    print(f"  Keyword F1: {f1:.4f}")
    return round(float(f1), 4)

# =============================================================
# CELL 8 — Evaluation artifacts
# =============================================================
def save_artifacts(trainer, tokenizer, df_test, val_f1, wandb_run=None):
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    test_ds = GSTDataset(df_test["text"].tolist(), df_test["label_id"].tolist(), tokenizer, HPARAMS["max_length"])
    po = trainer.predict(test_ds)
    yp, yt = np.argmax(po.predictions, -1), df_test["label_id"].values
    rs = classification_report(yt, yp, target_names=CLASS_NAMES, zero_division=0)
    rd = classification_report(yt, yp, target_names=CLASS_NAMES, output_dict=True, zero_division=0)
    with open(EVAL_DIR/"classification_report.txt","w") as f: f.write(rs)
    print(rs)
    pcf = {CLASS_NAMES[i]: round(float(rd[CLASS_NAMES[i]]["f1-score"]), 4) for i in range(NUM_LABELS)}
    try:
        cm = confusion_matrix(yt, yp)
        sns.heatmap(cm.astype("float")/cm.sum(1,keepdims=True), annot=True, fmt=".2f", xticklabels=CLASS_NAMES, yticklabels=CLASS_NAMES, cmap="Blues")
        plt.title("Confusion Matrix — GST Classifier v2")
        plt.tight_layout(); plt.savefig(EVAL_DIR/"confusion_matrix.png", dpi=150); plt.close()
        if wandb_run: import wandb; wandb.log({"confusion_matrix": wandb.Image(str(EVAL_DIR/"confusion_matrix.png"))})
    except Exception as e: print(f"  CM failed: {e}")
    try:
        logs = trainer.state.log_history
        te = [(l["epoch"],l["loss"]) for l in logs if "loss" in l and "eval_loss" not in l]
        ve = [(l["epoch"],l["eval_loss"],l.get("eval_f1_macro")) for l in logs if "eval_loss" in l]
        if te and ve:
            fig, ax = plt.subplots(1,2,figsize=(13,4))
            ax[0].plot([e for e,_ in te], [v for _,v in te], label="Train Loss")
            ax[0].plot([e for e,_,_ in ve], [v for _,v,_ in ve], label="Val Loss", marker="o")
            ax[0].set_xlabel("Epoch"); ax[0].set_ylabel("Loss"); ax[0].legend(); ax[0].grid(alpha=0.3)
            vf = [(e,f) for e,_,f in ve if f]
            if vf: ax[1].plot([e for e,_ in vf], [f for _,f in vf], marker="o", color="green"); ax[1].set_xlabel("Epoch"); ax[1].set_ylabel("Val F1"); ax[1].grid(alpha=0.3)
            plt.tight_layout(); plt.savefig(EVAL_DIR/"learning_curves.png", dpi=150); plt.close()
    except: pass
    return yp, yt, pcf

# =============================================================
# CELL 9 — Main pipeline
# =============================================================
def run_pipeline(use_wandb=True, do_cv=True):
    df_train = load_split(DATA_DIR/"train.csv")
    df_val = load_split(DATA_DIR/"val.csv")
    df_test = load_split(DATA_DIR/"test.csv")
    print(f"Train: {len(df_train)}  Val: {len(df_val)}  Test: {len(df_test)}")
    results = {}; wandb_run = None
    if use_wandb and os.environ.get("WANDB_API_KEY"):
        import wandb; wandb.login(key=os.environ["WANDB_API_KEY"])
        wandb_run = wandb.init(project="vyapaar-bandhu-gst-classifier-v2", name="muril-gst-v2-full", config={**HPARAMS})
        print(f"W&B: {wandb_run.url}")
    print("--- Baseline 1: Keyword ---")
    kw_f1 = eval_kw(df_test); results["keyword_baseline_f1"] = kw_f1
    if do_cv:
        print("--- 5-Fold CV ---")
        df_cv = pd.concat([df_train, df_val], ignore_index=True)
        skf = StratifiedKFold(5, shuffle=True, random_state=SEED)
        fold_f1s = []
        for f, (tr, vl) in enumerate(skf.split(df_cv["text"], df_cv["label_id"])):
            print(f"  Fold {f+1}/5...")
            t, tok = train_run(df_cv.iloc[tr]["text"].tolist(), df_cv.iloc[tr]["label_id"].tolist(), df_cv.iloc[vl]["text"].tolist(), df_cv.iloc[vl]["label_id"].tolist(), HPARAMS["model_name"], str(MODEL_DIR/f"cv-{f+1}"), f"cv-{f+1}", HPARAMS["num_epochs"], use_wandb)
            ds = GSTDataset(df_cv.iloc[vl]["text"].tolist(), df_cv.iloc[vl]["label_id"].tolist(), tok, HPARAMS["max_length"])
            pr = t.predict(ds); f1 = round(float(f1_score(df_cv.iloc[vl]["label_id"].values, np.argmax(pr.predictions,-1), average="macro", zero_division=0)), 4)
            fold_f1s.append(f1); print(f"  Fold {f+1} F1: {f1:.4f}")
            del t, tok
            if DEVICE=="cuda": torch.cuda.empty_cache()
            gc.collect()
            import shutil; shutil.rmtree(str(MODEL_DIR/f"cv-{f+1}"), ignore_errors=True)
        cm, cs = round(float(np.mean(fold_f1s)),4), round(float(np.std(fold_f1s)),4)
        results.update({"cv_f1_list":fold_f1s,"cv_f1_mean":cm,"cv_f1_std":cs})
        print(f"  CV F1: {cm} +- {cs}")
    else: cm, cs = 0, 0
    print("--- Baseline 2: xlm-roberta ---")
    xlm_t, xlm_tok = train_run(df_train["text"].tolist(), df_train["label_id"].tolist(), df_val["text"].tolist(), df_val["label_id"].tolist(), "xlm-roberta-base", str(MODEL_DIR/"xlm-baseline"), "xlm-baseline", 2, use_wandb)
    xlm_ds = GSTDataset(df_test["text"].tolist(), df_test["label_id"].tolist(), xlm_tok, HPARAMS["max_length"])
    xlm_pr = xlm_t.predict(xlm_ds)
    xlm_f1 = round(float(f1_score(df_test["label_id"].values, np.argmax(xlm_pr.predictions,-1), average="macro", zero_division=0)),4)
    print(f"  xlm-roberta Test F1: {xlm_f1:.4f}")
    results["xlm_baseline_test_f1"] = xlm_f1
    del xlm_t, xlm_tok
    if DEVICE=="cuda": torch.cuda.empty_cache()
    gc.collect()
    import shutil; shutil.rmtree(str(MODEL_DIR/"xlm-baseline"), ignore_errors=True)
    print("--- Final: MuRIL ---")
    final_t, final_tok = train_run(df_train["text"].tolist(), df_train["label_id"].tolist(), df_val["text"].tolist(), df_val["label_id"].tolist(), HPARAMS["model_name"], str(MODEL_DIR/"muril-gst-v2"), "muril-gst-v2-final", HPARAMS["num_epochs"], use_wandb)
    val_ds = GSTDataset(df_val["text"].tolist(), df_val["label_id"].tolist(), final_tok, HPARAMS["max_length"])
    val_pr = final_t.predict(val_ds)
    val_f1 = round(float(f1_score(df_val["label_id"].values, np.argmax(val_pr.predictions,-1), average="macro", zero_division=0)),4)
    results["val_f1"] = val_f1
    print("--- Test Evaluation ---")
    yp, yt, pcf = save_artifacts(final_t, final_tok, df_test, val_f1, wandb_run)
    test_f1 = round(float(f1_score(yt, yp, average="macro", zero_division=0)),4)
    results["test_f1"] = test_f1
    results["per_class_f1"] = pcf
    results["model"] = "muril-v2"
    final_t.save_model(str(MODEL_DIR/"muril-gst-v2"))
    final_tok.save_pretrained(str(MODEL_DIR/"muril-gst-v2"))
    inf = {"model":"meet136/muril-gst-classifier-v2","version":"v2","base_model":HPARAMS["model_name"],"confidence_threshold":HPARAMS["confidence_threshold"],"class_names":CLASS_NAMES}
    with open(MODEL_DIR/"muril-gst-v2"/"inference_config.json","w") as f: json.dump(inf,f,indent=2)
    json.dump(results, open(EVAL_DIR/"final_metrics.json","w"), indent=2)
    bl = {"keyword_rule_based":{"test_f1_macro":kw_f1},"xlm_roberta_base":{"test_f1_macro":xlm_f1},"muril_base_v2":{"cv_f1_macro_mean":cm,"cv_f1_macro_std":cs,"val_f1_macro":val_f1,"test_f1_macro":test_f1}}
    json.dump(bl, open(EVAL_DIR/"baselines.json","w"), indent=2)
    if wandb_run:
        import wandb
        wandb.log({"cv_f1_mean":cm,"cv_f1_std":cs,"val_f1_macro":val_f1,"test_f1_macro":test_f1,"keyword_baseline_f1":kw_f1,"xlm_baseline_test_f1":xlm_f1})
        wandb.log({"per_class_f1_table":wandb.Table(columns=["Class","F1"],data=[[c,pcf[c]] for c in CLASS_NAMES])})
        wandb_run.finish()
    print("="*65)
    print(f"CV F1: {cm} +- {cs} | Val F1: {val_f1} | Test F1: {test_f1}")
    print(f"Keyword: {kw_f1} | xlm: {xlm_f1} | MuRIL: {test_f1} (delta +{test_f1-max(kw_f1,xlm_f1):.4f})")
    print("="*65)
    return results

# =============================================================
# CELL 10 — Run
# =============================================================
results = run_pipeline(
    use_wandb=bool(os.environ.get("WANDB_API_KEY")),
    do_cv=True,
)

# =============================================================
# CELL 11 — Upload to HuggingFace
# =============================================================
def upload_hub():
    token = os.environ.get("HF_TOKEN")
    if not token: print("No HF_TOKEN. Skipping upload."); return
    api = huggingface_hub.HfApi(token=token)
    repo = "meet136/muril-gst-classifier-v2"
    api.create_repo(repo, exist_ok=True, token=token)
    api.upload_folder(folder_path=str(MODEL_DIR/"muril-gst-v2"), repo_id=repo, token=token)
    for a in ["confusion_matrix.png","classification_report.txt","final_metrics.json","baselines.json"]:
        p = EVAL_DIR/a
        if p.exists(): api.upload_file(path_or_fileobj=str(p), path_in_repo=f"eval/{a}", repo_id=repo, token=token)
    print(f"Uploaded to https://huggingface.co/{repo}")
upload_hub()




