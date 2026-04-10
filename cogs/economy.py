import discord
from discord.ext import commands
from data import database

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(name="balance", description="View your or someone else's chip balance.")
    @discord.app_commands.describe(member="The member whose balance to check (optional)")
    async def balance(self, interaction: discord.Interaction, member: discord.Member = None):
        target = member or interaction.user
        balance = await database.get_balance(target.id)
        
        embed = discord.Embed(
            title=f"💳 Balance: {target.display_name}",
            description=f"**{balance:,}** chips",
            color=discord.Color.gold()
        )
        embed.set_thumbnail(url=target.display_avatar.url if target.display_avatar else target.default_avatar.url)
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Economy(bot))
