import discord
from discord.ext import commands
import sys
import traceback
from datetime import datetime,timedelta

"""
Built on example error handler from EvieePy
"""

class CommandErrorHandler(commands.Cog, command_attrs = dict(hidden = True)):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx:commands.Context, error):
        '''
        Outputs an error
        '''

        # This prevents any commands with local handlers being handled here in on_command_error.
        if hasattr(ctx.command, 'on_error'):
            return

        # This prevents any cogs with an overwritten cog_command_error being handled here.
        cog = ctx.cog
        if cog:
            if cog._get_overridden_method(cog.cog_command_error) is not None:
                return

        ignored = (commands.CommandNotFound, )

        # Allows us to check for original exceptions raised and sent to CommandInvokeError.
        # If nothing is found. We keep the exception passed to on_command_error.

        error = getattr(error, 'original', error)

        if isinstance(error, ignored):
            return

        if isinstance(error,commands.MissingRequiredArgument):
            await ctx.send(f"You have not typed the required arguments!\nView `help {ctx.command.name}` to learn more.", delete_after = 5, ephemeral = True)
        
        elif isinstance(error,commands.BadArgument) or isinstance(error, discord.app_commands.errors.TransformerError):
            await ctx.send(f"You have not typed the arguments correctly!\nView `help {ctx.command.name}` to learn more.", delete_after = 5, ephemeral = True)
        
        elif isinstance(error,commands.CommandOnCooldown):
            now = datetime.now() + timedelta(seconds=error.retry_after)
            await ctx.send(f"You can use this command again **{discord.utils.format_dt(now,'R')}**",delete_after = 5 ,ephemeral = True)
        
        elif isinstance(error, commands.MissingPermissions) or isinstance(error, commands.BotMissingPermissions):
            await ctx.send("You do not have permissions to run this command.", ephemeral = True, delete_after = 5)
        
        elif isinstance(error,commands.CheckFailure) or isinstance(error, discord.errors.NotFound):
            pass

        else:
            print('Ignoring exception in command {}:'.format(ctx.command), file=sys.stderr)
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)


async def setup(bot: commands.Bot) -> None:

    await bot.add_cog(CommandErrorHandler(bot))
