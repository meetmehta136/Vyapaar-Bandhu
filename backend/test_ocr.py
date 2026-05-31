import os
from dotenv import load_dotenv
load_dotenv()
from app.services.ocr_service import extract_text_from_image_url

url = "https://raw.githubusercontent.com/Sparkfish/sample-invoices/main/sample_invoice_1.jpg"
sid = os.getenv("TWILIO_ACCOUNT_SID")
token = os.getenv("TWILIO_AUTH_TOKEN")

print("Testing OCR...")
res = extract_text_from_image_url(url, sid, token)
print("Result:")
print(res)
