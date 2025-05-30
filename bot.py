import os
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
from collections import defaultdict

# --------- FLASK INTEGRATION ---------
from flask import Flask
from threading import Thread

app = Flask(__name__)

@app.route("/")
def home():
    return "IGCSE Discord Bot is running!"

def run_flask():
    app.run(host="0.0.0.0", port=5000)

# --------- LOAD CONFIG ---------
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# --------- CONSTANTS FOR EMBED STYLE ---------
EMBED_COLOR = 0x00fff4  # Cyan
ADDNOTES_CHANNEL_ID = 1377955545071357983  # The channel where all notes/links should go

# --------- DATA STRUCTURES ---------

PAST_PAPER_BOARDS = {
    "CIE": {
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
}
PAST_PAPER_BOARD_NAMES = list(PAST_PAPER_BOARDS.keys())
PAST_PAPER_SUBJECTS = list(PAST_PAPER_BOARDS["CIE"].keys())

NOTES_BOARDS = ["IGCSE", "CBSE"]

NOTES_IGCSE_SUBJECTS = {
    "accounting": "https://drive.google.com/drive/folders/1qelX7sXIIxdk_v_bLxJRkbpfuBOfDFno",
    "biology": "https://drive.google.com/drive/folders/1mrh6_cdYUKTGvEN5UyBsLMacRzdsQQtz",
    "business studies": "https://drive.google.com/drive/folders/1JKujjCHyUhNM5y8tfonFrZ7ZPS8oH6Fe",
    "chemistry": "https://drive.google.com/drive/folders/1AgLXQz-dPLtpyvDgRVLnQtS7NVoUjtPp",
    "maths": "https://drive.google.com/drive/folders/1HlOXZYhJhEhz9e8KXVoOSr9lM9RQbXQ3",
    "physics": "https://drive.google.com/drive/folders/1_jnbXYTAVVVDvS-uHs4KQYbyZke5V5Bl",
    "urdu": "https://drive.google.com/drive/folders/1fXFImXjkvudt3FlqLTH8jCDdZX_LLfDf",
}
NOTES_IGCSE_SUBJECT_LIST = list(NOTES_IGCSE_SUBJECTS.keys())

NOTES_CBSE_YEAR_GROUPS = {
    "Class 10": "https://drive.google.com/drive/folders/11MWj0Byg9Chzn-wxg2_agje8hDaK7JpD",
    "Class 9": "https://drive.google.com/drive/folders/11GTAGG4PCZgN6-qWVCcDgUrpx2ImQ2-H",
}

# Stores user-shared links: {(group, subject): [link1, ...]}
user_shared_links = defaultdict(list)

# --------- DISCORD SETUP ---------
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)
tree = bot.tree

# --------- KEYWORD AUTORESPONDER ---------
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    content = message.content.lower()
    if "bestgradez" in content:
        await message.channel.send("https://bestgradez.com/")
    elif "nerd cafe" in content:
        await message.channel.send("https://nerdcafe.org/")
    await bot.process_commands(message)

