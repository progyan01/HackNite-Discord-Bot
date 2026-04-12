import discord
from discord.ext import commands
import random
import asyncio
from data import database
from utils.image_gen import render_blackjack_table, render_slots_machine

def generate_deck():
    suits = ['♠', '♥', '♦', '♣']
    ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
    return [f"{rank}{suit}" for suit in suits for rank in ranks]

def calculate_hand_value(hand):
    total = 0
    aces = 0
    for card in hand:
        rank = card[:-1]
        if rank in ['J', 'Q', 'K']:
            total += 10
        elif rank == 'A':
            aces += 1
            total += 11
        else:
            total += int(rank)
            
    while total > 21 and aces > 0:
        total -= 10
        aces -= 1
        
    return total

def format_hand(hand):
    return " ".join(f"`{card}`" for card in hand)

async def handle_perk_drop(user_id: int) -> str | None:
    chance = random.random()
    if chance > 0.05: # 5% total chance
        return None
        
    roll = random.random()
    if roll < 0.6: 
        perk = "perk_10"
        name = "10% Boost Perk"
    elif roll < 0.9: 
        perk = "perk_15"
        name = "15% Boost Perk"
    else: 
        perk = "perk_20"
        name = "20% Boost Perk"
        
    await database.update_perk(user_id, perk, 1)
    return name


class BlackjackView(discord.ui.View):
    def __init__(self, user, bet):
        super().__init__(timeout=180)
        self.user = user
        self.bet = bet
        self.deck = generate_deck()
        random.shuffle(self.deck)
        
        self.player_hand = [self.deck.pop(), self.deck.pop()]
        self.dealer_hand = [self.deck.pop(), self.deck.pop()]

    def generate_embed_and_file(self, game_over=False, result_msg="", color=discord.Color.gold()):
        embed = discord.Embed(title="🃏 Premium Blackjack", color=color)
        embed.set_author(name=f"{self.user.display_name}'s Table", icon_url=self.user.display_avatar.url if self.user.display_avatar else self.user.default_avatar.url)
        
        player_val = calculate_hand_value(self.player_hand)
        embed.add_field(name=f"👤 Your Hand Value: **{player_val}**", value="\u200b", inline=False)
        
        if game_over:
            dealer_val = calculate_hand_value(self.dealer_hand)
            embed.add_field(name=f"🏦 Dealer's Hand Value: **{dealer_val}**", value="\u200b", inline=False)
            embed.add_field(name="📜 Outcome", value=f"**{result_msg}**", inline=False)
        else:
            embed.add_field(name="🏦 Dealer's Hand Value: **?**", value="\u200b", inline=False)
            embed.set_footer(text=f"Stake: {self.bet:,} chips")
            
        buffer = render_blackjack_table(self.player_hand, self.dealer_hand, game_over)
        file = discord.File(buffer, filename="table.png")
        embed.set_image(url="attachment://table.png")
            
        return embed, file

    async def dealer_play(self, interaction):
        self.stop()
        for child in self.children:
            child.disabled = True
            
        player_val = calculate_hand_value(self.player_hand)
        
        # Dealer hits until 17
        while calculate_hand_value(self.dealer_hand) < 17:
            self.dealer_hand.append(self.deck.pop())
            
        dealer_val = calculate_hand_value(self.dealer_hand)
        
        if dealer_val > 21:
            await database.update_balance(self.user.id, self.bet * 2)
            msg = f"Dealer busts! You won {self.bet * 2:,} chips."
            color = discord.Color.green()
        elif dealer_val > player_val:
            msg = f"Dealer wins. You lost {self.bet:,} chips."
            color = discord.Color.red()
        elif dealer_val < player_val:
            await database.update_balance(self.user.id, self.bet * 2)
            msg = f"You win! You won {self.bet * 2:,} chips."
            color = discord.Color.green()
        else:
            await database.update_balance(self.user.id, self.bet)
            msg = f"Push! You get your {self.bet:,} chips back."
            color = discord.Color.orange()
            
        embed, file = self.generate_embed_and_file(True, msg, color)
        await interaction.response.edit_message(embed=embed, view=self, attachments=[file])
        
        drop_msg = await handle_perk_drop(self.user.id)
        if drop_msg:
            await interaction.followup.send(f"🎉 **RARE DROP!** You found a **{drop_msg}** while playing!", ephemeral=True)

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.primary, custom_id="hit", emoji="🎯")
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            return await interaction.response.send_message("This is not your table!", ephemeral=True)
            
        self.player_hand.append(self.deck.pop())
        player_val = calculate_hand_value(self.player_hand)
        
        if player_val > 21:
            self.stop()
            for child in self.children:
                child.disabled = True
            
            # Loss, bet is already deducted
            embed, file = self.generate_embed_and_file(True, f"Bust! You went over 21. You lost {self.bet:,} chips.", discord.Color.red())
            await interaction.response.edit_message(embed=embed, view=self, attachments=[file])
            
            drop_msg = await handle_perk_drop(self.user.id)
            if drop_msg:
                await interaction.followup.send(f"🎉 **RARE DROP!** You found a **{drop_msg}** while playing!", ephemeral=True)
        else:
            embed, file = self.generate_embed_and_file()
            await interaction.response.edit_message(embed=embed, view=self, attachments=[file])

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.secondary, custom_id="stand", emoji="🛑")
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            return await interaction.response.send_message("This is not your table!", ephemeral=True)
            
        await self.dealer_play(interaction)
        
