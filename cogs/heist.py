import discord
from discord.ext import commands, tasks
from discord import app_commands
import random
import datetime
from data import database

class Heist(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Simple memory storage for active lobbies: {user_id: {"target": str, "crew": [discord.Member], "start_time": datetime}}
        self.active_heists = {} 
        # Timeouts: {user_id: datetime}
        self.heist_timeouts = {} 
        self.lobby_cleanup.start()

    def cog_unload(self):
        self.lobby_cleanup.cancel()

    @tasks.loop(seconds=15)
    async def lobby_cleanup(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        expired = [uid for uid, lobby in self.active_heists.items() if (now - lobby["start_time"]).total_seconds() > 120]
        for uid in expired:
            del self.active_heists[uid]

    heist_group = app_commands.Group(name="heist", description="Las Vegas Heist Roleplay commands")

    @heist_group.command(name="start", description="Start a new heist lobby")
    @app_commands.describe(target="Where do you want to rob?", role="What role do you want to play?")
    @app_commands.choices(target=[
        app_commands.Choice(name="Gas Station (Low Risk, 1-2 players)", value="gas_station"),
        app_commands.Choice(name="Jewelry Store (Medium Risk, 2-3 players)", value="jewelry_store"),
        app_commands.Choice(name="Casino Vault (High Risk, 3-4 players)", value="casino_vault")
    ])
    @app_commands.choices(role=[
        app_commands.Choice(name="Driver", value="Driver"),
        app_commands.Choice(name="Muscle", value="Muscle"),
        app_commands.Choice(name="Hacker", value="Hacker"),
        app_commands.Choice(name="Inside Man", value="Inside Man")
    ])
    async def start_heist(self, interaction: discord.Interaction, target: str, role: str):
        if interaction.user.id in self.heist_timeouts:
            expiry = self.heist_timeouts[interaction.user.id]
            if datetime.datetime.now(datetime.timezone.utc) < expiry:
                remaining = int((expiry - datetime.datetime.now(datetime.timezone.utc)).total_seconds())
                await interaction.response.send_message(f"You are laying low! Try again in {remaining} seconds.", ephemeral=True)
                return
            else:
                del self.heist_timeouts[interaction.user.id]

        if interaction.user.id in self.active_heists:
            await interaction.response.send_message("You already have an active heist lobby!", ephemeral=True)
            return
        
        roles = {"Driver": None, "Muscle": None, "Hacker": None, "Inside Man": None}
        roles[role] = interaction.user

        self.active_heists[interaction.user.id] = {
            "target": target,
            "roles": roles,
            "start_time": datetime.datetime.now(datetime.timezone.utc)
        }
        await interaction.response.send_message(
            f"💰 {interaction.user.mention} is planning a heist on a **{target.replace('_', ' ').title()}**!\n"
            f"Host is taking the **{role}** role. Anyone else want in?\n"
            f"(Use `/heist join {interaction.user.display_name} <role>`)\n"
            f"⏱️ You have **2 minutes** to launch the heist before the lobby expires."
        )

    @heist_group.command(name="join", description="Join an active heist lobby")
    @app_commands.describe(role="What role do you want to play?")
    @app_commands.choices(role=[
        app_commands.Choice(name="Driver", value="Driver"),
        app_commands.Choice(name="Muscle", value="Muscle"),
        app_commands.Choice(name="Hacker", value="Hacker"),
        app_commands.Choice(name="Inside Man", value="Inside Man")
    ])
    async def join_heist(self, interaction: discord.Interaction, host: discord.User, role: str):
        if interaction.user.id in self.heist_timeouts:
            expiry = self.heist_timeouts[interaction.user.id]
            if datetime.datetime.now(datetime.timezone.utc) < expiry:
                remaining = int((expiry - datetime.datetime.now(datetime.timezone.utc)).total_seconds())
                await interaction.response.send_message(f"You are laying low! Try again in {remaining} seconds.", ephemeral=True)
                return
            else:
                del self.heist_timeouts[interaction.user.id]

        lobby = self.active_heists.get(host.id)
        if not lobby:
            await interaction.response.send_message("That user doesn't have an active heist lobby.", ephemeral=True)
            return
        
        if interaction.user in lobby["roles"].values():
            await interaction.response.send_message("You are already in this heist crew!", ephemeral=True)
            return

        if lobby["roles"].get(role) is not None:
            await interaction.response.send_message(f"The **{role}** role is already filled!", ephemeral=True)
            return

        lobby["roles"][role] = interaction.user
        crew_names = ", ".join([f"{u.display_name} ({r})" for r, u in lobby["roles"].items() if u is not None])
        await interaction.response.send_message(f"😎 {interaction.user.mention} joined the heist as **{role}**!\nCurrent crew: {crew_names}")

    @heist_group.command(name="launch", description="Launch your planned heist!")
    @app_commands.describe(perk="Optional perk to boost your success chance")
    @app_commands.choices(perk=[
        app_commands.Choice(name="10% Boost", value="perk_10"),
        app_commands.Choice(name="15% Boost", value="perk_15"),
        app_commands.Choice(name="20% Boost", value="perk_20")
    ])
    async def launch_heist(self, interaction: discord.Interaction, perk: str = None):
        lobby = self.active_heists.get(interaction.user.id)
        if not lobby:
            await interaction.response.send_message("You haven't setup a heist yet! Use `/heist start`.", ephemeral=True)
            return
        
        target = lobby["target"]
        roles = lobby["roles"]
        crew = [u for u in roles.values() if u is not None]
        crew_size = len(crew)
        
        # Check for required roles
        if target == "gas_station":
            if not roles["Driver"]:
                return await interaction.response.send_message("You need a **Driver** for the Gas Station!", ephemeral=True)
        elif target == "jewelry_store":
            if not roles["Driver"] or not roles["Muscle"]:
                return await interaction.response.send_message("You need at least a **Driver** and **Muscle** for the Jewelry Store!", ephemeral=True)
        elif target == "casino_vault":
            if not roles["Driver"] or not roles["Muscle"] or not roles["Hacker"] or not roles["Inside Man"]:
                return await interaction.response.send_message("You need a full crew (**Driver, Muscle, Hacker, Inside Man**) for the Casino Vault!", ephemeral=True)

        # Configure mechanics per target
        if target == "gas_station":
            success_threshold = 50
            share = random.randint(100, 500)
            fail_penalty = 300
            timeout_duration = datetime.timedelta(seconds=30)
        elif target == "jewelry_store":
            success_threshold = 25
            share = random.randint(1000, 2000)
            fail_penalty = 700
            timeout_duration = datetime.timedelta(minutes=1)
        else: # casino_vault
            success_threshold = 7
            share = random.randint(4000, 5000)
            fail_penalty = 1500
            timeout_duration = datetime.timedelta(minutes=2)

        perk_name = ""
        if perk:
            inv = await database.get_inventory(interaction.user.id)
            if inv.get(perk, 0) < 1:
                return await interaction.response.send_message("You do not own that perk. Check `/inventory`.", ephemeral=True)
            
            # Deduct the perk
            await database.update_perk(interaction.user.id, perk, -1)
            
            # Apply boost
            if perk == "perk_10":
                success_threshold += 10
                perk_name = "10% Boost Perk"
            elif perk == "perk_15":
                success_threshold += 15
                perk_name = "15% Boost Perk"
            elif perk == "perk_20":
                success_threshold += 20
                perk_name = "20% Boost Perk"

        success_chance = random.randint(1, 100)
        
        if success_chance <= success_threshold:
            payout = share * crew_size
            
            for user in crew:
                await database.update_balance(user.id, share)
                
            perk_text = f"\n*Used {perk_name} for a better chance!*" if perk else ""
            await interaction.response.send_message(f"🎉 SUCCESS! You hit the {target.replace('_', ' ').title()} cleanly and got away with **{payout}** chips to split between the crew (**{share}** chips each)!{perk_text}")
        else:
            expiry_time = datetime.datetime.now(datetime.timezone.utc) + timeout_duration
            for user in crew:
                await database.update_balance(user.id, -fail_penalty)
                self.heist_timeouts[user.id] = expiry_time
                        
            # Format time duration neatly
            mins = timeout_duration.total_seconds() // 60
            secs = timeout_duration.total_seconds() % 60
            time_str = f"{int(mins)}m {int(secs)}s" if mins > 0 else f"{int(secs)}s"
            
            perk_text = f"\n*Even with the {perk_name}, luck was not on your side.*" if perk else ""
            await interaction.response.send_message(f"🚨 FAILED! The cops showed up at the {target.replace('_', ' ').title()}. You all got busted! Each crew member lost **{fail_penalty}** chips and is in time-out for **{time_str}**!{perk_text}")

        # Clean up lobby
        del self.active_heists[interaction.user.id]

async def setup(bot):
    await bot.add_cog(Heist(bot))