# -------------------- /fetchpastpapers --------------------
@tree.command(name="fetchpastpapers", description="Get a Drive folder for CIE past papers by subject")
@app_commands.describe(
    board="Choose the board (only CIE supported)",
    subject="Choose the subject"
)
@app_commands.choices(
    board=[app_commands.Choice(name="CIE", value="CIE")],
    subject=[app_commands.Choice(name=s.title(), value=s) for s in PAST_PAPER_SUBJECTS]
)
async def fetchpastpapers(interaction: discord.Interaction, board: app_commands.Choice[str], subject: app_commands.Choice[str]):
    board_key = board.value
    subject_key = subject.value
    folder_link = PAST_PAPER_BOARDS.get(board_key, {}).get(subject_key)
    shared_links = user_shared_links.get((board_key, subject_key), [])

    bot_avatar = interaction.client.user.avatar.url if interaction.client.user.avatar else discord.Embed.Empty

    if not folder_link:
        await interaction.response.send_message("❌ No Drive folder found for this subject.", ephemeral=True)
        return
    embed = discord.Embed(
        title=f"📄 {board_key} {subject_key.title()} Past Papers",
        description=f"**Subject:** `{subject_key.title()}`\n\n"
                    f"**Official Drive Folder:**\n[📁 Click here to open folder]({folder_link})",
        color=EMBED_COLOR
    )
    embed.set_author(name="AjiroTech Notes Assistant", icon_url=bot_avatar)
    embed.add_field(
        name="🔗 Useful Links",
        value=f"[Official Drive Folder]({folder_link})",
        inline=False
    )
    if shared_links:
        embed.add_field(
            name="✨ User Shared Links",
            value="\n".join([f"`{i+1}.` {link}" for i, link in enumerate(shared_links)]),
            inline=False
        )
    embed.set_footer(text="Powered by xcho_", icon_url=bot_avatar)
    await interaction.response.send_message(embed=embed, ephemeral=False)

# -------------------- /fetchnotes --------------------
class CBSEYearGroupSelect(discord.ui.Select):
    def __init__(self, callback):
        options = [
            discord.SelectOption(label="Class 10", value="Class 10"),
            discord.SelectOption(label="Class 9", value="Class 9"),
        ]
        super().__init__(placeholder="Choose CBSE Year Group", min_values=1, max_values=1, options=options)
        self.callback_fn = callback

    async def callback(self, interaction: discord.Interaction):
        await self.callback_fn(interaction, self.values[0])

class CBSEYearGroupView(discord.ui.View):
    def __init__(self, callback):
        super().__init__(timeout=60)
        self.add_item(CBSEYearGroupSelect(callback))

@tree.command(name="fetchnotes", description="Get Drive folder for notes by board and subject/year group")
@app_commands.describe(
    board="Choose the board (IGCSE or CBSE)",
    subject="Choose subject (for IGCSE) or leave blank for CBSE"
)
@app_commands.choices(
    board=[app_commands.Choice(name=b, value=b) for b in NOTES_BOARDS],
    subject=[app_commands.Choice(name=s.title(), value=s) for s in NOTES_IGCSE_SUBJECT_LIST]
)
async def fetchnotes(
    interaction: discord.Interaction,
    board: app_commands.Choice[str],
    subject: app_commands.Choice[str] = None
):
    board_key = board.value
    bot_avatar = interaction.client.user.avatar.url if interaction.client.user.avatar else discord.Embed.Empty

    if board_key == "IGCSE":
        if not subject:
            await interaction.response.send_message("Please select a subject for IGCSE.", ephemeral=True)
            return
        subject_key = subject.value
        folder_link = NOTES_IGCSE_SUBJECTS.get(subject_key)
        shared_links = user_shared_links.get((board_key, subject_key), [])
        if not folder_link:
            await interaction.response.send_message("❌ No Drive folder found for this subject.", ephemeral=True)
            return
        embed = discord.Embed(
            title=f"📚 IGCSE {subject_key.title()} Notes",
            description=f"**Subject:** `{subject_key.title()}`\n\n"
                        f"**Official Drive Folder:**\n[📁 Click here to open folder]({folder_link})",
            color=EMBED_COLOR
        )
        embed.set_author(name="AjiroTech Notes Assistant", icon_url=bot_avatar)
        embed.add_field(
            name="🔗 Useful Links",
            value=f"[Official Drive Folder]({folder_link})",
            inline=False
        )
        if shared_links:
            embed.add_field(
                name="✨ User Shared Links",
                value="\n".join([f"`{i+1}.` {link}" for i, link in enumerate(shared_links)]),
                inline=False
            )
        embed.set_footer(text="Powered by xcho_", icon_url=bot_avatar)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    elif board_key == "CBSE":
        async def cbse_year_selected_callback(new_interaction, year_group):
            bot_avatar = new_interaction.client.user.avatar.url if new_interaction.client.user.avatar else discord.Embed.Empty
            folder_link = NOTES_CBSE_YEAR_GROUPS.get(year_group)
            if not folder_link:
                await new_interaction.response.send_message("❌ No Drive folder found for this year group.", ephemeral=True)
                return
            embed = discord.Embed(
                title=f"📚 CBSE {year_group} Notes",
                description=f"**Year Group:** `{year_group}`\n\n"
                            f"**Official Drive Folder:**\n[📁 Click here to open folder]({folder_link})",
                color=EMBED_COLOR
            )
            embed.set_author(name="AjiroTech Notes Assistant", icon_url=bot_avatar)
            embed.add_field(
                name="🔗 Useful Links",
                value=f"[Official Drive Folder]({folder_link})",
                inline=False
            )
            embed.set_footer(text="Powered by xcho_", icon_url=bot_avatar)
            await new_interaction.response.send_message(embed=embed, ephemeral=False)
        view = CBSEYearGroupView(cbse_year_selected_callback)
        await interaction.response.send_message("Please select your CBSE year group:", view=view, ephemeral=True)
    else:
        await interaction.response.send_message("❌ Board not recognized.", ephemeral=True)

