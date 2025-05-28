import os
import json
import discord
from discord.ext import commands
from dotenv import load_dotenv
from drive_utils import get_random_theory_question, get_question_and_mark_scheme
from marking_ai import evaluate_answer
from scheduler import schedule_daily_question
from flask_app import start_flask_app
from collections import defaultdict
from discord import app_commands

# -------------- CONFIGURATION --------------

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))
SCORE_FILE = "scores.json"

# Subject Choices (pretty name, internal key)
SUBJECT_CHOICES = [
    ("Mathematics (0580)", "mathematics"),
    ("Biology (0610)", "biology"),
    ("Chemistry (0620)", "chemistry"),
    ("Physics (0625)", "physics"),
    ("Geography (0460)", "geography"),
    ("Information and Communication Technology (0417)", "information and communication technology"),
    ("Business Studies (0450)", "business studies"),
    ("Accounting (0452)", "accounting"),
    ("Computer Science (0478)", "computer science"),
    ("French - Foreign Language (0520)", "french - foreign language"),
    ("Literature in English (0475)", "literature in english"),
    ("English - First Language (0500)", "english - first language"),
    ("History (0470)", "history"),
    ("Global Perspectives (0457)", "global perspectives"),
    ("Enterprise (0454)", "enterprise"),
    ("Economics (0455)", "economics"),
]

# Google Drive Links
SUBJECT_DRIVE_LINKS = {
    "mathematics": "https://drive.google.com/drive/folders/1GZUs34yS5dMmhO8Pm8rWokkS7VBQ5bqF?usp=sharing",
    "biology": "https://drive.google.com/drive/folders/1tCMnYUtHJ1jQAqmagUw1h5pWrtHxNwYE?usp=sharing",
    "chemistry": "https://drive.google.com/drive/folders/1Ji-VoRovspqnZtvxhJW1CCdeMilxQBCX?usp=sharing",
    "physics": "https://drive.google.com/drive/folders/1Baa4OKIzjjtHzwcy1-xwjBuCDMLh2FlW?usp=sharing",
    "geography": "https://drive.google.com/drive/folders/1xofPQTwhu7pUS0KqO7ielXj0fvmRBTuH?usp=sharing",
    "information and communication technology": "https://drive.google.com/drive/folders/1CnorPO8wNZNkjvQ6LwzkINZXRo24T6-1?usp=sharing",
    "business studies": "https://drive.google.com/drive/folders/1EWccBxwaoV4sjCSHG4DadcpIXUVqtdap?usp=sharing",
    "accounting": "https://drive.google.com/drive/folders/1BEumj8GOd4x0UOVkk8Cq5o5guTgBSeo2?usp=sharing",
    "computer science": "https://drive.google.com/drive/folders/1-CQZbc8dAxai2Qw-bpddpDudpSIASiaT?usp=sharing",
    "french - foreign language": "https://drive.google.com/drive/folders/18Hpg4LjOnw7KgRmXqtAq6MTbM5bpwBFx?usp=sharing",
    "literature in english": "https://drive.google.com/drive/folders/1aNqqrZ6Orl1qyBNsLr8BPhuezofGgXGi?usp=sharing",
    "english - first language": "https://drive.google.com/drive/folders/1YHvXgahzgsFwkcg3vzpHSrVdj_GnCq7E?usp=sharing",
    "history": "https://drive.google.com/drive/folders/1A1OHb2CW5cmCSyQf_cqZGemNQtskhgL_?usp=sharing",
    "global perspectives": "https://drive.google.com/drive/folders/1lTj44aH3tLLEbfK0Tnb5WFG1cwKV3tEJ?usp=sharing",
    "enterprise": "https://drive.google.com/drive/folders/187ppeu_FyUskOb8--2KOqVrGnkcIVHe5?usp=sharing",
    "economics": "https://drive.google.com/drive/folders/1lU4WqKULYiCJzCKPVJYDwsvFVudRB-as?usp=sharing",
}

# -------------- BOT SETUP --------------

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)
tree = bot.tree

