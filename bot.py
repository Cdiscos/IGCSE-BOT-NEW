import os
import io
import re
import random
import threading
import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, Modal, TextInput
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build, MediaFileUpload
from collections import defaultdict
import pdfplumber
from PIL import Image, ImageDraw
from flask import Flask, jsonify

# --- Load environment ---
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS")

# --- Discord bot setup ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

user_scores = defaultdict(int)
last_question = {}

SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive.file"
]
creds = service_account.Credentials.from_service_account_file(GOOGLE_CREDENTIALS, scopes=SCOPES)
drive_service = build("drive", "v3", credentials=creds)

SUBJECT_ALIASES = {
    "math": "0580", "mathematics": "0580",
    "biology": "0610", "chemistry": "0620", "physics": "0625",
    "ict": "0417", "computerscience": "0478", "cs": "0478",
    "literature": "0475", "accounting": "0452", "economics": "0455",
    "business": "0450", "business studies": "0450", "urdu": "3248"
}
EXCLUDED_SUBJECTS = {"english", "history", "geography", "french", "global"}

# Google Drive folders for each subject
SUBJECT_DRIVE_LINKS = {
    "accounting": "https://drive.google.com/drive/folders/1qelX7sXIIxdk_v_bLxJRkbpfuBOfDFno",
    "biology": "https://drive.google.com/drive/folders/1mrh6_cdYUKTGvEN5UyBsLMacRzdsQQtz",
    "business": "https://drive.google.com/drive/folders/1JKujjCHyUhNM5y8tfonFrZ7ZPS8oH6Fe",
    "business studies": "https://drive.google.com/drive/folders/1JKujjCHyUhNM5y8tfonFrZ7ZPS8oH6Fe",
    "chemistry": "https://drive.google.com/drive/folders/1AgLXQz-dPLtpyvDgRVLnQtS7NVoUjtPp",
    "math": "https://drive.google.com/drive/folders/1HlOXZYhJhEhz9e8KXVoOSr9lM9RQbXQ3",
    "mathematics": "https://drive.google.com/drive/folders/1HlOXZYhJhEhz9e8KXVoOSr9lM9RQbXQ3",
    "physics": "https://drive.google.com/drive/folders/1_jnbXYTAVVVDvS-uHs4KQYbyZke5V5Bl",
    "urdu": "https://drive.google.com/drive/folders/1fXFImXjkvudt3FlqLTH8jCDdZX_LLfDf"
}

def crop_footer(pil_image, footer_height=70):
    width, height = pil_image.size
    draw = ImageDraw.Draw(pil_image)
    draw.rectangle((0, height - footer_height, width, height), fill="white")
    return pil_image

def extract_question_number(text):
    match = re.search(r'\b(?:Question\s*)?(\d{1,2})[.)]', text)
    return match.group(1) if match else None

file_cache = {}
note_folder_cache = {}  # board_subject: folder_id

async def fetch_drive_files():
    global file_cache
    file_cache = {}
    for subject, code in SUBJECT_ALIASES.items():
        if subject in EXCLUDED_SUBJECTS:
            continue
        folder_id = os.getenv(f"FOLDER_{code}")
        if not folder_id:
            continue
        file_cache[subject] = []
        response = drive_service.files().list(
            q=f"'{folder_id}' in parents and mimeType='application/pdf'",
            fields="files(id, name)").execute()
        for f in response.get("files", []):
            name = f["name"].lower()
            if "qp" not in name:
                continue
            if "paper 2" in name or "paper 3" in name:
                if "ict" in subject or "accounting" in subject or "economics" in subject:
                    continue
            if any(k in name for k in ["practical", "alternative", "geography", "history", "english", "french", "global"]):
                continue
            file_cache[subject].append((f["id"], f["name"]))

async def download_file(file_id):
    request = drive_service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = drive_service._http.request(request.uri)
    fh.write(downloader[1])
    fh.seek(0)
    return fh