class CrashView(discord.ui.View):
    def __init__(self, user, bet):
        super().__init__(timeout=None)
        self.user = user
        self.bet = bet
        self.cashed_out = False
        self.current_multiplier = 1.0

    @discord.ui.button(label="Cash Out", style=discord.ButtonStyle.success, custom_id="cash_out", emoji="💸")
    async def cash_out(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            return await interaction.response.send_message("Not your game!", ephemeral=True)
            
        self.cashed_out = True
        for child in self.children:
            child.disabled = True
            
        win_amt = int(self.bet * self.current_multiplier)
        await database.update_balance(self.user.id, win_amt)
        
        embed = discord.Embed(
            title="📈 CRASH",
            description=f"✅ You cashed out at **{self.current_multiplier:.1f}x**!\nWon **{win_amt:,}** chips.",
            color=discord.Color.green()
        )
        
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()

class Gambling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(name="blackjack", description="Play a high-stakes game of blackjack against the dealer.")
    @discord.app_commands.describe(bet="How many chips to bet (minimum 100)")
    async def blackjack(self, interaction: discord.Interaction, bet: int):
        if bet < 100:
            return await interaction.response.send_message("The minimum betting amount is 100 chips.", ephemeral=True)
            
        balance = await database.get_balance(interaction.user.id)
        if balance < bet:
            return await interaction.response.send_message(f"You don't have enough chips! Your balance is {balance:,}.", ephemeral=True)
            
        # Deduct bet
        await database.update_balance(interaction.user.id, -bet)
        
        view = BlackjackView(interaction.user, bet)
        
        # Check instant blackjack
        player_val = calculate_hand_value(view.player_hand)
        dealer_val = calculate_hand_value(view.dealer_hand)
        
        if player_val == 21:
            for child in view.children:
                child.disabled = True
            
            if dealer_val == 21:
                await database.update_balance(interaction.user.id, bet)
                embed, file = view.generate_embed_and_file(True, f"Push! Both have Blackjack. You got your {bet:,} chips back.", discord.Color.orange())
            else:
                win_amount = int(bet * 2.5) # 3:2 payout => returns bet + 1.5 * bet
                await database.update_balance(interaction.user.id, win_amount)
                embed, file = view.generate_embed_and_file(True, f"Blackjack! You won {win_amount:,} chips!", discord.Color.green())
                
            await interaction.response.send_message(embed=embed, view=view, file=file)
            
            drop_msg = await handle_perk_drop(interaction.user.id)
            if drop_msg:
                await interaction.followup.send(f"🎉 **RARE DROP!** You found a **{drop_msg}** while playing!", ephemeral=True)
            return

        embed, file = view.generate_embed_and_file()
        await interaction.response.send_message(embed=embed, view=view, file=file)

    @discord.app_commands.command(name="crash", description="Play a real-time Crash game where the multiplier goes up until it crashes.")
    @discord.app_commands.describe(bet="How many chips to bet (minimum 100)")
    async def crash(self, interaction: discord.Interaction, bet: int):
        if bet < 100:
            return await interaction.response.send_message("The minimum betting amount is 100 chips.", ephemeral=True)
            
        balance = await database.get_balance(interaction.user.id)
        if balance < bet:
            return await interaction.response.send_message(f"You don't have enough chips! Your balance is {balance:,}.", ephemeral=True)
            
        # Deduct bet
        await database.update_balance(interaction.user.id, -bet)
        
        view = CrashView(interaction.user, bet)
        
        embed = discord.Embed(
            title="📈 CRASH",
            description=f"Multiplier: **1.0x**\n\nThe multiplier will go up... don't let it crash!",
            color=discord.Color.blue()
        )
        
        await interaction.response.send_message(embed=embed, view=view)
        
        # Real-time update loop
        multiplier = 1.0
        u = random.uniform(0.2, 1.0)
        crash_point = round(1.0 / u, 1)
        
        delay = 1.2
        while not view.cashed_out and multiplier < crash_point:
            await asyncio.sleep(delay)
            if view.cashed_out:
                break
                
            multiplier += round(random.uniform(0.1, 0.4), 1)
            multiplier = round(multiplier, 1)
            
            if multiplier >= crash_point:
                multiplier = crash_point
                
            view.current_multiplier = multiplier
            
            if multiplier < crash_point and not view.cashed_out:
                embed.description = f"Multiplier: **{multiplier:.1f}x**\n\nCash out before it crashes!"
                try:
                    await interaction.edit_original_response(embed=embed, view=view)
                except discord.HTTPException:
                    pass
            
        if not view.cashed_out:
            for child in view.children:
                child.disabled = True
            
            view.stop()
            embed.description = f"💥 **CRASHED at {crash_point:.1f}x!**\n\nYou lost **{bet:,}** chips."
            embed.color = discord.Color.red()
            
            try:
                await interaction.edit_original_response(embed=embed, view=view)
            except discord.HTTPException:
                pass
                
        drop_msg = await handle_perk_drop(interaction.user.id)
        if drop_msg:
            await interaction.followup.send(f"🎉 **RARE DROP!** You found a **{drop_msg}** while playing Crash!", ephemeral=True)


    @discord.app_commands.command(name="slots", description="Pull the handle on our 3x3 slot machine!")
    @discord.app_commands.describe(bet="How many chips to bet (minimum 100)")
    async def slots(self, interaction: discord.Interaction, bet: int):
        # Defer immediately — image generation + DB calls take > 3 seconds
        await interaction.response.defer()

        if bet < 100:
            return await interaction.followup.send("The minimum betting amount is 100 chips.", ephemeral=True)

        balance = await database.get_balance(interaction.user.id)
        if balance < bet:
            return await interaction.followup.send(f"You don't have enough chips! Your balance is {balance:,}.", ephemeral=True)

        # Deduct bet
        await database.update_balance(interaction.user.id, -bet)

        # Slot Machine Configuration — (Symbol, Multiplier for 3-in-a-row)
        symbols = [
            ("🍒", 2),
            ("🍋", 3),
            ("🍇", 5),
            ("🔔", 10),
            ("💎", 20),
            ("7️⃣", 50)
        ]
        weights = [40, 30, 15, 8, 5, 2]  # Higher multipliers are rarer

        # Generate 3x3 Grid
        grid = []
        for _ in range(3):
            row = random.choices(symbols, weights=weights, k=3)
            grid.append(row)

        # ── Spinning state (sent as followup since we deferred) ──
        spin_embed = discord.Embed(
            title="🎰 Super Slots",
            description=f"**Bet: {bet:,} chips**\n\n*Spinning the reels...*",
            color=discord.Color.blurple()
        )
        spin_embed.set_author(
            name=f"{interaction.user.display_name}'s Spin",
            icon_url=interaction.user.display_avatar.url if interaction.user.display_avatar else interaction.user.default_avatar.url
        )
        spin_buffer = render_slots_machine(grid, spinning=True)
        spin_file = discord.File(spin_buffer, filename="slots.png")
        spin_embed.set_image(url="attachment://slots.png")

        await interaction.followup.send(embed=spin_embed, file=spin_file)
        await asyncio.sleep(2.0)  # Suspense!

        # ── Calculate winnings ──
        total_winnings = 0
        win_row_indices = set()

        for i, row in enumerate(grid):
            sym1, sym2, sym3 = row
            if sym1[0] == sym2[0] == sym3[0]:
                multiplier = sym1[1]
                total_winnings += (bet * multiplier)
                win_row_indices.add(i)

        # ── Final result image ──
        result_buffer = render_slots_machine(grid, spinning=False, win_rows=win_row_indices)
        result_file = discord.File(result_buffer, filename="slots.png")

        final_embed = discord.Embed(title="🎰 Super Slots", color=discord.Color.gold())
        final_embed.set_author(
            name=f"{interaction.user.display_name}'s Spin",
            icon_url=interaction.user.display_avatar.url if interaction.user.display_avatar else interaction.user.default_avatar.url
        )
        final_embed.set_image(url="attachment://slots.png")

        if total_winnings > 0:
            final_embed.color = discord.Color.green()
            final_embed.description = f"**Bet: {bet:,} chips**"
            final_embed.add_field(name="🎉 Winner!", value=f"You matched **{len(win_row_indices)}** line(s) and won **{total_winnings:,}** chips!", inline=False)
            await database.update_balance(interaction.user.id, total_winnings)
        else:
            final_embed.color = discord.Color.red()
            final_embed.description = f"**Bet: {bet:,} chips**"
            final_embed.add_field(name="😢 Better Luck Next Time", value=f"No matching rows.\nLost **{bet:,}** chips.", inline=False)

        await interaction.edit_original_response(embed=final_embed, attachments=[result_file])

        drop_msg = await handle_perk_drop(interaction.user.id)
        if drop_msg:
            await interaction.followup.send(f"🎉 **RARE DROP!** You found a **{drop_msg}** while spinning!", ephemeral=True)

    @discord.app_commands.command(name="duel", description="Challenge someone to a Noir-style Rock-Paper-Scissors duel.")
    @discord.app_commands.describe(bet="How many chips to wager (minimum 100)", target="Optional specific user to challenge")
    async def duel(self, interaction: discord.Interaction, bet: int, target: discord.User = None):
        if bet < 100:
            return await interaction.response.send_message("The minimum betting amount is 100 chips.", ephemeral=True)

        balance = await database.get_balance(interaction.user.id)
        if balance < bet:
            return await interaction.response.send_message(f"You don't have enough chips! Your balance is {balance:,}.", ephemeral=True)

        # Deduct host bet immediately
        await database.update_balance(interaction.user.id, -bet)
        
        view = DuelWaitView(interaction.user, bet, target)
        
        target_str = f"**{target.display_name}**" if target else "anyone"
        embed = discord.Embed(
            title="⚔️ Duel Challenge Sent!",
            description=f"{interaction.user.display_name} is challenging {target_str} to a duel for **{bet:,}** chips!\n\nDo you have what it takes?",
            color=discord.Color.red()
        )
        
        await interaction.response.send_message(content=target.mention if target else "", embed=embed, view=view)
        # Store message reference to allow timeout edits
        view.message = await interaction.original_response()

MATCHUPS = {
    "Revolver": {
        "Switchblade": "Revolver guns down the Switchblade (from a distance)!",
        "Brass Knuckles": "Revolver out-powers the Brass Knuckles!"
    },
    "Switchblade": {
        "Choking wire": "Switchblade severs the Choking wire (cutting the wire)!",
        "Poison": "Switchblade stabs the Poison handler before the drink is poured!"
    },
    "Brass Knuckles": {
        "Switchblade": "Brass Knuckles shatter the Switchblade!",
        "Choking wire": "Brass Knuckles knock out the Choking wire wielder in a brawl!"
    },
    "Choking wire": {
        "Revolver": "Choking wire strangles the Revolver user (from behind)!",
        "Poison": "Choking wire chokes the Poison handler silently!"
    },
    "Poison": {
        "Revolver": "Poison taints the flask of the Revolver marksman!",
        "Brass Knuckles": "Poison quietly takes down the Brass Knuckles brute!"
    }
}

class DuelActiveView(discord.ui.View):
    def __init__(self, p1, p2, bet):
        super().__init__(timeout=60)
        self.p1 = p1
        self.p2 = p2
        self.bet = bet
        self.p1_choice = None
        self.p2_choice = None
        self.resolved = False
        self.message = None

    async def on_timeout(self):
        if not self.resolved:
            # Refund both players since the duel didn't finish
            await database.update_balance(self.p1.id, self.bet)
            await database.update_balance(self.p2.id, self.bet)
            
            embed = discord.Embed(
                title="⚔️ Duel Expired",
                description="Time ran out! Both players were refunded their bets.",
                color=discord.Color.dark_gray()
            )
            for child in self.children:
                child.disabled = True
            if self.message:
                await self.message.edit(embed=embed, view=self)

    async def process_choice(self, interaction: discord.Interaction, weapon: str):
        if interaction.user not in [self.p1, self.p2]:
            return await interaction.response.send_message("You are not part of this duel!", ephemeral=True)
            
        if interaction.user == self.p1:
            if self.p1_choice:
                return await interaction.response.send_message("You already locked in your weapon!", ephemeral=True)
            self.p1_choice = weapon
        elif interaction.user == self.p2:
            if self.p2_choice:
                return await interaction.response.send_message("You already locked in your weapon!", ephemeral=True)
            self.p2_choice = weapon
            
        await interaction.response.send_message(f"You locked in: **{weapon}** 🤫", ephemeral=True)
        
        if self.p1_choice and self.p2_choice and not self.resolved:
            self.resolved = True
            self.stop()
            for child in self.children:
                child.disabled = True
                
            w1 = self.p1_choice
            w2 = self.p2_choice
            
            if w1 == w2:
                # Tie
                await database.update_balance(self.p1.id, self.bet)
                await database.update_balance(self.p2.id, self.bet)
                desc = f"Both players chose **{w1}**. It's a standoff!\nBets have been returned."
                color = discord.Color.orange()
            elif MATCHUPS[w1].get(w2):
                # p1 wins
                await database.update_balance(self.p1.id, self.bet * 2)
                desc = f"**{self.p1.display_name}** wins!\n*{MATCHUPS[w1][w2]}*\n\nThey walk away with **{self.bet * 2:,}** chips."
                color = discord.Color.green()
            else:
                # p2 wins
                await database.update_balance(self.p2.id, self.bet * 2)
                desc = f"**{self.p2.display_name}** wins!\n*{MATCHUPS[w2][w1]}*\n\nThey walk away with **{self.bet * 2:,}** chips."
                color = discord.Color.red()
                
            embed = discord.Embed(title="⚔️ Duel Results", description=desc, color=color)
            embed.add_field(name=self.p1.display_name, value=w1, inline=True)
            embed.add_field(name=self.p2.display_name, value=w2, inline=True)
            
            if self.message:
                await self.message.edit(embed=embed, view=self)

    @discord.ui.button(emoji="🔫", label="Revolver", style=discord.ButtonStyle.secondary)
    async def b1(self, interaction, button): await self.process_choice(interaction, "Revolver")

    @discord.ui.button(emoji="🔪", label="Switchblade", style=discord.ButtonStyle.secondary)
    async def b2(self, interaction, button): await self.process_choice(interaction, "Switchblade")

    @discord.ui.button(emoji="👊", label="Brass Knuckles", style=discord.ButtonStyle.secondary)
    async def b3(self, interaction, button): await self.process_choice(interaction, "Brass Knuckles")

    @discord.ui.button(emoji="🪢", label="Choking wire", style=discord.ButtonStyle.secondary)
    async def b4(self, interaction, button): await self.process_choice(interaction, "Choking wire")

    @discord.ui.button(emoji="🧪", label="Poison", style=discord.ButtonStyle.secondary)
    async def b5(self, interaction, button): await self.process_choice(interaction, "Poison")


class DuelWaitView(discord.ui.View):
    def __init__(self, host: discord.User, bet: int, target: discord.User = None):
        super().__init__(timeout=180)
        self.host = host
        self.bet = bet
        self.target = target
        self.accepted = False
        self.opponent = None
        self.message = None

    async def on_timeout(self):
        if not self.accepted:
            # Refund host who already paid
            await database.update_balance(self.host.id, self.bet)
            for child in self.children:
                child.disabled = True
            
            embed = discord.Embed(title="⚔️ Duel Cancelled", description="Nobody accepted the duel in time. Bet refunded.", color=discord.Color.dark_gray())
            if self.message:
                await self.message.edit(embed=embed, view=self)

    @discord.ui.button(label="Accept Duel", style=discord.ButtonStyle.danger, custom_id="accept_duel", emoji="⚔️")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user == self.host:
            return await interaction.response.send_message("You cannot duel yourself!", ephemeral=True)
            
        if self.target and interaction.user != self.target:
            return await interaction.response.send_message(f"This duel is specifically targeted at {self.target.display_name}!", ephemeral=True)
            
        op_bal = await database.get_balance(interaction.user.id)
        if op_bal < self.bet:
            return await interaction.response.send_message(f"You don't have enough chips to match the **{self.bet:,}** chip bet!\nYour balance: {op_bal:,}", ephemeral=True)
            
        self.accepted = True
        self.opponent = interaction.user
        self.stop()
        
        # Deduct opponent bet (host bet already deducted when starting)
        await database.update_balance(self.opponent.id, -self.bet)
        
        active_view = DuelActiveView(self.host, self.opponent, self.bet)
        
        embed = discord.Embed(
            title="⚔️ Duel: Choose Your Weapon!",
            description=f"**{self.host.display_name}** vs **{self.opponent.display_name}**\n\nBoth players must securely lock in their choices below.\nPot: **{self.bet * 2:,}** chips",
            color=discord.Color.purple()
        )
        await interaction.response.edit_message(embed=embed, view=active_view)
        
        # We need to set active_view's message to the edited message so it can edit it upon resolve
        active_view.message = interaction.message

async def setup(bot):
    await bot.add_cog(Gambling(bot))