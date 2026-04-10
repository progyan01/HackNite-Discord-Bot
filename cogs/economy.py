import discord
from discord.ext import commands
import datetime
from data import database

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(name="balance", description="View your or someone else's chip balance.")
    @discord.app_commands.describe(member="The member whose balance to check (optional)")
    async def balance(self, interaction: discord.Interaction, member: discord.Member = None):
        target = member or interaction.user
        # Allow creating the account if it's the user checking their own balance
        should_create = (member is None) or (member == interaction.user)
        balance = await database.get_balance(target.id, create_if_missing=should_create)
        
        if balance is None:
            await interaction.response.send_message(f"**{target.display_name}** doesn't have an account yet.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"💳 Balance: {target.display_name}",
            description=f"**{balance:,}** chips",
            color=discord.Color.gold()
        )
        embed.set_thumbnail(url=target.display_avatar.url if target.display_avatar else target.default_avatar.url)
        
        await interaction.response.send_message(embed=embed)

    @discord.app_commands.command(name="daily", description="Claim your daily reward of 250 chips!")
    async def daily(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        today_str = datetime.date.today().isoformat()
        
        # Ensure user exists (in case they haven't checked balance yet)
        await database.get_balance(user_id)
        
        last_daily = await database.get_last_daily(user_id)
        
        if last_daily == today_str:
            return await interaction.response.send_message("❌ You have already claimed your daily reward today! Come back tomorrow.", ephemeral=True)
            
        # Give reward
        reward = 250
        await database.update_balance(user_id, reward)
        await database.update_last_daily(user_id, today_str)
        
        embed = discord.Embed(
            title="🎁 Daily Reward",
            description=f"You claimed your daily reward of **{reward:,}** chips!",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Economy(bot))