# -------------------- /addnotes --------------------

class AddNoteModal(discord.ui.Modal, title="Add a Note or Drive Link"):
    def __init__(self):
        super().__init__()
        self.add_item(discord.ui.TextInput(
            label="Group (e.g. IGCSE, A LEVELS, AS)", 
            required=True, 
            placeholder="IGCSE, A LEVELS, AS"
        ))
        self.add_item(discord.ui.TextInput(
            label="Subject (e.g. Mathematics, Physics, Biology)", 
            required=True, 
            placeholder="Mathematics"
        ))
        self.add_item(discord.ui.TextInput(
            label="Drive Link or Note",
            style=discord.TextStyle.paragraph,
            required=True,
            placeholder="Paste a Google Drive link or type your note here."
        ))

    async def on_submit(self, interaction: discord.Interaction):
        group = self.children[0].value.strip().upper()
        subject = self.children[1].value.strip().title()
        note_link = self.children[2].value.strip()
        user = interaction.user
        bot_avatar = interaction.client.user.avatar.url if interaction.client.user.avatar else discord.Embed.Empty

        # Save for lookup if needed
        user_shared_links[(group, subject.lower())].append(note_link)

        # Compose message for the channel
        embed = discord.Embed(
            title=f"📝 New User Note/Link Submission",
            description=f"**Group:** `{group}`\n**Subject:** `{subject}`\n\n"
                        f"**Content:**\n>>> {note_link}",
            color=EMBED_COLOR
        )
        embed.set_author(name="AjiroTech Notes Assistant", icon_url=bot_avatar)
        embed.add_field(
            name="🆔 User",
            value=f"{user.mention} (`{user.id}`)",
            inline=True
        )
        embed.set_footer(text="Powered by xcho_", icon_url=bot_avatar)

        # Try to get the channel (cached or fetch)
        channel = interaction.client.get_channel(ADDNOTES_CHANNEL_ID)
        if channel is None:
            try:
                channel = await interaction.client.fetch_channel(ADDNOTES_CHANNEL_ID)
            except Exception:
                channel = None

        if channel is not None:
            await channel.send(embed=embed)

        await interaction.response.send_message(
            f"✅ Your note/link was sent to the Administration! Thank you for sharing.",
            ephemeral=True
        )

@tree.command(name="addnotes", description="Share a Drive link or note for a subject and group (e.g. IGCSE, A LEVELS, AS)")
async def addnotes(interaction: discord.Interaction):
    await interaction.response.send_modal(AddNoteModal())

# --------- SYNC COMMANDS ON READY ---------
@bot.event
async def on_ready():
    await tree.sync()
    print(f"Logged in as {bot.user}")

# --------- RUN THE BOT ----------
if __name__ == "__main__":
    # Start Flask in a separate thread
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # Start Discord bot (blocking)
    bot.run(TOKEN)
