import discord
from discord.ext import commands, tasks
from discord import app_commands
import random
import asyncio
import datetime
from data import database
from utils.image_gen import render_heist_result

# ── Target Configuration ──────────────────────────────────────────────────────

TARGET_CONFIG = {
    "gas_station": {
        "name": "Gas Station",
        "emoji": "⛽",
        "risk": "Low",
        "players": "1–2",
        "color": discord.Color.green(),
        "success_threshold": 50,
        "share_range": (100, 500),
        "fail_penalty": 300,
        "timeout": datetime.timedelta(seconds=30),
        "cinematic": [
            "🚗 *The crew rolls up in a blacked-out car. Engine running, lights off...*",
            "⛽ *The Driver keeps watch. Someone vaults the counter in under 10 seconds...*",
            "💰 *Register cleaned out. Back in the car. Tires screech into the night...*",
        ],
    },
    "jewelry_store": {
        "name": "Jewelry Store",
        "emoji": "💍",
        "risk": "Medium",
        "players": "2–3",
        "color": discord.Color.blue(),
        "success_threshold": 25,
        "share_range": (1000, 2000),
        "fail_penalty": 700,
        "timeout": datetime.timedelta(minutes=1),
        "cinematic": [
            "🕶️ *The crew cases the store from across the street. Two guards. One camera blind spot...*",
            "💥 *Muscle smashes the display cases. Alarms start screaming. Glass everywhere...*",
            "💎 *Diamonds swept into duffel bags. Driver is screaming on the radio — sixty seconds!*",
        ],
    },
    "casino_vault": {
        "name": "Casino Vault",
        "emoji": "🎰",
        "risk": "High",
        "players": "3–4",
        "color": discord.Color.gold(),
        "success_threshold": 7,
        "share_range": (4000, 5000),
        "fail_penalty": 1500,
        "timeout": datetime.timedelta(minutes=2),
        "cinematic": [
            "🃏 *Inside Man signals from the floor: guard rotation window is open. Thirty seconds.*",
            "💻 *Hacker kills the cameras and brute-forces the electronic vault lock. Sweat dripping...*",
            "💪 *Muscle holds the floor — tourists zip-tied, security down. Nobody moves.*",
            "🏦 *The vault door swings open. Rows upon rows of casino chips. Breathtaking.*",
        ],
    },
}

ALL_ROLES = ["Driver", "Muscle", "Hacker", "Inside Man"]
ROLE_EMOJIS = {"Driver": "🚗", "Muscle": "💪", "Hacker": "💻", "Inside Man": "🕵️"}
PERK_INFO = {
    "perk_10": ("10% Boost", "🔸", 10),
    "perk_15": ("15% Boost", "🔹", 15),
    "perk_20": ("20% Boost", "🌟", 20),
}


# ── Helper: send embed with file, falling back to embed-only on 403 ───────────

async def send_result(channel: discord.abc.Messageable, embed: discord.Embed, buf) -> None:
    """Send an embed with an image file. Falls back to embed-only if 403 Forbidden."""
    result_file = discord.File(buf, filename="heist_result.png")
    embed.set_image(url="attachment://heist_result.png")
    try:
        await channel.send(embed=embed, file=result_file)
    except discord.Forbidden:
        embed.set_image(url=None)  # clear the attachment reference
        await channel.send(embed=embed)


# ── Lobby Embed Builder ───────────────────────────────────────────────────────

def build_lobby_embed(
    host: discord.User, target_key: str, roles: dict, expires_at: datetime.datetime
) -> discord.Embed:
    cfg = TARGET_CONFIG[target_key]
    embed = discord.Embed(
        title=f"{cfg['emoji']}  Heist Lobby — {cfg['name']}",
        color=cfg["color"],
    )
    embed.set_author(
        name=f"Planned by {host.display_name}",
        icon_url=host.display_avatar.url if host.display_avatar else host.default_avatar.url,
    )
    embed.add_field(name="⚠️ Risk Level", value=cfg["risk"], inline=True)
    embed.add_field(name="👥 Ideal Size", value=cfg["players"], inline=True)
    ts = int(expires_at.timestamp())
    embed.add_field(name="⏱️ Expires", value=f"<t:{ts}:R>", inline=True)

    roster = ""
    for r in ALL_ROLES:
        emoji = ROLE_EMOJIS[r]
        user = roles.get(r)
        if user:
            roster += f"{emoji} **{r}**: ✅ {user.display_name}\n"
        else:
            roster += f"{emoji} **{r}**: 🔲 *Open*\n"

    embed.add_field(name="👤 Crew Roster", value=roster, inline=False)
    embed.set_footer(text="Press 'Join Crew' to pick a role  •  Only the host can Launch")
    return embed


# ── UI: Ephemeral Role Picker ─────────────────────────────────────────────────

