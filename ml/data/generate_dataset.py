"""
GST transaction classification dataset generator.
Multi-provider: Claude (primary) -> DeepSeek (fallback) -> Gemini (fallback) -> Template (last resort)
Output: ml/data/raw_synthetic.csv
"""

import csv
import json
import os
import random
import sys
import time
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", "backend", ".env"))

# ── Configuration ──────────────────────────────────────────────────────────

CLASSES = {
    0: "capital_goods",
    1: "input_services",
    2: "raw_materials",
    3: "motor_vehicles_conveyance",
    4: "food_beverages_catering",
    5: "club_health_beauty",
    6: "personal_employee_benefit",
}

CLASS_DESCRIPTIONS = {
    "capital_goods": (
        "machinery, equipment, computers, office furniture, factory tools, "
        "plant machinery, generators, office equipment"
    ),
    "input_services": (
        "accounting fees, legal services, courier, advertising, "
        "software subscriptions, consultancy fees, professional fees, "
        "maintenance contracts, security services"
    ),
    "raw_materials": (
        "fabric, steel, chemicals, packaging material, grain, "
        "industrial consumables, spare parts, lubricants"
    ),
    "motor_vehicles_conveyance": (
        "car purchase, truck hire, bike fuel, vehicle insurance, "
        "vehicle maintenance, taxi hire, transportation services"
    ),
    "food_beverages_catering": (
        "lunch for staff, tea/coffee supplies, Zomato orders, "
        "restaurant bills, canteen expenses, party catering, "
        "refreshment for meetings"
    ),
    "club_health_beauty": (
        "gym membership, health insurance, beauty salon, spa, "
        "club fees, yoga classes, wellness programs"
    ),
    "personal_employee_benefit": (
        "Diwali gifts for staff, travel allowance, mobile phone personal, "
        "home internet reimbursement, uniform for personal use, "
        "employee welfare expenses"
    ),
}

LANGUAGE_VARIANTS = {
    0: ("Hindi (Devanagari)", "pure Hindi in Devanagari script"),
    1: ("Transliterated Hindi", "transliterated Hindi in Roman script (like 'Dal kharida 5kg', 'Gaadi ki servicing')"),
    2: ("Gujarati", "Gujarati script"),
    3: ("Code-mixed Hindi-English", "code-mixed Hindi-English, most realistic for Indian SMEs — mix of Hindi and English words, e.g. 'Office furniture kharida', 'Zomato order for lunch meeting'"),
}

BATCH_SIZE = 50
BATCHES_PER_VARIANT_PER_CLASS = 5  # 5 * 50 = 250 per variant per class

OUTPUT_DIR = Path(__file__).parent
OUTPUT_FILE = OUTPUT_DIR / "raw_synthetic.csv"
PROGRESS_FILE = OUTPUT_DIR / "generation_progress.json"
PROVIDER_FILE = OUTPUT_DIR / "active_provider.txt"

MAX_RETRIES = 3
RETRY_DELAY = 2.0
API_DELAY = 0.5


# ── Prompt builder ─────────────────────────────────────────────────────────

def build_prompt(category: str, description: str, language_instruction: str) -> str:
    return f"""Generate 50 realistic Indian SME invoice line item descriptions for the category: {category}.

Category description: {description}

These are descriptions a shopkeeper or small business owner would write when entering expenses in their bookkeeping or billing software. Each description should be 1-15 words, highly varied, realistic.

Language: {language_instruction}

Requirements for variety:
- Include amounts occasionally (e.g., "Stationery rs 500", "Steel rod 2m @ 1200/m")
- Include vendor/brand names where realistic (e.g., "Tata Steel invoice", "Dell laptop for office")
- Include quantity/unit where appropriate (e.g., "5 kg dal", "2 reams A4 paper")
- Use realistic spelling variations including common misspellings
- Include some OCR-like noise occasionally (e.g., "0" instead of "O")
- Vary the structure: some should start with the item name, some with a vendor name, some with a transaction type

Do NOT include any explanation, preamble, or formatting outside the JSON array.
Return ONLY a JSON array of strings. No markdown, no code fences, just the raw JSON array."""


