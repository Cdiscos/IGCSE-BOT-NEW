
import discord
from discord.ext import commands
from discord.ui import View, Button
import os
import random
import io
import re
import pdfplumber
from PIL import Image, ImageDraw
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
from collections import defaultdict
from flask import Flask

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

user_scores = defaultdict(int)
last_question = {}

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
creds = service_account.Credentials.from_service_account_file(GOOGLE_CREDENTIALS, scopes=SCOPES)
drive_service = build("drive", "v3", credentials=creds)

SUBJECT_ALIASES = {
    "math": "0580", "mathematics": "0580",
    "biology": "0610", "chemistry": "0620", "physics": "0625",
    "ict": "0417", "computerscience": "0478", "cs": "0478",
    "literature": "0475", "accounting": "0452", "economics": "0455"
}

EXCLUDED_SUBJECTS = {"english", "history", "geography", "business", "french", "global"}

def crop_footer(pil_image, footer_height=70):
    width, height = pil_image.size
    draw = ImageDraw.Draw(pil_image)
    draw.rectangle((0, height - footer_height, width, height), fill="white")
    return pil_image

def extract_question_number(text):
    match = re.search(r'\b(?:Question\s*)?(\d{1,2})[.)]', text)
    return match.group(1) if match else None

file_cache = {}

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
            if any(k in name for k in ["practical", "alternative", "geography", "history", "english", "french", "global", "business"]):
                continue
            file_cache[subject].append((f["id"], f["name"]))

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
            return

        request = drive_service.files().get_media(fileId=ms_file_id)
        fh = io.BytesIO()
        downloader = build("media", "v1").media().download_media(request, fh)
        downloader.next_chunk()
        fh.seek(0)
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
        return
    file_id, file_name = random.choice(files)
    request = drive_service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = build("media", "v1").media().download_media(request, fh)
    downloader.next_chunk()
    fh.seek(0)
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

@bot.command()
async def question(ctx, *, subject=None):
    if not subject:
        await ctx.send("❌ Please specify a subject. Use `!subjectlist`.")
        return
    subject = subject.lower().strip()
    if subject not in SUBJECT_ALIASES:
        await ctx.send("❌ Unsupported subject. Use `!subjectlist`.")
        return
    await post_question(ctx.channel, subject, ctx.author)

@bot.command()
async def subjectlist(ctx):
    available = sorted(set(SUBJECT_ALIASES.keys()) - EXCLUDED_SUBJECTS)
    await ctx.send("📚 **Supported Subjects:** " + ", ".join(available))

@bot.event
async def on_ready():
    await fetch_drive_files()
    print(f"✅ Logged in as {bot.user.name}")

bot.run(TOKEN)
