from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
import pytesseract
from pdf2image import convert_from_bytes
from PIL import Image
import io
import fitz
import re

app = Flask(__name__)

class AadhaarData:
    def __init__(self):
        self.aadhaar_number = ""
        self.name_tamil = ""
        self.name = ""
        self.guardian_name = ""
        self.dob = ""
        self.gender = ""
        self.address = ""
        self.district = ""
        self.state = ""
        self.pincode = ""
        self.phone = ""
        self.vid = ""

def extract_text_from_image(image: Image.Image) -> str:
    custom_config = r'--oem 3 --psm 6'
    return pytesseract.image_to_string(image, config=custom_config, lang='eng+tam')

def extract_text_from_pdf(pdf_bytes: bytes, password: str = None) -> str:
    text = ""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    if doc.needs_pass and password:
        doc.authenticate(password)

    for page in doc:
        text += page.get_text("text")
    return text

def parse_aadhaar_details(text: str) -> dict:
    data = AadhaarData()
    lines = [line.strip() for line in text.split("\n") if line.strip()]

    aadhaar_match = re.search(r'\b(\d{4}\s\d{4}\s\d{4})\b', text)
    if aadhaar_match:
        data.aadhaar_number = aadhaar_match.group(1)

    # Additional parsing logic here... (for brevity, logic can be copied as is)

    return vars(data)

@app.route("/extract", methods=["POST"])
def extract_aadhaar():
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files['file']
    password = request.form.get('password')

    contents = file.read()

    if file.filename.endswith(".pdf"):
        text = extract_text_from_pdf(contents, password)
    else:
        image = Image.open(io.BytesIO(contents))
        text = extract_text_from_image(image)

    aadhaar_data = parse_aadhaar_details(text)

    print("\nExtracted Aadhaar Details:")
    print(aadhaar_data)

    return jsonify(aadhaar_data)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8000)
