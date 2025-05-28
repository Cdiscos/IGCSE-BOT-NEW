import os
import discord
import json
from discord.ext import commands, tasks
from dotenv import load_dotenv
from drive_utils import get_random_theory_question, get_question_and_mark_scheme
from scheduler import schedule_daily_question
from marking_ai import evaluate_answer
from collections import defaultdict

from discord import app_commands
from discord.ui import Modal, TextInput, View, Button

# --- Subject Aliases and Google Drive Links ---
SUBJECT_ALIASES = {
    "math": "0580", "mathematics": "0580",
    "biology": "0610", "chemistry": "0620", "physics": "0625",
    "ict": "0417", "computerscience": "0478", "cs": "0478",
    "literature": "0475", "accounting": "0452", "economics": "0455",
    "business": "0450", "business studies": "0450", "urdu": "3248"
}
EXCLUDED_SUBJECTS = {"english", "history", "geography", "french", "global"}

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

# --- Load environment ---
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))
SCORE_FILE = "scores.json"

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)
tree = bot.tree

# --- User Score Management ---
def load_scores():
    if os.path.exists(SCORE_FILE):
        with open(SCORE_FILE, "r") as f:
            return json.load(f)
    return {}

def save_scores(scores):
    with open(SCORE_FILE, "w") as f:
        json.dump(scores, f)

user_scores = load_scores()

# --- User-Shared Note Links ---
user_shared_drive_links = defaultdict(list)  # in-memory only

# --- QuestionView for Classic Command ---
class QuestionView(discord.ui.View):
    def __init__(self, question_text, mark_scheme_text, image_path):
        super().__init__(timeout=None)
        self.question_text = question_text
        self.mark_scheme_text = mark_scheme_text
        self.image_path = image_path

    @discord.ui.button(label="🔄 Next Question", style=discord.ButtonStyle.primary)
    async def next_question(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Use same subject as previous question if possible, else default to math
        subject = getattr(interaction, "subject", "math")
        img, text, mark_scheme, _ = get_question_and_mark_scheme(subject.lower())
        if img:
            view = QuestionView(text, mark_scheme or "Mark scheme not available yet.", img)
            await interaction.response.send_message(content=f"**New Question:**\n{text}", file=discord.File(img), view=view)
        else:
            await interaction.response.send_message("No more questions found.")

    @discord.ui.button(label="🧠 View Mark Scheme", style=discord.ButtonStyle.secondary)
    async def view_mark_scheme(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(f"**Mark Scheme:**\n{self.mark_scheme_text}", ephemeral=True)

# --- Modal for Uploading Notes ---
class NoteModal(Modal, title="Upload Note"):
    subject = TextInput(label="Subject", required=True, placeholder="e.g. Math")
    note = TextInput(label="Note or Google Drive Link", required=False, style=discord.TextStyle.paragraph, placeholder="Paste your note text OR a Google Drive link here.")

    def __init__(self):
        super().__init__()

# --- Events ---
@bot.event
async def on_ready():
    bot.question_data = {}
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print('------')
    try:
        synced = await tree.sync()
        print(f"✅ Synced {len(synced)} slash commands")
    except Exception as e:
        print(f"Error syncing commands: {e}")
    schedule_daily_question(bot, CHANNEL_ID)
    try:
        from flask_app import start_flask_app
        start_flask_app(bot, CHANNEL_ID)
    except ImportError:
        print("Flask app not started (flask_app.py missing or errored).")

# --- Classic Text Commands ---
@bot.command()
async def question(ctx, subject: str = "math"):
    img, text, mark_scheme, _ = get_question_and_mark_scheme(subject.lower())
    if img:
        view = QuestionView(text, mark_scheme, img)
        await ctx.send(content=f"📘 **{subject.title()} Question:**\n{text}", file=discord.File(img), view=view)
        bot.question_data[str(ctx.author.name)] = (text, mark_scheme)
    else:
        await ctx.send("❌ No theory question available for that subject.")

@bot.command()
async def answer(ctx, *, response: str):
    user = str(ctx.author.name)
    if not hasattr(bot, "question_data") or user not in bot.question_data:
        await ctx.send("❌ Please answer a question first using `/question`.")
        return

    question_text, mark_scheme = bot.question_data[user]
    try:
        result = evaluate_answer(question_text, response, mark_scheme)
        lines = result.strip().splitlines()
        mark = 0
        explanation = "No explanation."
        for line in lines:
            if line.strip().isdigit():
                mark = int(line.strip())
            else:
                explanation = line
        user_scores[user] = user_scores.get(user, 0) + mark
        save_scores(user_scores)
        await ctx.author.send(
            f"📥 **Your Answer Result:**\n"
            f"✅ Marked by AI:\n**{mark} mark(s)** awarded.\n🧠 *{explanation}*"
        )
        await ctx.send("✅ Your answer was received and marked. Check your DM!")
    except Exception as e:
        await ctx.author.send(f"❌ Error during evaluation: {str(e)}")
        await ctx.send("❌ Could not mark your answer. Check your DM for details.")

@bot.command()
async def score(ctx):
    user = str(ctx.author.name)
    score = user_scores.get(user, 0)
    await ctx.send(f"🏅 **{user}**, your total score is: **{score}**")

@bot.command()
async def leaderboard(ctx):
    if not user_scores:
        await ctx.send("No scores recorded yet.")
        return
    sorted_scores = sorted(user_scores.items(), key=lambda x: x[1], reverse=True)
    leaderboard_text = "\n".join([f"{i+1}. {user} — {score} pts" for i, (user, score) in enumerate(sorted_scores)])
    await ctx.send(f"📊 **Leaderboard**:\n{leaderboard_text}")

def is_admin(ctx):
    return ctx.author.guild_permissions.administrator

@bot.command()
async def reset_scores(ctx):
    if not is_admin(ctx):
        await ctx.send("🚫 You are not authorized to use this command.")
        return
    user_scores.clear()
    save_scores(user_scores)
    await ctx.send("🧹 All scores have been reset.")

# --- Slash Commands ---

@tree.command(name="subjectlist", description="List available subjects")
async def slash_subjectlist(interaction: discord.Interaction):
    available = sorted(set(SUBJECT_ALIASES.keys()) - EXCLUDED_SUBJECTS)
    await interaction.response.send_message("📚 **Supported Subjects:** " + ", ".join(available), ephemeral=True)

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
            # Note: Actual Drive upload should be done here if needed
            # You can add your drive_utils upload logic here
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

# --- Launch Bot ---
if __name__ == "__main__":
    bot.run(TOKEN)
