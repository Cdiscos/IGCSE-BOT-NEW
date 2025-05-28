import os
import io
import random
import fitz  # PyMuPDF
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from pdf2image import convert_from_path
import os
import re

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

# Subject-specific Google Drive folder IDs (add more as needed)
FOLDER_IDS = {
    "math": "1GZUs34yS5dMmhO8Pm8rWokkS7VBQ5bqF",
    "biology": "1tCMnYUtHJ1jQAqmagUw1h5pWrtHxNwYE",
    "physics": "1Baa4OKIzjjtHzwcy1-xwjBuCDMLh2FlW",
    "chemistry": "1Ji-VoRovspqnZtvxhJW1CCdeMilxQBCX"
}

# Define theory paper patterns per subject
THEORY_PAPER_RULES = {
    "math": ["_qp_2", "_qp_4"],
    "biology": ["_qp_2", "_qp_4"],
    "physics": ["_qp_2", "_qp_4"],
    "chemistry": ["_qp_2", "_qp_4"]
}
def filter_theory_papers(files, subject):
    allowed = THEORY_PAPER_RULES.get(subject, [])
    return [f for f in files if any(rule in f['name'].lower() for rule in allowed)]


def get_drive_service():
    creds = service_account.Credentials.from_service_account_file(
        os.getenv("GOOGLE_DRIVE_CREDENTIALS"), scopes=SCOPES)
    return build('drive', 'v3', credentials=creds)

def list_pdfs_in_folder(service, folder_id):
    pdfs = []

    def recursive_scan(current_folder_id):
        query = f"'{current_folder_id}' in parents"
        items = service.files().list(q=query, fields="files(id, name, mimeType)").execute().get("files", [])
        for item in items:
            if item['mimeType'] == 'application/pdf':
                pdfs.append(item)
            elif item['mimeType'] == 'application/vnd.google-apps.folder':
                recursive_scan(item['id'])

    recursive_scan(folder_id)
    return pdfs

def filter_theory_papers(files, subject):
    allowed = THEORY_PAPER_RULES.get(subject, [])
    return [f for f in files if any(paper in f['name'].lower() for paper in allowed)]

def download_random_pdf(service, folder_id, subject):
    all_files = list_pdfs_in_folder(service, folder_id)

    filtered = filter_theory_papers(all_files, subject)
    if not filtered:
        return None, None

    # Pick a random theory file
    chosen = random.choice(filtered)
    file_id, file_name = chosen['id'], chosen['name']
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()

    # Sanitize filename
    safe_name = re.sub(r'[^\w\-_.()]', '_', file_name)
    os.makedirs('pdfs', exist_ok=True)
    path = os.path.join('pdfs', safe_name)

    fh.seek(0)  # 🧠 move pointer to start of the buffer
    with open(path, 'wb') as f:
     f.write(fh.read())



    return path, file_name



def extract_question_image_and_text(pdf_path):
    images = convert_from_path(pdf_path, first_page=1, last_page=1)
    img_path = pdf_path.replace(".pdf", ".png")
    images[0].save(img_path, 'PNG')
    doc = fitz.open(pdf_path)
    first_page_text = doc[0].get_text()
    doc.close()
    return img_path, first_page_text

def get_random_theory_question(subject="math"):
    subject = subject.lower()
    folder_id = FOLDER_IDS.get(subject)

    print(f"\n[DEBUG] Getting question for subject: {subject}")
    if not folder_id:
        print(f"[ERROR] No folder ID found for subject: {subject}")
        return None, None, None

    service = get_drive_service()
    print(f"[DEBUG] Using folder ID: {folder_id}")

    try:
        pdf_path, file_name = download_random_pdf(service, folder_id, subject)
        if not pdf_path:
            print("[ERROR] No suitable PDF found after filtering.")
            return None, None, None

        print(f"[DEBUG] Downloaded PDF: {file_name}")
        img_path, question_text = extract_question_image_and_text(pdf_path)
        print(f"[DEBUG] Extracted image path: {img_path}")
        return img_path, question_text, file_name
    except Exception as e:
        print(f"[EXCEPTION] Failed to get theory question: {e}")
        return None, None, None

def find_matching_mark_scheme(file_name, service, subject):
    if "_qp_" not in file_name:
        return None
    ms_name = file_name.replace("_qp_", "_ms_")
    folder_id = FOLDER_IDS.get(subject, None)
    if not folder_id:
        return None
    all_files = list_pdfs_in_folder(service, folder_id)
    for f in all_files:
        if ms_name.lower() in f['name'].lower():
            return f
    return None

def extract_mark_scheme_text(file_id, service):
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    with open("/mnt/data/temp_ms.pdf", "wb") as f:
        f.write(fh.getbuffer())

    doc = fitz.open("/mnt/data/temp_ms.pdf")
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text

def get_question_and_mark_scheme(subject="math"):
    subject = subject.lower()
    folder_id = FOLDER_IDS.get(subject)
    if not folder_id:
        return None, None, None, None

    service = get_drive_service()
    pdf_path, file_name = download_random_pdf(service, folder_id, subject)
    if not pdf_path:
        return None, None, None, None

    img_path, question_text = extract_question_image_and_text(pdf_path)

    mark_scheme_file = find_matching_mark_scheme(file_name, service, subject)
    mark_scheme_text = ""
    if mark_scheme_file:
        mark_scheme_text = extract_mark_scheme_text(mark_scheme_file['id'], service)

    return img_path, question_text, mark_scheme_text, file_name
