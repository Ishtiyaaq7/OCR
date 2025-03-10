from flask import Flask, request, jsonify
from flask_cors import CORS  # Import Flask-CORS for handling CORS
from pydantic import BaseModel
import pytesseract
from pdf2image import convert_from_bytes
from PIL import Image
import io
import fitz  # PyMuPDF
import re

app = Flask(__name__)
CORS(app)  # Enable CORS for the entire app

class AadhaarData(BaseModel):
    aadhaar_number: str = ""
    name_tamil: str = ""  
    name: str = ""        
    guardian_name: str = ""
    dob: str = ""
    gender: str = ""
    address: str = ""
    district: str = ""
    state: str = ""
    pincode: str = ""
    phone: str = ""
    vid: str = ""

# Extract text from image using Tesseract OCR
def extract_text_from_image(image: Image.Image) -> str:
    custom_config = r'--oem 3 --psm 6'
    return pytesseract.image_to_string(image, config=custom_config, lang='eng+tam')

# Extract text from PDF using PyMuPDF
def extract_text_from_pdf(pdf_bytes: bytes, password: str = None) -> str:
    text = ""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    if doc.needs_pass and password:
        doc.authenticate(password)
    
    for page in doc:
        text += page.get_text("text")
    return text

# Extract name logic
def extract_name_from_text(lines):
    unwanted_phrases = [
        "Digitally signed by DS Unique",
        "Identification Authority of India",
        "Government of India",
        "Signature Not Verified",
    ]

    for line in lines:
        clean_line = line.strip()
        if (
            re.match(r'^[A-Za-z\s\'-]+$', clean_line)
            and len(clean_line.split()) > 1
            and all(phrase.lower() not in clean_line.lower() for phrase in unwanted_phrases)
        ):
            name_part = re.split(r'\s*(?:S/O|C/O|W/O|D/O)\s*', clean_line, flags=re.IGNORECASE)[0]
            name_part = re.sub(r'\s+[CWSD]\s*$', '', name_part).strip()
            name_part = re.sub(r'\s+', ' ', name_part)
            return name_part
    return ""

# Parse Aadhaar details
def parse_aadhaar_details(text: str) -> AadhaarData:
    data = AadhaarData()
    lines = [line.strip() for line in text.split("\n") if line.strip()]

    # Aadhaar Number
    aadhaar_match = re.search(r'\b(\d{4}\s\d{4}\s\d{4})\b', text)
    if aadhaar_match:
        data.aadhaar_number = aadhaar_match.group(1)

    # VID
    vid_match = re.search(r'VID[:\s]*(\d{4}\s\d{4}\s\d{4}\s\d{4})', text)
    if vid_match:
        data.vid = vid_match.group(1)

    # Name (Tamil and English)
    tamil_name_match = re.search(r'([\u0B80-\u0BFF\s]+)\n([A-Za-z\s\'-]+)', text)
    if tamil_name_match:
        data.name_tamil = tamil_name_match.group(1).strip()
        data.name = tamil_name_match.group(2).strip().replace("\n", " ")
        data.name = re.split(r'\s*(?:S/O|C/O|W/O|D/O)\s*', data.name, flags=re.IGNORECASE)[0].strip()
        data.name = re.sub(r'\s+[CWSD]\s*$', '', data.name).strip()
        data.name = re.sub(r'\s+', ' ', data.name)

    if not data.name:
        data.name = extract_name_from_text(lines)

    # Guardian Name
    guardian_match = re.search(r'(S/o|C/o|D/o|W/o)[.:]?\s*([A-Za-z\s\'-]+)', text, re.IGNORECASE)
    if guardian_match:
        data.guardian_name = guardian_match.group(2).strip()

    # DOB
    dob_match = re.search(r'(DOB|Date of Birth|D\\.O\\.B)[:\s]*?(\d{1,2}[-/]\d{1,2}[-/]\d{4})', text, re.IGNORECASE)
    if dob_match:
        data.dob = dob_match.group(2).replace('-', '/')

    # Gender
    gender_match = re.search(r'\b(Male|Female|Transgender|M|F|T)\b', text, re.IGNORECASE)
    if gender_match:
        data.gender = gender_match.group(1).capitalize()

    # Address
    address_match = re.search(r'(?i)address[:\s]*(.*?)(?=\nDistrict|\nState|\n\d{6}|\nVID|\nDigitally|$)', text, re.DOTALL)
    if address_match:
        address_text = re.sub(r'(S/o|C/o|D/o|W/o)[.:]?\s*[A-Za-z\s\'-]+', '', address_match.group(1).strip(), flags=re.IGNORECASE)
        address_text = re.sub(r'\b\d{4}\s\d{4}\s\d{4}\b', '', address_text)
        address_text = re.sub(r'PO:.*?,', '', address_text)
        address_text = re.sub(r'(?i)\b(dist|state)\b.*', '', address_text)
        address_text = re.sub(r'\n+', ' ', address_text).strip()
        address_text = re.sub(r'\s+', ' ', address_text).strip()
        data.address = address_text

    # District
    district_match = re.search(r'District[:\s]*(.*)', text, re.IGNORECASE)
    if district_match:
        data.district = district_match.group(1).strip().replace(',', '')

    # State
    state_match = re.search(r'State[:\s]*(.*)', text, re.IGNORECASE)
    if state_match:
        data.state = state_match.group(1).strip()

    # Pincode
    pincode_match = re.search(r'\b(\d{6})\b', text)
    if pincode_match:
        data.pincode = pincode_match.group(1)

    # Phone Number
    phone_match = re.search(r'\b(\d{10})\b', text)
    if phone_match:
        data.phone = phone_match.group(1)

    return data

@app.route('/extract', methods=['POST'])
def extract_aadhaar():
    file = request.files['file']
    password = request.form.get('password', None)
    contents = file.read()

    if file.filename.endswith(".pdf"):
        text = extract_text_from_pdf(contents, password)
    else:
        image = Image.open(io.BytesIO(contents))
        text = extract_text_from_image(image)

    aadhaar_data = parse_aadhaar_details(text)

    # Print formatted JSON to terminal
    print("\nExtracted Aadhaar Details:")
    print(aadhaar_data.model_dump_json(indent=4))

    return jsonify(aadhaar_data.dict())

if __name__ == "__main__":
    app.run(debug=True, host='127.0.0.1', port=5000)