# ── Response parser (shared across providers) ──────────────────────────────

def parse_json_response(text: str) -> list[str] | None:
    text = text.strip()
    if text.startswith("```"):
        for fence in ["```json", "```JSON", "```"]:
            if text.startswith(fence):
                text = text[len(fence):]
                break
        idx = text.rfind("```")
        if idx != -1:
            text = text[:idx]
    text = text.strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, list) and len(parsed) > 0:
            return [str(item) for item in parsed]
    except json.JSONDecodeError:
        pass
    return None


# ── Provider 1: Claude (Anthropic) ────────────────────────────────────────

def call_claude(prompt: str) -> list[str] | None:
    import anthropic
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    client = anthropic.Anthropic(api_key=api_key)
    for attempt in range(MAX_RETRIES):
        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                temperature=0.8,
                messages=[{"role": "user", "content": prompt}],
            )
            result = parse_json_response(response.content[0].text)
            if result:
                return result
            print(f"  Claude parse error (attempt {attempt + 1})")
        except Exception as e:
            err_str = str(e).lower()
            if "401" in err_str or "unauthorized" in err_str or "permission" in err_str or "not found" in err_str:
                print(f"  Claude auth error — will switch provider")
                return None
            print(f"  Claude error (attempt {attempt + 1}): {e}")
        if attempt < MAX_RETRIES - 1:
            time.sleep(RETRY_DELAY * (2 ** attempt))
    return None


# ── Provider 2: DeepSeek via OpenRouter ────────────────────────────────────

def call_deepseek(prompt: str) -> list[str] | None:
    import openai
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return None

    client = openai.OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
    )
    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model="deepseek/deepseek-chat",
                max_tokens=4096,
                temperature=0.8,
                messages=[{"role": "user", "content": prompt}],
            )
            result = parse_json_response(response.choices[0].message.content or "")
            if result:
                return result
            print(f"  DeepSeek parse error (attempt {attempt + 1})")
        except Exception as e:
            err_str = str(e).lower()
            if "401" in err_str or "unauthorized" in err_str or "permission" in err_str:
                print(f"  DeepSeek auth error — will switch provider")
                return None
            print(f"  DeepSeek error (attempt {attempt + 1}): {e}")
        if attempt < MAX_RETRIES - 1:
            time.sleep(RETRY_DELAY * (2 ** attempt))
    return None


# ── Provider 3: Google Gemini ──────────────────────────────────────────────

def call_gemini(prompt: str) -> list[str] | None:
    import google.genai as genai
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None

    client = genai.Client(api_key=api_key)
    for attempt in range(MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
            )
            result = parse_json_response(response.text)
            if result:
                return result
            print(f"  Gemini parse error (attempt {attempt + 1})")
        except Exception as e:
            err_str = str(e).lower()
            if "401" in err_str or "unauthorized" in err_str or "permission" in err_str or "api key" in err_str:
                print(f"  Gemini auth error — will switch provider")
                return None
            print(f"  Gemini error (attempt {attempt + 1}): {e}")
        if attempt < MAX_RETRIES - 1:
            time.sleep(RETRY_DELAY * (2 ** attempt))
    return None


# ── Provider 4: Template-based (last resort) ──────────────────────────────