class QuestionView(View):
    def __init__(self, subject, file_id, question_number):
        super().__init__(timeout=None)
        self.subject = subject
        self.file_id = file_id
        self.question_number = question_number

    @discord.ui.button(label="Next Question", style=discord.ButtonStyle.primary)
    async def next_question(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        await post_question(interaction.channel, self.subject, interaction.user)

    @discord.ui.button(label="Marking Scheme", style=discord.ButtonStyle.success)
    async def marking_scheme(self, interaction: discord.Interaction, button: Button):
        ms_file_id = None
        for fid, name in file_cache.get(self.subject, []):
            if "ms" in name and name.replace("ms", "qp") in self.file_id:
                ms_file_id = fid
                break
        if not ms_file_id:
            await interaction.response.send_message("No marking scheme found.", ephemeral=True)
            return
        fh = await download_file(ms_file_id)
        with pdfplumber.open(fh) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                if self.question_number in text:
                    image = crop_footer(page.to_image(resolution=200).original)
                    img_io = io.BytesIO()
                    image.save(img_io, format='PNG')
                    img_io.seek(0)
                    await interaction.response.send_message(file=discord.File(img_io, filename="ms.png"))
                    return

async def post_question(channel, subject, user=None):
    files = file_cache.get(subject)
    if not files:
        await channel.send("No files found for this subject.")
        return
    file_id, file_name = random.choice(files)
    fh = await download_file(file_id)
    with pdfplumber.open(fh) as pdf:
        page_num = random.randint(1, len(pdf.pages)-2)
        page = pdf.pages[page_num]
        question_number = extract_question_number(page.extract_text() or "") or str(page_num+1)
        image = crop_footer(page.to_image(resolution=200).original)
        img_io = io.BytesIO()
        image.save(img_io, format='PNG')
        img_io.seek(0)
    view = QuestionView(subject, file_id, question_number)
    await channel.send(f"📘 **Subject:** {subject.title()}", file=discord.File(img_io, filename="question.png"), view=view)
    if user:
        user_scores[user.id] += 1
    last_question[channel.id] = {"subject": subject, "file_id": file_id, "question_number": question_number}

# --- SLASH COMMANDS ---

@tree.command(name="question", description="Get a random question for a subject")
@app_commands.describe(subject="Subject for the question")
async def slash_question(interaction: discord.Interaction, subject: str):
    subject = subject.lower().strip()
    if subject not in SUBJECT_ALIASES:
        await interaction.response.send_message("❌ Unsupported subject. Use `/subjectlist`.", ephemeral=True)
        return
    await interaction.response.defer()
    await post_question(interaction.channel, subject, interaction.user)

@tree.command(name="subjectlist", description="List available subjects")
async def slash_subjectlist(interaction: discord.Interaction):
    available = sorted(set(SUBJECT_ALIASES.keys()) - EXCLUDED_SUBJECTS)
    await interaction.response.send_message("📚 **Supported Subjects:** " + ", ".join(available), ephemeral=True)

# In-memory user-shared links for demo; use persistent storage for production
user_shared_drive_links = defaultdict(list)

class NoteModal(Modal, title="Upload Note"):
    subject = TextInput(label="Subject", required=True, placeholder="e.g. Math")
    note = TextInput(label="Note or Google Drive Link", required=False, style=discord.TextStyle.paragraph, placeholder="Paste your note text OR a Google Drive link here.")

    def __init__(self):
        super().__init__()

@tree.command(name="addnote", description="Upload a note or share a Drive link for a subject")
async def addnote(interaction: discord.Interaction):
    await interaction.response.send_modal(NoteModal())

@bot.event
async def on_modal_submit(modal: NoteModal, interaction: discord.Interaction):
    subject = modal.subject.value.strip().lower()
    note_content = modal.note.value.strip()
    response_msg = ""
    # If the note_content is a Google Drive link, save it (in-memory here)
    if note_content.startswith("https://drive.google.com/"):
        user_shared_drive_links[subject].append(note_content)
        response_msg = f"✅ Saved your Drive link for {subject.title()}."
    elif note_content:
        # Upload text note as a file to the appropriate Drive folder
        folder_link = SUBJECT_DRIVE_LINKS.get(subject)
        if folder_link:
            folder_id = folder_link.split('/')[-1]
            note_filename = f"{subject}_note.txt"
            note_path = f"/tmp/{note_filename}"
            with open(note_path, "w") as f:
                f.write(note_content)
            media = MediaFileUpload(note_path, resumable=True)
            file_metadata = {'name': note_filename, 'parents': [folder_id]}
            drive_service.files().create(body=file_metadata, media_body=media, fields='id,webViewLink').execute()
            os.remove(note_path)
            response_msg = f"✅ Uploaded note for {subject.title()} to its Google Drive folder."
        else:
            response_msg = f"❌ Subject not recognized or not configured for Drive uploads."
    else:
        response_msg = "❌ Please provide a note or a Google Drive link."
    await interaction.response.send_message(response_msg, ephemeral=True)

@tree.command(name="fetchnote", description="Get the Google Drive folder link for a subject and shared links")
@app_commands.describe(subject="Subject to fetch notes for")
async def fetchnote(interaction: discord.Interaction, subject: str):
    subject = subject.strip().lower()
    folder_link = SUBJECT_DRIVE_LINKS.get(subject)
    if folder_link:
        shared_links = user_shared_drive_links.get(subject, [])
        msg = f"📁 **{subject.title()} Notes Folder:**\n{folder_link}"
        if shared_links:
            msg += "\n\n**User Shared Links:**\n" + "\n".join(shared_links)
        await interaction.response.send_message(msg, ephemeral=True)
    else:
        await interaction.response.send_message("❌ No Google Drive folder found for this subject.", ephemeral=True)

# --- FLASK SERVER ---
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return jsonify({"status": "ok", "message": "IGCSE Discord Bot Flask API running."})

def run_flask():
    flask_app.run(host="0.0.0.0", port=5000)

# --- Startup logic ---
@bot.event
async def on_ready():
    await fetch_drive_files()
    try:
        synced = await tree.sync()
        print(f"✅ Synced {len(synced)} slash commands")
    except Exception as e:
        print(f"Slash command sync failed: {e}")
    print(f"✅ Logged in as {bot.user.name}")

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    bot.run(TOKEN)