# -------------- SCORE MANAGEMENT --------------

def load_scores():
    if os.path.exists(SCORE_FILE):
        with open(SCORE_FILE, "r") as f:
            return json.load(f)
    return {}

def save_scores(scores):
    with open(SCORE_FILE, "w") as f:
        json.dump(scores, f)

user_scores = load_scores()

# -------------- NOTE SHARING --------------

user_shared_drive_links = defaultdict(list)  # {subject: [links]}

class NoteModal(discord.ui.Modal, title="Upload Note or Drive Link"):
    subject = discord.ui.TextInput(label="Subject", required=True, placeholder="E.g. Math")
    note = discord.ui.TextInput(label="Note or Google Drive Link", style=discord.TextStyle.paragraph, required=True, placeholder="Paste your note or drive link here")

    async def on_submit(self, interaction: discord.Interaction):
        subject = self.subject.value.strip().lower()
        note_content = self.note.value.strip()
        if note_content.startswith("https://drive.google.com/"):
            user_shared_drive_links[subject].append(note_content)
            await interaction.response.send_message(f"✅ Saved your Drive link for {subject.title()}.", ephemeral=False)
        else:
            # Here you can implement uploading text notes to Google Drive if you want.
            await interaction.response.send_message("✅ Text note received and would be uploaded (not implemented).", ephemeral=False)

# -------------- QUESTION VIEW --------------

