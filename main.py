import discord
from discord.ext import commands
import asyncpg
from helper import poll_views, join_view
from os import getenv
from dotenv import load_dotenv

load_dotenv()
"test"
TOKEN = getenv("TOKEN")
DB_NAME = getenv("DB_NAME")
DB_USERNAME = getenv("DB_USERNAME")
DB_PASSWORD = getenv("DB_PASSWORD")

class MyBot(commands.Bot):
    async def setup_hook(self) -> None:
        try:
            self.pool = await asyncpg.create_pool(database = DB_NAME, user = DB_USERNAME, password = DB_PASSWORD)
            await self.load_extension('commands.moderation')
            await self.load_extension('helper.error_handler')
            await self.load_extension('commands.utility')
            await self.load_extension('commands.public')
            await self.load_extension('commands.owner')
            await self.load_extension('commands.setup')
            await self.load_extension('help_command')

            try:
                poll_records = await self.pool.fetch("SELECT * FROM poll_table")
            except asyncpg.UndefinedTableError:
                poll_records = []
            
            for record in poll_records:
                try:
                    self.add_view(poll_views.Poll(len(record['poll_options']), self.pool), message_id = record['message_id'])
                except:
                    pass

            try:
                verify_records = await self.pool.fetch("SELECT verify_message FROM join_stats")    
            except asyncpg.UndefinedTableError:
                verify_records = []
                        
            for record in verify_records:
                try:
                    self.add_view(join_view.VerifyMessageView(self.pool), message_id = record['verify_message'])
                except:
                    pass

        except KeyboardInterrupt:
            await self.pool.close()
            await self.logout()

async def get_prefix(bot: commands.Bot, message: discord.Message):
    try:
        prefix = await bot.pool.fetchval("SELECT prefix FROM guild_table WHERE guild_id = $1", message.guild.id)
    except:
        prefix = None

    if prefix is None:
        return [f"{bot.user.mention} ", bot.user.mention, '-']
    return [f"{bot.user.mention} ", bot.user.mention, prefix]

activity = discord.Activity(type=discord.ActivityType.watching, name="-help")
bot = MyBot(command_prefix = get_prefix, intents = discord.Intents.all(), activity = activity)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')

@bot.event
async def on_guild_join(guild: discord.Guild):
    if await bot.pool.fetchval("SELECT * FROM guild_table WHERE guild_id = $1", guild.id) is None:
            await bot.pool.execute("INSERT INTO guild_table (guild_id) VALUES ($1)", guild.id)

@bot.event
async def on_member_join(member: discord.Member):
    join_stats = await bot.pool.fetchrow("SELECT * FROM join_stats WHERE guild_id = $1", member.guild.id)

    if join_stats is None:
        return

    verify_role = member.guild.get_role(join_stats['verify_role']) if join_stats['verify_role'] is not None else None
    user_role = member.guild.get_role(join_stats['join_role_u']) if join_stats['join_role_u'] is not None else None
    bot_role = member.guild.get_role(join_stats['join_role_b']) if join_stats['join_role_b'] is not None else None

    if not member.bot:
        if verify_role is not None:
            await member.add_roles(verify_role, reason = "Verification pending")
        
        elif user_role is not None:
            await member.add_roles(user_role, reason = "User joinrole")

    elif bot_role is not None:
        await member.add_roles(bot_role, reason = "Bot joinrole")


if __name__ == '__main__':
    bot.run(TOKEN)