CLASS_TEMPLATES = {
    "capital_goods": [
        "Laptop {brand} for office use", "{brand} computer {spec}",
        "Office table and chair set", "Printer {brand} toner cartridge",
        "AC installation at factory", "Generator {kva}kva diesel",
        "Furniture for reception area", "CCTV camera {n}mp {qty} nos",
        "Server rack and cooling system", "UPS battery backup {va}va",
        "Office desk modular {qty} nos", "Factory machine spare part",
        "Electric wiring and fittings", "Water cooler for office",
        "LED monitor {brand} {inch}inch", "Biometric attendance machine",
        "Fire extinguisher {qty} kg", "Air conditioner split {ton}ton",
        "Photocopy machine {brand}", "Industrial fan {inch}inch exhaust",
        "Machine {brand} pump motor", "Testing equipment multimeter",
        "Welding machine {brand}", "Compressor {hp}hp industrial",
        "Office partition work {sqft}sqft",
    ],
    "input_services": [
        "Accounting fees for {year} audit", "Legal consultation fees",
        "Courier charges {qty} parcels", "GST filing service fees",
        "Software subscription {app} monthly", "Advertising in {paper} newspaper",
        "Website maintenance monthly", "Digital marketing {platform} campaign",
        "Consultancy fees for project", "Security service {month} month",
        "SEO services for website", "Cloud hosting fees {provider}",
        "Email marketing campaign", "Social media management fees",
        "IT support contract annual", "Content writing services",
        "Graphic design for brochure", "Video production ad shoot",
        "PR and media monitoring", "Market research report purchase",
        "Training program registration fees", "Audit fees statutory",
        "Tax consultant retainer fees", "Patent filing services",
        "Insurance brokerage fees",
    ],
    "raw_materials": [
        "Steel rod {size}mm {qty} ton", "Cement {brand} {qty} bag",
        "Cotton fabric {quality} grade {qty}m", "Chemical {chem} {qty}ltr",
        "Packaging boxes corrugated {qty} pcs", "Timber wood {type} {qty}cft",
        "Paint {brand} {color} {qty}ltr", "Plastic granules {grade} grade",
        "Aluminum sheet {gauge}mm {qty} sheet", "Bricks {qty} thousand",
        "Sand fine {qty} ton truck", "Crush stone aggregate {size}mm",
        "Thread polyester {denier}d {qty} kg", "Leather {type} {qty}sqft",
        "Glass sheet {thick}mm {qty} sqft", "Rubber {type} raw material",
        "Paper roll {gsm}gsm {qty} kg", "Dye {color} {qty} kg industrial",
        "Copper wire {swg} swg {qty} kg", "PVC pipe {dia}inch {qty} meter",
        "Wheat grain {grade} {qty} quintal", "Sugar {grade} {qty} kg bulk",
        "Edible oil refined {qty} ltr", "Spices {type} ground {qty} kg",
        "Fertilizer {grade} {qty} bag",
    ],
    "motor_vehicles_conveyance": [
        "Car {brand} {model} purchase new", "Truck hiring for goods transport {route}",
        "Bike fuel petrol {ltr} ltr", "Vehicle insurance premium renewal",
        "Car servicing and maintenance", "Taxi fare from {from} to {to}",
        "Tyre replacement {qty} nos", "Car wash and detailing",
        "CNG refill {kg} kg for taxi", "Transportation charges goods truck",
        "Vehicle spare parts {part}", "Engine oil change {brand}",
        "Parking charges monthly", "Toll tax paid {route} highway",
        "Driver salary for {month}", "Vehicle registration renewal fee",
        "GPS tracker installation", "Truck body repair denting painting",
        "Car battery replacement {brand}", "Wheel alignment balancing",
        "Speed governor installation", "Fitness certificate renewal truck",
        "Number plate HSRP new", "Loading unloading charges",
        "Cold storage transport charges",
    ],
    "food_beverages_catering": [
        "Lunch for staff {qty} persons", "Tea coffee supplies for office",
        "Zomato order for team meeting", "Catering for {event} party",
        "Restaurant bill client dinner", "Refreshment for board meeting",
        "Canteen supplies monthly", "Drinking water cans {qty} nos",
        "Office birthday cake", "Snacks for training session",
        "Biscuits and namkeen for pantry", "Party catering diwali celebration",
        "Lunch meeting {qty} pax", "Chai nashta for staff",
        "Water cooler maintenance", "Disposable plates cups for party",
        "Annual day dinner catering", "Fruits for office pantry",
        "Cold drinks for summer supply", "Festival sweets distribution",
        "Breakfast meeting arrangement", "Guest lunch charges",
        "Employee farewell party", "Milestone celebration team lunch",
        "Monthly team dinner outing",
    ],
    "club_health_beauty": [
        "Gym membership annual fee", "Health insurance premium family",
        "Beauty salon services for staff function", "Spa voucher gift",
        "Yoga class fees monthly", "Club membership fees",
        "Wellness program registration", "Sports equipment for recreation room",
        "Health checkup camp expenses", "Swimming pool membership",
        "Fitness trainer consultation", "Massage therapy session",
        "Salon visit for event grooming", "Meditation workshop fees",
        "Weight loss program enrollment", "Personal trainer charges",
        "Gym equipment treadmill purchase", "Protein supplements purchase",
        "Steam bath membership fees", "Tennis court booking annual",
        "Golf club membership fees", "Ayurvedic massage therapy",
        "Hair styling for corporate event", "Facial and skincare products",
        "Body massage oil and supplies",
    ],
    "personal_employee_benefit": [
        "Diwali gifts for all staff members", "Travel allowance {month} month",
        "Mobile phone personal bill reimbursement", "Home internet bill reimbursement",
        "Uniform stitching for {qty} employees", "Employee welfare fund contribution",
        "Festival bonus advance", "Medical reimbursement employee",
        "Education allowance for staff children", "Marriage gift for employee",
        "LTA claim for {year}", "Leave travel concession",
        "Birthday gift for team member", "Employee engagement activity",
        "Team building retreat expenses", "Relocation allowance for transfer",
        "Vehicle fuel reimbursement", "Mobile handset personal",
        "Club fees reimbursement employee", "Newspaper subscription home delivery",
        "Food coupon for employee", "Gift voucher for employee recognition",
        "Transport allowance monthly", "Children school fees reimbursement",
        "Housing rent allowance admin",
    ],
}