class QuestionView(discord.ui.View):
    def __init__(self, subject, question_text, mark_scheme_text, image_path, user_id=None):
        super().__init__(timeout=None)
        self.subject = subject
        self.question_text = question_text
        self.mark_scheme_text = mark_scheme_text
        self.image_path = image_path
        self.user_id = user_id

    @discord.ui.button(label="🔄 Next Question", style=discord.ButtonStyle.primary)
    async def next_question(self, interaction: discord.Interaction, button: discord.ui.Button):
        img, text, mark_scheme, _ = get_question_and_mark_scheme(self.subject.lower())
        if img:
            new_view = QuestionView(self.subject, text, mark_scheme or "Mark scheme not available.", img, user_id=interaction.user.id)
            await interaction.response.send_message(
                content=f"**New {self.subject.title()} Question:**\n{text}",
                file=discord.File(img),
                view=new_view,
                ephemeral=False
            )
            bot.question_data[str(interaction.user.id)] = (text, mark_scheme)
        else:
            await interaction.response.send_message("No more questions found.", ephemeral=True)

    @discord.ui.button(label="🧠 Mark My Answer", style=discord.ButtonStyle.success)
    async def mark_answer(self, interaction: discord.Interaction, button: discord.ui.Button):
        class AnswerModal(discord.ui.Modal, title="Submit Your Answer"):
            answer = discord.ui.TextInput(label="Your Answer", style=discord.TextStyle.paragraph, required=True)

            async def on_submit(self, modal_interaction: discord.Interaction):
                user = str(modal_interaction.user.id)
                if not hasattr(bot, "question_data") or user not in bot.question_data:
                    await modal_interaction.response.send_message("❌ Please answer a question first using /question.", ephemeral=True)
                    return
                question_text, mark_scheme = bot.question_data[user]
                response = self.answer.value
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
                    await modal_interaction.response.send_message(
                        f"📥 **Your Answer Result:**\n"
                        f"✅ Marked by AI:\n**{mark} mark(s)** awarded.\n🧠 *{explanation}*",
                        ephemeral=False
                    )
                except Exception as e:
                    await modal_interaction.response.send_message(f"❌ Error during evaluation: {str(e)}", ephemeral=True)
        await interaction.response.send_modal(AnswerModal())

    @discord.ui.button(label="🧾 View Mark Scheme", style=discord.ButtonStyle.secondary)
    async def view_mark_scheme(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(f"**Mark Scheme:**\n{self.mark_scheme_text}", ephemeral=True)

# -------------- EVENTS --------------

@bot.event
async def on_ready():
    bot.question_data = {}
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    try:
        synced = await tree.sync()
        print(f"Synced {len(synced)} slash commands")
    except Exception as e:
        print(f"Error syncing commands: {e}")
    schedule_daily_question(bot, CHANNEL_ID)
    start_flask_app(bot, CHANNEL_ID)

# -------------- PREFIX COMMANDS --------------

@bot.command()
async def question(ctx, *, subject: str = "mathematics"):
    img, text, mark_scheme, _ = get_question_and_mark_scheme(subject.lower())
    if img:
        view = QuestionView(subject, text, mark_scheme, img, user_id=ctx.author.id)
        await ctx.send(
            content=f"📘 **{subject.title()} Question:**\n{text}",
            file=discord.File(img),
            view=view
        )
        bot.question_data[str(ctx.author.id)] = (text, mark_scheme)
    else:
        await ctx.send("❌ No theory question available for that subject.")

@bot.command()
async def answer(ctx, *, response: str):
    user = str(ctx.author.id)
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
        await ctx.send(
            f"📥 **Your Answer Result:**\n"
            f"✅ Marked by AI:\n**{mark} mark(s)** awarded.\n🧠 *{explanation}*"
        )
    except Exception as e:
        await ctx.send(f"❌ Error during evaluation: {str(e)}")

@bot.command()
async def score(ctx):
    user = str(ctx.author.id)
    score = user_scores.get(user, 0)
    await ctx.send(f"🏅 **{ctx.author.display_name}**, your total score is: **{score}**")

@bot.command()
async def leaderboard(ctx):
    if not user_scores:
        await ctx.send("No scores recorded yet.")
        return
    sorted_scores = sorted(user_scores.items(), key=lambda x: x[1], reverse=True)
    leaderboard_text = "\n".join(
        [f"{i+1}. <@{user}> — {score} pts" for i, (user, score) in enumerate(sorted_scores)]
    )
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

# -------------- SLASH COMMANDS --------------

@tree.command(name="question", description="Get a random question from a subject")
@app_commands.describe(subject="Pick a subject to get a question from")
@app_commands.choices(subject=[
    app_commands.Choice(name=pretty, value=internal)
    for pretty, internal in SUBJECT_CHOICES
])
async def slash_question(interaction: discord.Interaction, subject: app_commands.Choice[str]):
    chosen_subject = subject.value
    img, text, mark_scheme, _ = get_question_and_mark_scheme(chosen_subject.lower())
    if img:
        view = QuestionView(chosen_subject, text, mark_scheme, img, user_id=interaction.user.id)
        await interaction.response.send_message(
            content=f"📘 **{chosen_subject.title()} Question:**\n{text}",
            file=discord.File(img),
            view=view,
            ephemeral=False
        )
        bot.question_data[str(interaction.user.id)] = (text, mark_scheme)
    else:
        await interaction.response.send_message("❌ No theory question available for that subject.", ephemeral=False)

@tree.command(name="addnote", description="Upload a note or share a Drive link for a subject")
async def addnote(interaction: discord.Interaction):
    await interaction.response.send_modal(NoteModal())

@tree.command(name="fetchnote", description="Get the Google Drive folder link for a subject and shared links")
@app_commands.describe(subject="Subject to fetch notes for (e.g. math, biology, business studies, etc.)")
async def fetchnote(interaction: discord.Interaction, subject: str):
    subject = subject.strip().lower()
    folder_link = SUBJECT_DRIVE_LINKS.get(subject)
    if folder_link:
        shared_links = user_shared_drive_links.get(subject, [])
        msg = f"📁 **{subject.title()} Notes Folder:**\n{folder_link}"
        if shared_links:
            msg += "\n\n**User Shared Links:**\n" + "\n".join(shared_links)
        await interaction.response.send_message(msg, ephemeral=False)
    else:
        await interaction.response.send_message("❌ No Google Drive folder found for this subject.", ephemeral=False)

# -------------- RUN BOT --------------

if __name__ == "__main__":
    bot.run(TOKEN)
