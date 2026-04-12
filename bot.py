import discord
from discord.ext import commands
import config
from data import database
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=config.PREFIX, intents=intents)

@bot.event
async def on_ready():
    await database.setup()
    await bot.load_extension("cogs.heist")
    await bot.load_extension("cogs.gambling")
    await bot.load_extension("cogs.economy")
    await bot.load_extension("cogs.help")
    await bot.tree.sync()
    print(f"Logged in as {bot.user}")

bot.run(config.TOKEN)