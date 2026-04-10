import discord
from discord.ext import commands
from discord import app_commands
import random
from data import database

class Heist(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Simple memory storage for active lobbies: {user_id: {"target": str, "crew": [discord.Member]}}
        self.active_heists = {} 

    heist_group = app_commands.Group(name="heist", description="Las Vegas Heist Roleplay commands")

    @heist_group.command(name="start", description="Start a new heist lobby")
    @app_commands.describe(target="Where do you want to rob?")
    @app_commands.choices(target=[
        app_commands.Choice(name="Gas Station (Low Risk, 1-2 players)", value="gas_station"),
        app_commands.Choice(name="Jewelry Store (Medium Risk, 2-3 players)", value="jewelry_store"),
        app_commands.Choice(name="Casino Vault (High Risk, 3-4 players)", value="casino_vault")
    ])
    async def start_heist(self, interaction: discord.Interaction, target: str):
        if interaction.user.id in self.active_heists:
            await interaction.response.send_message("You already have an active heist lobby!", ephemeral=True)
            return
        
        self.active_heists[interaction.user.id] = {
            "target": target,
            "crew": [interaction.user]
        }
        await interaction.response.send_message(
            f"💰 {interaction.user.mention} is planning a heist on a **{target.replace('_', ' ').title()}**!\n"
            f"Crew: {interaction.user.display_name}. Anyone else want in? (Use `/heist join {interaction.user.display_name}`)"
        )

    @heist_group.command(name="join", description="Join an active heist lobby")
    async def join_heist(self, interaction: discord.Interaction, host: discord.User):
        lobby = self.active_heists.get(host.id)
        if not lobby:
            await interaction.response.send_message("That user doesn't have an active heist lobby.", ephemeral=True)
            return
        
        if interaction.user in lobby["crew"]:
            await interaction.response.send_message("You are already in this heist crew!", ephemeral=True)
            return

        lobby["crew"].append(interaction.user)
        crew_names = ", ".join([user.display_name for user in lobby["crew"]])
        await interaction.response.send_message(f"😎 {interaction.user.mention} joined the heist! Current crew: {crew_names}")

    @heist_group.command(name="launch", description="Launch your planned heist!")
    async def launch_heist(self, interaction: discord.Interaction):
        lobby = self.active_heists.get(interaction.user.id)
        if not lobby:
            await interaction.response.send_message("You haven't setup a heist yet! Use `/heist start`.", ephemeral=True)
            return
        
        target = lobby["target"]
        crew = lobby["crew"]
        crew_size = len(crew)
        
        # Skeleton check for required crew sizes
        if target == "jewelry_store" and crew_size < 2:
            await interaction.response.send_message("You need at least 2 people for the Jewelry Store!")
            return
        if target == "casino_vault" and crew_size < 3:
            await interaction.response.send_message("You need at least 3 people for the Casino Vault!")
            return

        # Basic Skeleton outcome generator
        success_chance = random.randint(1, 100)
        
        # You will likely want to build this out!
        if success_chance > 40: # 60% win rate
            payout = random.randint(500, 2000) * crew_size
            share = payout // crew_size
            
            for user in crew:
                await database.update_balance(user.id, share)
                
            await interaction.response.send_message(f"🎉 SUCCESS! You hit the {target.replace('_', ' ')} cleanly and got away with **{payout}** chips to split between the crew (**{share}** chips each)!")
        else:
            await interaction.response.send_message(f"🚨 FAILED! The cops showed up at the {target.replace('_', ' ')}. You all got busted!")

        # Clean up lobby
        del self.active_heists[interaction.user.id]

async def setup(bot):
    await bot.add_cog(Heist(bot))
