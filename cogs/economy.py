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

    @discord.app_commands.command(name="inventory", description="View your owned Heist Perks.")
    async def inventory(self, interaction: discord.Interaction):
        inv = await database.get_inventory(interaction.user.id)
        embed = discord.Embed(
            title=f"🎒 {interaction.user.display_name}'s Inventory",
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url if interaction.user.display_avatar else interaction.user.default_avatar.url)
        
        embed.add_field(name="🔸 10% Boost Perk", value=f"x{inv['perk_10']}", inline=False)
        embed.add_field(name="🔹 15% Boost Perk", value=f"x{inv['perk_15']}", inline=False)
        embed.add_field(name="🌟 20% Boost Perk", value=f"x{inv['perk_20']}", inline=False)
        
        await interaction.response.send_message(embed=embed)

    @discord.app_commands.command(name="buy", description="Buy perks from the marketplace.")
    @discord.app_commands.describe(perk="Which perk to buy")
    @discord.app_commands.choices(perk=[
        discord.app_commands.Choice(name="10% Boost (1000 chips)", value="perk_10"),
        discord.app_commands.Choice(name="15% Boost (2000 chips)", value="perk_15"),
        discord.app_commands.Choice(name="20% Boost (3000 chips)", value="perk_20")
    ])
    async def buy(self, interaction: discord.Interaction, perk: str):
        prices = {"perk_10": 1000, "perk_15": 2000, "perk_20": 3000}
        names = {"perk_10": "10% Boost Perk", "perk_15": "15% Boost Perk", "perk_20": "20% Boost Perk"}
        
        price = prices[perk]
        balance = await database.get_balance(interaction.user.id)
        
        if balance < price:
            return await interaction.response.send_message(f"❌ You don't have enough chips! You need **{price}** chips.", ephemeral=True)
            
        await database.update_balance(interaction.user.id, -price)
        await database.update_perk(interaction.user.id, perk, 1)
        
        await interaction.response.send_message(f"✅ You successfully bought a **{names[perk]}** for **{price}** chips!\nCheck it with `/inventory`.")

    @discord.app_commands.command(name="pay", description="Transfer chips to another user.")
    @discord.app_commands.describe(target="The user to pay", amount="The amount of chips to transfer")
    async def pay(self, interaction: discord.Interaction, target: discord.User, amount: int):
        if amount <= 0:
            return await interaction.response.send_message("❌ Amount must be greater than 0.", ephemeral=True)
        if target.id == interaction.user.id:
            return await interaction.response.send_message("❌ You cannot pay yourself.", ephemeral=True)
            
        balance = await database.get_balance(interaction.user.id)
        if balance < amount:
            return await interaction.response.send_message("❌ You don't have enough chips.", ephemeral=True)
            
        await database.update_balance(interaction.user.id, -amount)
        await database.update_balance(target.id, amount)
        await interaction.response.send_message(f"💸 You paid **{target.display_name}** **{amount:,}** chips.")

    @discord.app_commands.command(name="give_perk", description="Transfer a perk to another user.")
    @discord.app_commands.describe(target="The user to receive the perk", perk="Which perk to give")
    @discord.app_commands.choices(perk=[
        discord.app_commands.Choice(name="10% Boost", value="perk_10"),
        discord.app_commands.Choice(name="15% Boost", value="perk_15"),
        discord.app_commands.Choice(name="20% Boost", value="perk_20")
    ])
    async def give_perk(self, interaction: discord.Interaction, target: discord.User, perk: str):
        if target.id == interaction.user.id:
            return await interaction.response.send_message("❌ You cannot give a perk to yourself.", ephemeral=True)
            
        inv = await database.get_inventory(interaction.user.id)
        if inv.get(perk, 0) < 1:
            return await interaction.response.send_message("❌ You do not own this perk.", ephemeral=True)
            
        names = {"perk_10": "10% Boost Perk", "perk_15": "15% Boost Perk", "perk_20": "20% Boost Perk"}
        
        await database.update_perk(interaction.user.id, perk, -1)
        await database.update_perk(target.id, perk, 1)
        await interaction.response.send_message(f"🎁 You successfully transferred a **{names[perk]}** to **{target.display_name}**.")


async def setup(bot):
    await bot.add_cog(Economy(bot))