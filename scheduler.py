from discord.ext import tasks
from drive_utils import get_random_theory_question
import discord

def schedule_daily_question(bot, channel_id):
    @tasks.loop(hours=24)
    async def daily_post():
        try:
            channel = bot.get_channel(channel_id)
            if channel:
                img, text, _ = get_random_theory_question()
                if img:
                    await channel.send(content=f"📘 Daily Question:\n{text}", file=discord.File(img))
                else:
                    await channel.send("⚠️ No theory question found today.")
        except Exception as e:
            print(f"[SCHEDULER ERROR] {e}")

    daily_post.start()