BRANDS = {
    "capital_goods": ["Dell", "HP", "Lenovo", "Apple", "Samsung", "LG", "Godrej", "Voltas", "Bluestar", "Daikin", "Crompton", "Bajaj", "Siemens", "Bosch", "Mitsubishi"],
    "input_services": ["Google", "Microsoft", "Amazon AWS", "HubSpot", "Zoho", "Tally", "QuickBooks", "Freshworks", "Salesforce", "Mailchimp"],
    "raw_materials": ["Tata Steel", "JSW", "Ultratech", "ACC", "Ambuja", "Asian Paints", "Berger", "Nerolac", "SRF", "Grasim", "Reliance", "Birlasoft", "Arvind Mills"],
    "motor_vehicles_conveyance": ["Maruti", "Hyundai", "Tata", "Mahindra", "Honda", "Toyota", "Bajaj", "Hero", "TVS", "Ashok Leyland", "Eicher"],
    "food_beverages_catering": ["Amul", "Nestle", "Britannia", "Parle", "Haldiram", "MTR", "Tata Consumer", "ITC", "Mother Dairy", "Patanjali"],
    "club_health_beauty": ["Cultfit", "Gold's Gym", "Talwalkars", "VLCC", "Kaya", "Lakme", "Lotus Herbals", "Forest Essentials", "Biotique", "Himalaya"],
    "personal_employee_benefit": [],
}

UNITS = ["kg", "g", "ltr", "ml", "pcs", "nos", "box", "carton", "m", "sqft", "ton", "quintal", "dozen", "pair", "set", "pack"]

CITIES = ["Mumbai", "Delhi", "Bangalore", "Ahmedabad", "Surat", "Vadodara", "Rajkot", "Pune", "Chennai", "Kolkata", "Hyderabad", "Jaipur", "Lucknow", "Indore", "Bhopal"]

