import discord
from discord.ext import commands

EXTRA_INFO = {
    "blackjack": "🃏 **Rules**: Standard Blackjack rules. You must beat the Dealer's hand without going over 21. Dealer hits until 17.\n💰 **Payouts**:\n- Normal Win: 2x Bet\n- Blackjack: 2.5x Bet (3:2 payout)\n- Tie (Push): Bet refunded",
    "crash": "📈 **Rules**: The multiplier will steadily rise. You must hit 'Cash Out' before the game randomly crashes (between 1.0x and 5.0x).\n💰 **Payouts**: Bet multiplied by your cash-out multiplier. If you crash, you lose it all.",
    "slots": "🎰 **Rules**: 3x3 slot machine. You win if you match 3 identical symbols in any horizontal row.\n💰 **Odds & Multipliers**:\n🍒 `(x2)` | 🍋 `(x3)` | 🍇 `(x5)`\n🔔 `(x10)` | 💎 `(x20)` | 7️⃣ `(x50)`",
    "duel": "⚔️ **Rules**: A 1v1 Rock-Paper-Scissors style duel with 5 weapons.\n🔫 Revolver beats Switchblade & Knuckles\n🔪 Switchblade beats Wire & Poison\n👊 Knuckles beat Switchblade & Wire\n🪢 Wire beats Revolver & Poison\n🧪 Poison beats Revolver & Knuckles\n💰 **Payout**: Winner takes the entire pot (2x Bet).",
    "loan": "🦈 **Rules**: The Loan Shark will lend you chips, but adds a 50% interest fee instantly. You must use `/payback` to clear it within 24 hours.\n⚠️ **Penalty**: 1.3x of your owed amount is placed as a Bounty on your head!",
    "bounty_hunt": "🚨 **Rules**: Attempt to arrest a player with an active bounty. There is a **50% base chance** of catching them.\n💰 **Payout**: You receive their full bounty amount in chips.",
    "heist": "💰 **Rules**: Plan a robbery! Choose a target and recruit players.\n- **Gas Station**: High chance (50%), Low payout.\n- **Jewelry Store**: Medium chance (25%), Medium payout.\n- **Casino Vault**: Low chance (7%), Massive payout.\n🔥 **Boosts**: Having an 'Optimal Crew' (filling needed roles) adds +7.5% success chance. Perks add up to +20%!"
}

class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(name="help", description="Shows a list of all commands, or get details on a specific command.")
    @discord.app_commands.describe(command_name="The specific command to get more details about (optional)")
    async def help_command(self, interaction: discord.Interaction, command_name: str = None):
        commands_list = self.bot.tree.get_commands()
        
        if command_name:
            cmd_name_lower = command_name.lower().strip()
            if cmd_name_lower.startswith("/"):
                cmd_name_lower = cmd_name_lower[1:]
                
            found_cmd = next((c for c in commands_list if c.name == cmd_name_lower), None)
            
            if not found_cmd:
                return await interaction.response.send_message(f"❌ Command `{cmd_name_lower}` not found.", ephemeral=True)
                
            embed = discord.Embed(
                title=f"Command: /{found_cmd.name}",
                description=found_cmd.description or "No description provided.",
                color=discord.Color.gold()
            )
            
            if hasattr(found_cmd, 'parameters') and found_cmd.parameters:
                params_text = ""
                for param in found_cmd.parameters:
                    req = "Required" if param.required else "Optional"
                    params_text += f"- **{param.name}** ({req})\n> {param.description}\n"
                embed.add_field(name="Arguments / Options", value=params_text, inline=False)
                
            if hasattr(found_cmd, 'choices') and found_cmd.choices:
                 for param in found_cmd.parameters:
                     if param.choices:
                         choices_text = ", ".join(f"`{c.name}`" for c in param.choices)
                         embed.add_field(name=f"Choices for '{param.name}'", value=choices_text, inline=False)

            if found_cmd.name in EXTRA_INFO:
                embed.add_field(name="📜 Rules & Odds", value=EXTRA_INFO[found_cmd.name], inline=False)

            embed.set_footer(text="May the odds be ever in your favor!")
            await interaction.response.send_message(embed=embed)
            
        else:
            embed = discord.Embed(
                title="Las Vegas Bot - Help Menu",
                description="Here is a list of all available commands.\nTip: Type `/help <command_name>` for details on a specific command.",
                color=discord.Color.blurple()
            )
            
            for cmd in commands_list:
                embed.add_field(
                    name=f"/{cmd.name}", 
                    value=cmd.description or "No description provided.", 
                    inline=False
                )
                
            embed.set_thumbnail(url=self.bot.user.display_avatar.url if self.bot.user.display_avatar else self.bot.user.default_avatar.url)
            embed.set_footer(text="May the odds be ever in your favor!")
            
            await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Help(bot))
