import discord
from discord.ext import commands
import random
from data import database

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

class BlackjackView(discord.ui.View):
    def __init__(self, user, bet):
        super().__init__(timeout=180)
        self.user = user
        self.bet = bet
        self.deck = generate_deck()
        random.shuffle(self.deck)
        
        self.player_hand = [self.deck.pop(), self.deck.pop()]
        self.dealer_hand = [self.deck.pop(), self.deck.pop()]

    def generate_embed(self, game_over=False, result_msg="", color=discord.Color.blue()):
        embed = discord.Embed(title="🃏 Blackjack", color=color)
        
        player_val = calculate_hand_value(self.player_hand)
        embed.add_field(name=f"Your Hand ({player_val})", value=format_hand(self.player_hand), inline=False)
        
        if game_over:
            dealer_val = calculate_hand_value(self.dealer_hand)
            embed.add_field(name=f"Dealer's Hand ({dealer_val})", value=format_hand(self.dealer_hand), inline=False)
            embed.add_field(name="Result", value=result_msg, inline=False)
        else:
            embed.add_field(name="Dealer's Hand", value=f"`{self.dealer_hand[0]}` `?`", inline=False)
            
        return embed

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
            msg = f"Dealer busts! You won {self.bet * 2} chips."
            color = discord.Color.green()
        elif dealer_val > player_val:
            msg = f"Dealer wins. You lost {self.bet} chips."
            color = discord.Color.red()
        elif dealer_val < player_val:
            await database.update_balance(self.user.id, self.bet * 2)
            msg = f"You win! You won {self.bet * 2} chips."
            color = discord.Color.green()
        else:
            await database.update_balance(self.user.id, self.bet)
            msg = f"Push! You get your {self.bet} chips back."
            color = discord.Color.orange()
            
        embed = self.generate_embed(True, msg, color)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.primary, custom_id="hit")
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)
            
        self.player_hand.append(self.deck.pop())
        player_val = calculate_hand_value(self.player_hand)
        
        if player_val > 21:
            self.stop()
            for child in self.children:
                child.disabled = True
            
            # Loss, bet is already deducted
            embed = self.generate_embed(True, f"Bust! You went over 21. You lost {self.bet} chips.", discord.Color.red())
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            embed = self.generate_embed()
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.secondary, custom_id="stand")
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)
            
        await self.dealer_play(interaction)


class Gambling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(name="blackjack", description="Play a game of blackjack against the dealer.")
    @discord.app_commands.describe(bet="How many chips to bet (minimum 100)")
    async def blackjack(self, interaction: discord.Interaction, bet: int):
        if bet < 100:
            return await interaction.response.send_message("The minimum betting amount is 100 chips.", ephemeral=True)
            
        balance = await database.get_balance(interaction.user.id)
        if balance < bet:
            return await interaction.response.send_message(f"You don't have enough chips! Your balance is {balance}.", ephemeral=True)
            
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
                embed = view.generate_embed(True, f"Push! Both have Blackjack. You get your {bet} chips back.", discord.Color.orange())
            else:
                win_amount = int(bet * 2.5) # 3:2 payout => returns bet + 1.5 * bet
                await database.update_balance(interaction.user.id, win_amount)
                embed = view.generate_embed(True, f"Blackjack! You won {win_amount} chips!", discord.Color.green())
                
            await interaction.response.send_message(embed=embed, view=view)
            return

        embed = view.generate_embed()
        await interaction.response.send_message(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(Gambling(bot))