HINDI_ITEMS = {
    "capital_goods": ["कंप्यूटर", "लैपटॉप", "प्रिंटर", "फर्नीचर", "मशीनरी", "ऑफिस का सामान", "बिजली का उपकरण", "एसी", "जनरेटर", "सीसीटीवी कैमरा"],
    "input_services": ["लेखा शुल्क", "कानूनी सलाह", "कूरियर चार्ज", "सॉफ्टवेयर", "विज्ञापन", "कंसल्टेंसी फीस", "ऑडिट फीस", "टैक्स फाइलिंग"],
    "raw_materials": ["कच्चा माल", "स्टील", "सीमेंट", "केमिकल", "पैकिंग सामग्री", "कपड़ा", "लकड़ी", "पेंट", "प्लास्टिक दाना"],
    "motor_vehicles_conveyance": ["गाड़ी", "कार", "बाइक", "पेट्रोल", "डीज़ल", "ट्रक", "वाहन बीमा", "टायर", "सर्विसिंग"],
    "food_beverages_catering": ["खाना", "भोजन", "चाय", "नाश्ता", "कैटरिंग", "लंच", "पार्टी", "मिठाई", "पानी"],
    "club_health_beauty": ["जिम", "स्पा", "योगा", "हेल्थ इंश्योरेंस", "ब्यूटी सैलून", "क्लब"],
    "personal_employee_benefit": ["गिफ्ट", "भत्ता", "मोबाइल", "इंटरनेट", "वर्दी", "कर्मचारी कल्याण", "बोनस"],
}

GUJARATI_ITEMS = {
    "capital_goods": ["કમ્પ્યુટર", "લેપટોપ", "પ્રિન્ટર", "ફર્નિચર", "મશીનરી", "ઓફિસનો સામાન", "એસી", "જનરેટર", "સીસીટીવી કેમેરા"],
    "input_services": ["હિસાબી ફી", "કાનૂની સલાહ", "કુરિયર ચાર્જ", "સોફ્ટવેર", "જાહેરાત", "કન્સલ્ટન્સી ફી", "ઓડિટ ફી"],
    "raw_materials": ["કાચો માલ", "સ્ટીલ", "સિમેન્ટ", "કેમિકલ", "પેકિંગ સામગ્રી", "કાપડ", "લાકડું", "પેઇન્ટ"],
    "motor_vehicles_conveyance": ["ગાડી", "કાર", "બાઇક", "પેટ્રોલ", "ડીઝલ", "ટ્રક", "વાહન વીમો", "ટાયર"],
    "food_beverages_catering": ["ખાવાનું", "ભોજન", "ચા", "નાસ્તો", "કેટરિંગ", "લંચ", "પાર્ટી", "મિઠાઇ"],
    "club_health_beauty": ["જિમ", "સ્પા", "યોગા", "હેલ્થ ઇન્શ્યોરન્સ", "બ્યુટી સલૂન"],
    "personal_employee_benefit": ["ગિફ્ટ", "ભથ્થું", "મોબાઇલ", "ઇન્ટરનેટ", "ગણવેશ", "કર્મચારી કલ્યાણ"],
}

TRANSLITERATED_MAP = {
    "capital_goods": ["computer kharida", "laptop liya", "printer kharida", "office furniture", "machine kharida", "factory ka samaan", "AC lagwaya"],
    "input_services": ["accounting fee diya", "courier bheja", "software ka subscription", "advertising kharcha", "legal fees", "consultancy fees"],
    "raw_materials": ["steel kharida", "cement mangaaya", "chemical liya", "packing material", "kapda kharida", "wood mangaaya"],
    "motor_vehicles_conveyance": ["gaadi kharidi", "car ki servicing", "petrol dalwaya", "diesel bharwaya", "truck hire kiya", "bike ka insurance"],
    "food_beverages_catering": ["khana order kiya", "chai nashta", "lunch party", "catering karwaya", "restaurant ka bill", "canteen kharcha"],
    "club_health_beauty": ["gym membership liya", "spa gaya", "yoga class", "health insurance", "saloon gaya"],
    "personal_employee_benefit": ["diwali gift diya", "travel allowance", "mobile bill bhara", "internet recharge", "uniform silwaya"],
}