class RoleSelect(discord.ui.Select):
    def __init__(self, lobby_view: "HeistLobbyView", joiner: discord.User):
        self.lobby_view = lobby_view
        self.joiner = joiner
        options = [
            discord.SelectOption(
                label=r,
                emoji=ROLE_EMOJIS[r],
                description=f"Join as the {r}",
            )
            for r in ALL_ROLES
            if lobby_view.roles.get(r) is None
        ]
        super().__init__(
            placeholder="Choose your role…",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.joiner:
            return await interaction.response.send_message("This isn't your picker!", ephemeral=True)
        chosen = self.values[0]
        await interaction.response.defer()
        await self.lobby_view.add_member(self.joiner, chosen, interaction)
        self.view.stop()


class RoleSelectView(discord.ui.View):
    def __init__(self, lobby_view: "HeistLobbyView", joiner: discord.User):
        super().__init__(timeout=30)
        self.add_item(RoleSelect(lobby_view, joiner))


# ── UI: Ephemeral Perk Picker (shown to host before launch) ──────────────────

class PerkSelect(discord.ui.Select):
    def __init__(self, inv: dict, lobby_view: "HeistLobbyView", trigger: discord.Interaction):
        self.lobby_view = lobby_view
        self.trigger = trigger
        options = [discord.SelectOption(label="No Perk — Launch Now", value="none", emoji="🚀")]
        for k, (label, emoji, _) in PERK_INFO.items():
            if inv.get(k, 0) > 0:
                options.append(discord.SelectOption(label=label, value=k, emoji=emoji))
        super().__init__(
            placeholder="Use a perk? (optional)",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.lobby_view.host:
            return await interaction.response.send_message("Only the host!", ephemeral=True)
        chosen = self.values[0] if self.values[0] != "none" else None
        await interaction.response.defer()
        self.view.stop()
        await self.lobby_view._do_launch(self.trigger, chosen)


class PerkSelectView(discord.ui.View):
    def __init__(self, inv: dict, lobby_view: "HeistLobbyView", trigger: discord.Interaction):
        super().__init__(timeout=20)
        self.add_item(PerkSelect(inv, lobby_view, trigger))


# ── Main Interactive Lobby View ───────────────────────────────────────────────

class HeistLobbyView(discord.ui.View):
    def __init__(
        self,
        host: discord.User,
        target_key: str,
        host_role: str,
        expires_at: datetime.datetime,
        cog: "Heist",
    ):
        timeout_secs = (expires_at - datetime.datetime.now(datetime.timezone.utc)).total_seconds()
        super().__init__(timeout=max(timeout_secs, 1))
        self.host = host
        self.target_key = target_key
        self.roles: dict = {r: None for r in ALL_ROLES}
        self.roles[host_role] = host
        self.expires_at = expires_at
        self.cog = cog
        self.message: discord.Message | None = None
        self.launched = False

    async def add_member(self, user: discord.User, role: str, interaction: discord.Interaction):
        """Called from the ephemeral role picker after user picks their role."""
        if self.launched:
            return await interaction.followup.send("❌ The heist already launched!", ephemeral=True)
        if user in self.roles.values():
            return await interaction.followup.send("❌ You're already in the crew!", ephemeral=True)
        if self.roles.get(role) is not None:
            return await interaction.followup.send(
                f"❌ **{role}** was just filled! Try again.", ephemeral=True
            )

        self.roles[role] = user

        embed = build_lobby_embed(self.host, self.target_key, self.roles, self.expires_at)
        if self.message:
            await self.message.edit(embed=embed, view=self)

        await interaction.followup.send(
            f"{ROLE_EMOJIS[role]} **{user.display_name}** joined the crew as **{role}**!"
        )

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            embed = build_lobby_embed(self.host, self.target_key, self.roles, self.expires_at)
            embed.color = discord.Color.dark_gray()
            embed.set_footer(text="⌛ Lobby expired — the plan fell apart.")
            try:
                await self.message.edit(embed=embed, view=self)
            except Exception:
                pass
        self.cog.active_heists.pop(self.host.id, None)

    # ── Buttons ──────────────────────────────────────────────────────────────

    @discord.ui.button(label="Join Crew", style=discord.ButtonStyle.primary, emoji="🤝")
    async def btn_join(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.launched:
            return await interaction.response.send_message("The heist already launched!", ephemeral=True)
        if interaction.user == self.host:
            return await interaction.response.send_message(
                "You're already in this heist as the host!", ephemeral=True
            )
        if interaction.user in self.roles.values():
            return await interaction.response.send_message(
                "You're already in this crew!", ephemeral=True
            )

        if interaction.user.id in self.cog.heist_timeouts:
            expiry = self.cog.heist_timeouts[interaction.user.id]
            if datetime.datetime.now(datetime.timezone.utc) < expiry:
                remaining = int(
                    (expiry - datetime.datetime.now(datetime.timezone.utc)).total_seconds()
                )
                return await interaction.response.send_message(
                    f"🚨 You're laying low! **{remaining}s** until you can join again.", ephemeral=True
                )
            else:
                del self.cog.heist_timeouts[interaction.user.id]

        open_roles = [r for r, u in self.roles.items() if u is None]
        if not open_roles:
            return await interaction.response.send_message("All roles are filled!", ephemeral=True)

        role_view = RoleSelectView(self, interaction.user)
        await interaction.response.send_message(
            "🎭 **Pick your role in the crew:**", view=role_view, ephemeral=True
        )

    @discord.ui.button(label="Launch Heist", style=discord.ButtonStyle.danger, emoji="🚀")
    async def btn_launch(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.host:
            return await interaction.response.send_message(
                "Only the host can launch the heist!", ephemeral=True
            )
        if self.launched:
            return await interaction.response.send_message("Already launching!", ephemeral=True)

        self.launched = True

        inv = await database.get_inventory(self.host.id)
        has_perks = any(inv.get(k, 0) > 0 for k in PERK_INFO)

        if has_perks:
            perk_view = PerkSelectView(inv, self, interaction)
            await interaction.response.send_message(
                "🎒 **You have perks available!** Use one to boost your success chance?",
                view=perk_view,
                ephemeral=True,
            )
        else:
            await interaction.response.defer()
            await self._do_launch(interaction, None)

    async def _do_launch(self, interaction: discord.Interaction, perk: str | None):
        """Finalise lobby UI and hand off to the cog's execute_heist."""
        for child in self.children:
            child.disabled = True
        if self.message:
            embed = build_lobby_embed(self.host, self.target_key, self.roles, self.expires_at)
            embed.set_footer(text="🚀 The heist is underway — good luck!")
            await self.message.edit(embed=embed, view=self)

        self.cog.active_heists.pop(self.host.id, None)
        self.stop()

        await self.cog.execute_heist(interaction, self.host, self.target_key, self.roles, perk)


# ── Heist Cog ────────────────────────────────────────────────────────────────

class Heist(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_heists: dict = {}
        self.heist_timeouts: dict = {}
        self.lobby_cleanup.start()

    def cog_unload(self):
        self.lobby_cleanup.cancel()

    @tasks.loop(seconds=15)
    async def lobby_cleanup(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        expired = [
            uid
            for uid, lobby in self.active_heists.items()
            if (now - lobby["start_time"]).total_seconds() > 120
        ]
        for uid in expired:
            del self.active_heists[uid]

    heist_group = app_commands.Group(name="heist", description="Las Vegas Heist Roleplay commands")

    @heist_group.command(name="start", description="Start a new heist lobby")
    @app_commands.describe(target="Where do you want to rob?", role="What role do you want to play?")
    @app_commands.choices(
        target=[
            app_commands.Choice(name="Gas Station (Low Risk, 1-2 players)", value="gas_station"),
            app_commands.Choice(name="Jewelry Store (Medium Risk, 2-3 players)", value="jewelry_store"),
            app_commands.Choice(name="Casino Vault (High Risk, 3-4 players)", value="casino_vault"),
        ]
    )
    @app_commands.choices(
        role=[
            app_commands.Choice(name="Driver", value="Driver"),
            app_commands.Choice(name="Muscle", value="Muscle"),
            app_commands.Choice(name="Hacker", value="Hacker"),
            app_commands.Choice(name="Inside Man", value="Inside Man"),
        ]
    )
    async def start_heist(self, interaction: discord.Interaction, target: str, role: str):
        await interaction.response.defer()

        if interaction.user.id in self.heist_timeouts:
            expiry = self.heist_timeouts[interaction.user.id]
            if datetime.datetime.now(datetime.timezone.utc) < expiry:
                remaining = int(
                    (expiry - datetime.datetime.now(datetime.timezone.utc)).total_seconds()
                )
                return await interaction.followup.send(
                    f"🚨 You're **laying low**! Try again in **{remaining}s**.", ephemeral=True
                )
            else:
                del self.heist_timeouts[interaction.user.id]

        if interaction.user.id in self.active_heists:
            return await interaction.followup.send(
                "You already have an active heist lobby!", ephemeral=True
            )

        expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=2)
        self.active_heists[interaction.user.id] = {
            "target": target,
            "start_time": datetime.datetime.now(datetime.timezone.utc),
        }

        view = HeistLobbyView(interaction.user, target, role, expires_at, self)
        embed = build_lobby_embed(interaction.user, target, view.roles, expires_at)

        await interaction.followup.send(embed=embed, view=view)
        view.message = await interaction.original_response()

    async def execute_heist(
        self,
        interaction: discord.Interaction,
        host: discord.User,
        target_key: str,
        roles: dict,
        perk: str | None,
    ):
        cfg = TARGET_CONFIG[target_key]
        crew = [u for u in roles.values() if u is not None]
        crew_size = len(crew)

        # interaction.channel can be None when channel is not in cache after a button defer.
        channel = interaction.channel
        if channel is None:
            try:
                channel = self.bot.get_channel(interaction.channel_id) or await self.bot.fetch_channel(interaction.channel_id)
            except Exception:
                return

        try:
            # ── Cinematic sequence ────────────────────────────────────────────
            cinematic_msg = await channel.send(
                "🎬 *The plan is set. Everyone moves to their positions...*"
            )
            await asyncio.sleep(2.0)

            for line in cfg["cinematic"]:
                await cinematic_msg.edit(content=line)
                await asyncio.sleep(2.2)

            await cinematic_msg.edit(content="⏳ *The moment of truth...*")
            await asyncio.sleep(2.0)

            # ── Calculate success ─────────────────────────────────────────────
            success_threshold = cfg["success_threshold"]

            optimal_crew = False
            if target_key == "gas_station" and roles.get("Driver"):
                optimal_crew = True
            elif target_key == "jewelry_store" and roles.get("Driver") and roles.get("Muscle"):
                optimal_crew = True
            elif target_key == "casino_vault" and all(roles.get(r) for r in ALL_ROLES):
                optimal_crew = True

            if optimal_crew:
                success_threshold += 7.5

            perk_name = None
            if perk and perk in PERK_INFO:
                inv = await database.get_inventory(host.id)
                if inv.get(perk, 0) >= 1:
                    label, _, boost = PERK_INFO[perk]
                    await database.update_perk(host.id, perk, -1)
                    success_threshold += boost
                    perk_name = label

            roll = random.randint(1, 100)
            success = roll <= success_threshold
            share = random.randint(*cfg["share_range"])
            crew_names = [u.display_name for u in crew]

            await cinematic_msg.delete()

            # ── Apply outcome ─────────────────────────────────────────────────
            if success:
                payout = share * crew_size
                for user in crew:
                    await database.update_balance(user.id, share)

                modifier_lines = []
                if perk_name:
                    modifier_lines.append(f"🎒 Used **{perk_name}** perk")
                if optimal_crew:
                    modifier_lines.append("👥 Perfect crew gave **+7.5%** success chance")

                desc = (
                    f"You hit the **{cfg['name']}** and got away clean!\n\n"
                    f"💰 **{share:,} chips each** *(total: {payout:,})*"
                )
                if modifier_lines:
                    desc += "\n\n" + "\n".join(modifier_lines)

                result_embed = discord.Embed(
                    title="🎉  HEIST SUCCESSFUL",
                    description=desc,
                    color=discord.Color.green(),
                )
                result_buf = render_heist_result(
                    target_name=cfg["name"],
                    target_emoji=cfg["emoji"],
                    crew=crew_names,
                    payout=payout,
                    share=share,
                    success=True,
                )
                await send_result(channel, result_embed, result_buf)

            else:
                timeout_dur = cfg["timeout"]
                expiry_time = datetime.datetime.now(datetime.timezone.utc) + timeout_dur
                for user in crew:
                    await database.update_balance(user.id, -cfg["fail_penalty"])
                    self.heist_timeouts[user.id] = expiry_time

                mins = int(timeout_dur.total_seconds() // 60)
                secs = int(timeout_dur.total_seconds() % 60)
                time_str = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"

                modifier_lines = []
                if perk_name:
                    modifier_lines.append(f"🎒 Even **{perk_name}** couldn't save you")
                if optimal_crew:
                    modifier_lines.append("👥 Even a perfect crew wasn't enough")

                desc = (
                    f"Cops swarmed the **{cfg['name']}**. Everyone got busted!\n\n"
                    f"💸 Each crew member lost **{cfg['fail_penalty']:,}** chips\n"
                    f"⏳ Laying low for **{time_str}**"
                )
                if modifier_lines:
                    desc += "\n\n" + "\n".join(modifier_lines)

                result_embed = discord.Embed(
                    title="🚨  HEIST FAILED — BUSTED!",
                    description=desc,
                    color=discord.Color.red(),
                )
                result_buf = render_heist_result(
                    target_name=cfg["name"],
                    target_emoji=cfg["emoji"],
                    crew=crew_names,
                    payout=cfg["fail_penalty"] * crew_size,
                    share=cfg["fail_penalty"],
                    success=False,
                )
                await send_result(channel, result_embed, result_buf)

        except Exception:
            import traceback
            traceback.print_exc()
            try:
                await channel.send(
                    "⚠️ An internal error occurred during the heist. Check the terminal for the full traceback."
                )
            except Exception:
                pass


async def setup(bot):
    await bot.add_cog(Heist(bot))
