import discord
from discord import app_commands
from discord.ext import commands
import config
from data import database
import logging

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)

# ── Bot setup ─────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=config.PREFIX, intents=intents)


# ── Global app-command error handler ─────────────────────────────────────────
@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
):
    """
    Silently swallow stale-interaction errors (10062 / 40060).
    These happen when Discord sends a duplicate interaction event to a second
    bot instance, or when the network is slow enough that the token expires.
    All other errors are logged normally.
    """
    original = getattr(error, "original", error)

    # 10062 = Unknown interaction (token expired / duplicate)
    # 40060 = Interaction has already been acknowledged
    if isinstance(original, (discord.NotFound, discord.HTTPException)):
        code = getattr(original, "code", None)
        if code in (10062, 40060):
            return  # silently ignore — these are harmless race conditions

    # For everything else, log it so we can still see real bugs
    logging.error(f"Unhandled app command error in '{interaction.command}': {error}", exc_info=error)

    # Try to tell the user something went wrong
    msg = "⚠️ Something went wrong. Please try again."
    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except Exception:
        pass


# ── on_ready (logging only) ───────────────────────────────────────────────────
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")


# ── setup_hook: runs ONCE before the bot connects ────────────────────────────
async def setup_hook():
    await database.setup()
    await bot.load_extension("cogs.heist")
    await bot.load_extension("cogs.gambling")
    await bot.load_extension("cogs.economy")
    await bot.load_extension("cogs.help")
    synced = await bot.tree.sync()
    print(f"🔄 Synced {len(synced)} command(s) to Discord.")


bot.setup_hook = setup_hook

bot.run(config.TOKEN)