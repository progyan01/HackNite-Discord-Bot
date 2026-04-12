import discord
from discord.ext import commands

class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(name="help", description="Shows a list of all commands and their descriptions.")
    async def help_command(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Las Vegas Bot - Help Menu",
            description="Here is a list of all available commands:",
            color=discord.Color.blurple()
        )
        
        # self.bot.tree.get_commands() returns a list of all registered top-level slash commands
        for cmd in self.bot.tree.get_commands():
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
