import discord
from discord.ext import commands
import datetime
from data import database
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_loans.start()

    def cog_unload(self):
        self.check_loans.cancel()

    @discord.ext.tasks.loop(hours=1)
    async def check_loans(self):
        # Wait until bot is ready
        await self.bot.wait_until_ready()
        now = datetime.datetime.now(datetime.timezone.utc)
        
        loans = await database.get_all_loans()
        for loan in loans:
            try:
                due_date = datetime.datetime.fromisoformat(loan["loan_due"])
                if now > due_date:
                    # Loan overdue! Apply 1.3x bounty and clear loan
                    bounty_amt = int(loan["loan_amount"] * 1.3)
                    await database.update_bounty(loan["user_id"], bounty_amt)
                    await database.update_loan(loan["user_id"], 0, None)
            except Exception:
                pass

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

    @discord.app_commands.command(name="daily", description="Claim your daily reward!")
    async def daily(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        today = datetime.date.today()
        today_str = today.isoformat()
        
        # Ensure user exists
        await database.get_balance(user_id)
        user_data = await database.get_user_data(user_id)
        
        last_daily_str = user_data["last_daily"]
        streak = user_data["daily_streak"]
        
        if last_daily_str == today_str:
            return await interaction.response.send_message("❌ You have already claimed your daily reward today! Come back tomorrow.", ephemeral=True)
            
        if last_daily_str:
            last_daily = datetime.date.fromisoformat(last_daily_str)
            if (today - last_daily).days == 1:
                streak += 1
            else:
                streak = 0
        else:
            streak = 0
            
        # Cap streak at 10 for balancing
        effective_streak = min(streak, 10)
        reward = 250 + (effective_streak * 50)
        
        await database.update_balance(user_id, reward)
        await database.update_last_daily(user_id, today_str, streak)
        
        embed = discord.Embed(
            title="🎁 Daily Reward",
            description=f"You claimed your daily reward of **{reward:,}** chips!\n🔥 Current Streak: **{streak}** days",
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
    @discord.app_commands.command(name="profile", description="Generate your Vegas ID profile card.")
    async def profile(self, interaction: discord.Interaction):
        await interaction.response.defer()
        user_data = await database.get_user_data(interaction.user.id)
        if not user_data:
            await database.get_balance(interaction.user.id) # creates user
            user_data = await database.get_user_data(interaction.user.id)
            
        balance = user_data["balance"]
        streak = user_data["daily_streak"]
        bounty = user_data["bounty"]
        
        # Load avatar
        try:
            avatar_bytes = await interaction.user.display_avatar.read()
            avatar_img = Image.open(BytesIO(avatar_bytes)).convert("RGBA")
            avatar_img = avatar_img.resize((150, 150))
        except Exception:
            avatar_img = Image.new("RGBA", (150, 150), color=(100, 100, 100, 255))

        # Create canvas
        bg = Image.new("RGBA", (600, 300), color=(30, 30, 30, 255))
        draw = ImageDraw.Draw(bg)
        
        # Draw some Vegas flair (a red strip)
        draw.rectangle([0, 0, 600, 20], fill=(200, 0, 0, 255))
        
        # Paste avatar
        bg.paste(avatar_img, (30, 75), avatar_img)
        
        # Define fonts - fallback to default if TTF unavailable
        try:
            font_title = ImageFont.truetype("arial.ttf", 36)
            font_text = ImageFont.truetype("arial.ttf", 24)
        except OSError:
            font_title = ImageFont.load_default()
            font_text = ImageFont.load_default()

        # Draw text
        draw.text((210, 50), f"Name: {interaction.user.display_name}", fill=(255, 255, 255, 255), font=font_title)
        draw.text((210, 110), f"Chips: {balance:,}", fill=(255, 215, 0, 255), font=font_text)
        draw.text((210, 150), f"Daily Streak: {streak} days", fill=(200, 200, 200, 255), font=font_text)
        
        if bounty > 0:
            draw.text((210, 190), f"WANTED: {bounty:,} BOUNTY", fill=(255, 50, 50, 255), font=font_text)

        # Save to buffer
        buffer = BytesIO()
        bg.save(buffer, format="PNG")
        buffer.seek(0)
        
        file = discord.File(buffer, filename="profile.png")
        await interaction.followup.send(file=file)

    @discord.app_commands.command(name="leaderboard", description="View the top 10 richest players.")
    async def leaderboard(self, interaction: discord.Interaction):
        top_users = await database.get_top_users()
        
        desc = ""
        for i, u in enumerate(top_users):
            user_obj = self.bot.get_user(u["user_id"])
            name = user_obj.display_name if user_obj else f"User {u['user_id']}"
            
            medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"`{i+1}.`"
            desc += f"{medal} **{name}**: {u['balance']:,} chips\n\n"
            
        embed = discord.Embed(title="🏆 Global Rich List", description=desc or "No data yet.", color=discord.Color.gold())
        await interaction.response.send_message(embed=embed)

    @discord.app_commands.command(name="loan", description="Borrow chips from the Loan Shark. (50% interest, due in 24 hours)")
    @discord.app_commands.describe(amount="Amount of chips to borrow")
    async def loan(self, interaction: discord.Interaction, amount: int):
        if amount <= 0:
            return await interaction.response.send_message("Must borrow a positive amount.", ephemeral=True)
            
        user_data = await database.get_user_data(interaction.user.id)
        if user_data and user_data["loan_amount"] > 0:
            return await interaction.response.send_message("You already have an active loan! Pay it off first.", ephemeral=True)
            
        # Restrict loan to half their balance or a base amount
        balance = user_data["balance"] if user_data else 1000
        max_loan = max(1000, balance // 2)
        if amount > max_loan:
            return await interaction.response.send_message(f"The Loan Shark doesn't trust you that much. Max loan: **{max_loan:,}** chips.", ephemeral=True)

        due = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=24)
        total_due = int(amount * 1.5)
        
        await database.update_balance(interaction.user.id, amount)
        await database.update_loan(interaction.user.id, total_due, due.isoformat())
        
        await interaction.response.send_message(f"🤝 The Loan Shark lent you **{amount:,}** chips.\n⚠️ You owe **{total_due:,}** chips. Due in exactly 24 hours or a bounty will be placed on your head!")

    @discord.app_commands.command(name="payback", description="Pay back your active loan.")
    async def payback(self, interaction: discord.Interaction):
        user_data = await database.get_user_data(interaction.user.id)
        if not user_data or user_data["loan_amount"] <= 0:
            return await interaction.response.send_message("You don't have an active loan to pay back.", ephemeral=True)
            
        balance = user_data["balance"]
        loan_amount = user_data["loan_amount"]
        
        if balance < loan_amount:
            return await interaction.response.send_message(f"❌ You don't have enough chips! You need **{loan_amount:,}** chips to pay off your loan.", ephemeral=True)
            
        await database.update_balance(interaction.user.id, -loan_amount)
        await database.update_loan(interaction.user.id, 0, None)
        
        await interaction.response.send_message(f"✅ You successfully paid back your loan of **{loan_amount:,}** chips!")

    @discord.app_commands.command(name="bounty_hunt", description="Hunt down a wanted player to claim their bounty!")
    async def bounty_hunt(self, interaction: discord.Interaction, target: discord.User):
        if target.id == interaction.user.id:
            return await interaction.response.send_message("You can't hunt yourself.", ephemeral=True)
            
        target_data = await database.get_user_data(target.id)
        if not target_data or target_data["bounty"] <= 0:
            return await interaction.response.send_message(f"**{target.display_name}** is not wanted. No bounty on them.", ephemeral=True)
            
        import random
        success = random.random() < 0.50 # 50% chance to catch them
        
        bounty = target_data["bounty"]
        if success:
            await database.update_balance(interaction.user.id, bounty)
            # Remove bounty from target, and also heavily penalize their balance
            await database.update_bounty(target.id, -bounty)
            target_bal = await database.get_balance(target.id)
            if target_bal > 0:
                penalty = min(target_bal, bounty)
                await database.update_balance(target.id, -penalty)
                
            await interaction.response.send_message(f"🚨 **BUSTED!** You caught **{target.display_name}** and claimed the **{bounty:,}** chip bounty!\n💸 They also lost some chips from the arrest.")
        else:
            await interaction.response.send_message(f"💨 You tried to corner **{target.display_name}**, but they slipped away!")


async def setup(bot):
    await bot.add_cog(Economy(bot))