import discord
from discord.ext import commands
from asyncpg import Connection
from typing import Mapping

SERVER_LINK = "https://discord.gg/gjRfPR8Rcm"
EMBED_COLOR = discord.Color.from_str("#6f9c6b")

class MyHelpCommand(commands.HelpCommand):

    async def send_bot_help(self, mapping: Mapping):
        ctx = self.context
        conn: Connection = ctx.bot.pool

        desc = "Use `help <command>` or `help <category>` to learn more about a specific command or category."

        embed = discord.Embed(title="Help Module", color = EMBED_COLOR, description = desc)
        categ_list = []

        for cog, commands in mapping.items():
            cog_name = cog.qualified_name if cog is not None else None
            
            if cog_name is None:
                continue

            filtered = await self.filter_commands(commands)
            if filtered:
                comms = [f'`{command.qualified_name}`' for command in filtered]
                val = f"**__{cog_name.capitalize()}__**\n{', '.join(comms)}"
                categ_list.append(val)

        embed.add_field(name = "Help for newbies", value = "Use `help Setup` to see useful info for setup commands for this server.")
        embed.add_field(name = "Contribute", value = f"Found a bug? Or want to request a feature? Join here:\n{SERVER_LINK}")
        embed.add_field(name = "Categories", value = '\n'.join(categ_list), inline = False)
        channel = self.get_destination()
        await channel.send(embed=embed)

    async def send_cog_help(self, cog: commands.Cog, /) -> None:
        em = discord.Embed(color = EMBED_COLOR, title = f"Category: {cog.qualified_name.capitalize()}",
        description = f"{cog.description if cog.description is not None else 'No description given'}")

        filtered = await self.filter_commands(cog.walk_commands())

        if not filtered:
            return await self.context.send("Hidden category.", delete_after = 5)

        for command in filtered:
            em.add_field(name = f"`{command.qualified_name} {command.signature}`",
            value = f"{command.description or 'No description given'}\n\
                **Aliases:** {', '.join(f'`{alias}`' for alias in command.aliases) if len(command.aliases) > 1 else '`None`'}",
            inline = False)

        channel = self.get_destination()
        await channel.send(embed = em)

    async def send_command_help(self, command: commands.Command):
        embed = discord.Embed(color = EMBED_COLOR, title = f"`{command.qualified_name} {command.signature}`")
        
        embed.add_field(name = "Description", value = command.description or "No description given")
        aliases = command.aliases
        
        if aliases:
            embed.add_field(name = "Aliases", value = ", ".join(f'`{alias}`' for alias in aliases), inline = False)

        channel = self.get_destination()
        await channel.send(embed=embed)

    async def send_error_message(self, error):
        channel = self.get_destination()
        await channel.send(f"An error occured: {error}")

    async def send_group_help(self, group: commands.Group):
        embed = discord.Embed(color = EMBED_COLOR, title = f"Group: {group.qualified_name}")

        for command in group.commands:
            embed.add_field(name = f"`{command.qualified_name} {command.signature}`",
            value = f"{command.description or 'No description given'}\n\
                **Aliases:** {', '.join(f'`{alias}`' for alias in command.aliases) if len(command.aliases) > 1 else '`None`'}",
            inline = False)

        channel = self.get_destination()
        await channel.send(embed = embed)


class Help(commands.Cog):
    # by Vex
    def __init__(self, bot):
        self.bot = bot
        self._original_help_command = bot.help_command
        bot.help_command.cog = self
        help_comm = MyHelpCommand()
        help_comm.command_attrs = {"help": "The help command for the bot", "cooldown": commands.CooldownMapping.from_cooldown(2, 5,
        commands.BucketType.user),"aliases": ['commands','help']}
        
        bot.help_command = help_comm
        
    def cog_unload(self):
        self.bot.help_command = self._original_help_command

async def setup(bot: commands.Bot) -> None:

    await bot.add_cog(Help(bot))