def call_template(prompt: str) -> list[str] | None:
    """Generate data from templates when all APIs fail."""
    category_key = None
    for cid, cname in CLASSES.items():
        if cname.replace("_", " ").title() in prompt or cname in prompt:
            category_key = cname
            break
    if not category_key:
        for cname in CLASSES.values():
            if cname.replace("_", " ") in prompt.lower():
                category_key = cname
                break
    if not category_key:
        category_key = "capital_goods"

    lang_instruction = prompt
    is_gujarati = "Gujarati" in lang_instruction and "script" in lang_instruction
    is_hindi_dev = "Devanagari" in lang_instruction
    is_transliterated = "transliterated" in lang_instruction.lower()
    is_codemixed = not is_gujarati and not is_hindi_dev and not is_transliterated

    samples = []
    templates = CLASS_TEMPLATES.get(category_key, CLASS_TEMPLATES["capital_goods"])
    brands = BRANDS.get(category_key, ["Generic"])

    for i in range(BATCH_SIZE):
        if is_hindi_dev:
            items = HINDI_ITEMS.get(category_key, ["सामान"])
            base = random.choice(items)
            amt = random.randint(100, 50000)
            text = f"{base} रु {amt}"
        elif is_gujarati:
            items = GUJARATI_ITEMS.get(category_key, ["સામાન"])
            base = random.choice(items)
            amt = random.randint(100, 50000)
            text = f"{base} રૂ {amt}"
        elif is_transliterated:
            items = TRANSLITERATED_MAP.get(category_key, ["saman kharida"])
            base = random.choice(items)
            amt = random.randint(100, 50000)
            text = f"{base} rs {amt}"
        else:
            template = random.choice(templates)
            fill = {
                "brand": random.choice(brands) if brands else "Generic",
                "qty": str(random.randint(1, 50)),
                "ltr": str(random.randint(1, 20)),
                "kg": str(random.randint(1, 100)),
                "inch": str(random.choice([15, 17, 19, 21, 24, 27, 32, 43, 55])),
                "ton": str(random.choice([1, 1.5, 2, 2.5, 3])),
                "hp": str(random.choice([1, 2, 3, 5, 7.5, 10])),
                "kva": str(random.choice([5, 10, 15, 20, 25, 50])),
                "va": str(random.choice([600, 800, 1000, 1500, 2000])),
                "sqft": str(random.randrange(50, 5000, 50)),
                "size": str(random.choice([6, 8, 10, 12, 16, 20, 25, 32])),
                "mm": str(random.choice([2, 3, 4, 5, 6, 8, 10, 12])),
                "gauge": str(random.choice([16, 18, 20, 22, 24, 26])),
                "swg": str(random.choice([12, 14, 16, 18, 20, 22])),
                "gsm": str(random.choice([60, 70, 80, 100, 120, 150, 200])),
                "dia": str(random.choice([0.5, 0.75, 1, 1.5, 2, 3, 4, 6])),
                "spec": str(random.choice(["i5", "i7", "Ryzen 5", "Ryzen 7", "M1", "M2"])),
                "n": str(random.choice([2, 3, 4, 5, 8])),
                "mp": str(random.choice([2, 4, 8, 12])),
                "app": random.choice(["QuickBooks", "Tally", "Zoho", "Freshbooks", "Salesforce", "HubSpot", "Mailchimp", "Canva", "Slack", "Asana"]),
                "paper": random.choice(["Times of India", "Gujarat Samachar", "Sandesh", "Divya Bhaskar", "Indian Express", "Hindustan Times", "Lokmat"]),
                "platform": random.choice(["Google Ads", "Facebook Ads", "Instagram", "LinkedIn", "Twitter", "YouTube"]),
                "provider": random.choice(["AWS", "Google Cloud", "Azure", "Digital Ocean", "Linode", "Vultr"]),
                "chem": random.choice(["Hydrochloric Acid", "Caustic Soda", "Acetone", "Methanol", "Sulfuric Acid", "Glycerin", "Ethanol"]),
                "grade": random.choice(["A", "B", "Premium", "Industrial", "Food", "Excellent", "Standard"]),
                "quality": random.choice(["Premium", "Standard", "Economy", "Superior", "First"]),
                "color": random.choice(["White", "Red", "Blue", "Green", "Yellow", "Black", "Brown", "Grey"]),
                "type": random.choice(["Teak", "Sal", "Pine", "Mahogany", "Sesame", "Mustard", "Cumin", "Turmeric", "Red Chili"]),
                "thick": str(random.choice([3, 4, 5, 6, 8, 10, 12])),
                "denier": str(random.choice([30, 50, 70, 100, 150, 200, 300])),
                "part": random.choice(["brake pad", "clutch plate", "air filter", "oil filter", "spark plug", "battery", "shock absorber", "belt"]),
                "from": random.choice(CITIES),
                "to": random.choice(CITIES),
                "route": f"{random.choice(CITIES)}-{random.choice(CITIES)}",
                "month": random.choice(["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]),
                "event": random.choice(["Diwali", "Holi", "birthday", "anniversary", "New Year", "team meeting", "conference", "training", "seminar"]),
                "year": str(random.choice([2024, 2025, 2026])),
            }
            try:
                text = template.format(**fill)
            except KeyError:
                text = template
            # Add amount to some
            if random.random() < 0.4:
                amt = random.choice([random.randint(100, 50000), random.randint(50000, 500000)])
                text = f"{text} Rs {amt}"

        if random.random() < 0.15:
            noise = {"0": "O", "O": "0", "1": "l", "l": "1", "5": "S", "S": "5", "8": "B", "B": "8"}
            chars = list(text)
            for j in range(len(chars)):
                if random.random() < 0.05 and chars[j] in noise:
                    chars[j] = noise[chars[j]]
            text = "".join(chars)

        if text not in samples:
            samples.append(text)

    return samples if samples else None


# ── Provider chain ─────────────────────────────────────────────────────────

PROVIDERS = [
    ("Claude", call_claude),
    ("DeepSeek", call_deepseek),
    ("Gemini", call_gemini),
    ("Template", call_template),
]


def read_active_provider() -> str | None:
    if PROVIDER_FILE.exists():
        return PROVIDER_FILE.read_text().strip()
    return None


def write_active_provider(name: str):
    PROVIDER_FILE.write_text(name)


def call_with_fallback(prompt: str) -> tuple[list[str] | None, str]:
    active = read_active_provider()
    start_idx = 0
    if active:
        for i, (name, _) in enumerate(PROVIDERS):
            if name == active:
                start_idx = i
                break

    for i in range(start_idx, len(PROVIDERS)):
        name, func = PROVIDERS[i]
        print(f"  [{name}] Calling...")
        result = func(prompt)
        if result:
            if name != active:
                write_active_provider(name)
            return result, name
        if i < len(PROVIDERS) - 1:
            print(f"  [{name}] Failed, trying next provider...")
    return None, "All failed"


# ── Progress helpers ───────────────────────────────────────────────────────

def load_progress() -> dict:
    if PROGRESS_FILE.exists():
        return json.loads(PROGRESS_FILE.read_text())
    return {"completed_batches": []}


def save_progress(progress: dict):
    PROGRESS_FILE.write_text(json.dumps(progress, indent=2))


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("GST Dataset Generator — Multi-Provider")
    print("=" * 60)
    print(f"Target: {len(CLASSES)} classes × {len(LANGUAGE_VARIANTS)} languages × {BATCHES_PER_VARIANT_PER_CLASS} batches × {BATCH_SIZE} samples")
    print(f"Total target: {len(CLASSES) * len(LANGUAGE_VARIANTS) * BATCHES_PER_VARIANT_PER_CLASS * BATCH_SIZE} samples")
    print()

    progress = load_progress()
    completed = set(tuple(b) for b in progress.get("completed_batches", []))

    all_rows = []
    # Load already generated data
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                all_rows.append(row)
        print(f"Loaded {len(all_rows)} existing samples from {OUTPUT_FILE.name}")
        print(f"Completed batches: {len(completed)}")

    total_batches = len(CLASSES) * len(LANGUAGE_VARIANTS) * BATCHES_PER_VARIANT_PER_CLASS
    provider_usage = Counter()

    with tqdm(total=total_batches, desc="Generating", unit="batch") as pbar:
        for class_id, class_name in CLASSES.items():
            for lang_id, (lang_name, lang_instruction) in LANGUAGE_VARIANTS.items():
                for batch_num in range(BATCHES_PER_VARIANT_PER_CLASS):
                    batch_key = (class_id, lang_id, batch_num)

                    if batch_key in completed:
                        pbar.update(1)
                        continue

                    prompt = build_prompt(
                        class_name.replace("_", " ").title(),
                        CLASS_DESCRIPTIONS[class_name],
                        lang_instruction,
                    )

                    pbar.set_description(
                        f"{class_name[:12]:12s} {lang_name[:16]:16s} batch {batch_num + 1}"
                    )

                    samples, provider = call_with_fallback(prompt)
                    if samples is None:
                        print(f"\n  ALL providers failed for batch {batch_key}")
                        time.sleep(RETRY_DELAY)
                        continue

                    provider_usage[provider] += 1
                    for text in samples:
                        all_rows.append({
                            "text": text,
                            "label": class_name,
                            "label_id": class_id,
                            "language_variant": lang_name,
                            "language_id": lang_id,
                            "is_synthetic": True,
                        })

                    completed.add(batch_key)
                    save_progress({"completed_batches": [list(b) for b in completed]})

                    tmp_rows = []
                    seen = set()
                    for r in all_rows:
                        key = (r["text"], r["label"], r["language_variant"])
                        if key not in seen:
                            seen.add(key)
                            tmp_rows.append(r)
                    all_rows = tmp_rows

                    fieldnames = ["text", "label", "label_id", "language_variant", "language_id", "is_synthetic"]
                    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerows(all_rows)

                    pbar.update(1)
                    time.sleep(API_DELAY)

    print(f"\n{'='*60}")
    print(f"Dataset generation complete!")
    print(f"Total unique samples: {len(all_rows)}")
    print(f"Saved to: {OUTPUT_FILE}")
    print(f"\nProvider usage: {dict(provider_usage)}")
    print(f"\nClass distribution:")
    class_counts = Counter(r["label"] for r in all_rows)
    for label, count in sorted(class_counts.items()):
        print(f"  {label:40s} {count:5d}")
    print(f"\nLanguage variant distribution:")
    lang_counts = Counter(r["language_variant"] for r in all_rows)
    for lang, count in sorted(lang_counts.items()):
        print(f"  {lang:30s} {count:5d}")

    print(f"\nSample outputs (5 per class):")
    for class_name in sorted(set(r["label"] for r in all_rows)):
        print(f"\n  [{class_name}]")
        samples = [r for r in all_rows if r["label"] == class_name][:5]
        for s in samples:
            print(f"    ({s['language_variant'][:18]:>18s}) {s['text']}")


if __name__ == "__main__":
    main()
