import discord
from discord.ext import commands
from typing import Optional, Literal
from asyncpg import Connection

class Owner(commands.Cog, command_attrs = dict(hidden = True), description = "Commands for bot owner only."):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    async def cog_check(self, ctx: commands.Context) -> bool:
        if ctx.channel.type == discord.ChannelType.private:
            return False
        return True

    @commands.command()
    @commands.is_owner()
    async def reload(self, ctx, folder, extension):
        """
        Reloads the extension.
        Use `.` if in root directory. 
        """
        try:
            if folder == '.':
                await self.bot.reload_extension(extension)
            else:
                await self.bot.reload_extension(f'{folder}.{extension}')
        
        except commands.errors.ExtensionNotFound:
            await ctx.send("Extension does not exist")
        
        else:
            await ctx.send("extension has been reloaded!")

    @commands.command()
    @commands.is_owner()
    async def load(self, ctx, folder, extension):
        """
        Load an extension.
        Use `.` if already in root directory.
        """
        try:
            if folder == '.':
                await self.bot.load_extension(extension)
            else:
                await self.bot.load_extension(f'{folder}.{extension}')
        
        except commands.errors.ExtensionAlreadyLoaded:
            return await ctx.send("Extension already loaded.")
        
        await ctx.send("Extension has been loaded!")

    @commands.command()
    @commands.is_owner()
    async def unload(self, ctx, folder, extension):
        """
        Unload an extension.
        Use `.` if already in root directory.
        """
        try:
            if folder == '.':
                await self.bot.unload_extension(extension)
            else:
                await self.bot.unload_extension(f'{folder}.{extension}')
        
        except commands.errors.ExtensionNotLoaded or commands.errors.ExtensionNotFound:
            await ctx.send("Extension failed to unload. Check if it exists and was not loaded in the first place.")
        
        else:
            await ctx.send("Extension has been unloaded!")

    @commands.command()
    @commands.guild_only()
    @commands.is_owner()
    async def sync(self, ctx: commands.Context, guilds: commands.Greedy[discord.Object], spec: Optional[Literal["~", "*", "^"]] = None) -> None:
        """
        Sync commands.
        `~` for syncing current guild
        `*` for copying global app commands to current guild and then syncing
        `^` for clearing all commands from current guild and then syncing (removes guild commands)
        To globally sync, do not suffix with any literal 
        """
        # by Umbra#0009

        # procedure: sync * THEN sync ^ THEN sync
        if not guilds:
            if spec == "~":
                # sync current guild
                synced = await ctx.bot.tree.sync(guild=ctx.guild)
            elif spec == "*":
                # copies all global app commands to current guild and syncs
                ctx.bot.tree.copy_global_to(guild=ctx.guild)
                synced = await ctx.bot.tree.sync(guild=ctx.guild)
            elif spec == "^":
                # clears all commands from the current guild target and syncs (removes guild commands)
                ctx.bot.tree.clear_commands(guild=ctx.guild)
                await ctx.bot.tree.sync(guild=ctx.guild)
                synced = []
            else:
                # global sync
                synced = await ctx.bot.tree.sync()

            await ctx.send(
                f"Synced {len(synced)} commands {'globally' if spec is None else 'to the current guild.'}"
            )
            return

        ret = 0
        for guild in guilds:
            # syncs specified guilds
            try:
                await ctx.bot.tree.sync(guild=guild)
            except discord.HTTPException:
                pass
            else:
                ret += 1

        await ctx.send(f"Synced the tree to {ret}/{len(guilds)}.")

    @commands.command()
    @commands.is_owner()
    async def test(self, ctx: commands.Context):
        """
        A simple command that can be used for testing.
        """
        await ctx.send("test successful!")


class MasterSetup(commands.Cog, command_attrs = dict(hidden = True), description = "Setup commands to use after inviting the bot"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @commands.command()
    @commands.is_owner()
    async def dbsetup(self, ctx: commands.Context):
        """Setup the database"""

        conn: Connection = self.bot.pool

        # GUILD TABLE
        await conn.execute("""CREATE TABLE IF NOT EXISTS guild_table (
            guild_id BIGINT primary key,
            blacklisted_channels BIGINT [] DEFAULT '{}',
            offence_message TEXT,
            prefix varchar (20)
        )""")

        # WARNS: THRESHOLD PUNISHMENTS
        await conn.execute("""CREATE TABLE IF NOT EXISTS autopunishments (
            id bigserial primary key,
            guild_id BIGINT,
            points INT NOT NULL,
            p_type varchar (10) NOT NULL,
            timer INTERVAL
        )""")

        # WARNS: WARN REASON AUTOCOMPLETES
        await conn.execute("""CREATE TABLE IF NOT EXISTS autocompletes(
            id bigserial primary key,
            guild_id BIGINT,
            points INT,
            reason TEXT
        )""")

        # VERIFICATION / JOIN ROLES
        await conn.execute("""CREATE TABLE IF NOT EXISTS join_stats (
            guild_id BIGINT PRIMARY KEY,
            verify_role BIGINT,
            verify_channel BIGINT,
            verify_message BIGINT,
            join_role_u BIGINT,
            join_role_b BIGINT
            )""")

        # POLLS
        await conn.execute("""CREATE TABLE IF NOT EXISTS poll_table (
            id bigserial PRIMARY KEY,
            message_id BIGINT,
            creator_id bigint not null,
            poll_options TEXT [] NOT NULL,
            multi_option bool DEFAULT true,
            option_votes INT [],
            used_users JSON
        )""")        

        # TAGS
        await conn.execute("""CREATE TABLE IF NOT EXISTS tags (
            id bigserial primary key,
            guild_id BIGINT NOT NULL,
            tag_name varchar(255) NOT NULL,
            body TEXT,
            created_by BIGINT NOT NULL,
            created_on TIMESTAMP WITH TIME ZONE NOT NULL,
            aliases varchar(255) []
        )""")

        # BANNED USERS
        await conn.execute("""CREATE TABLE IF NOT EXISTS banned_users (
            id bigserial primary key,
            user_id BIGINT NOT NULL,
            guild_id BIGINT NOT NULL,
            wait_until TIMESTAMP WITH TIME ZONE
        )""")

        # WARNS LOGGING
        await conn.execute("""CREATE TABLE IF NOT EXISTS warns (
            id bigserial primary key,
            guild_id BIGINT NOT NULL,
            user_id BIGINT NOT NULL,
            body TEXT,
            points INT,
            created_by BIGINT NOT NULL,
            created_on TIMESTAMP WITH TIME ZONE NOT NULL
        )""")

        # OFFENCE LOGGING
        await conn.execute("""CREATE TABLE IF NOT EXISTS offences (
            id bigserial primary key,
            guild_id BIGINT NOT NULL,
            user_id BIGINT NOT NULL,
            punishment varchar (100) NOT NULL,
            body TEXT,
            pardoned bool DEFAULT FALSE,
            created_by BIGINT NOT NULL,
            created_on TIMESTAMP WITH TIME ZONE NOT NULL
        )""")

        # MARKOV TRIGRAM LOGGER
        await conn.execute("""CREATE TABLE IF NOT EXISTS markov_table (
            guild_id BIGINT primary key,
            channel_id BIGINT,
            trigrams TEXT [] DEFAULT '{}'
        )""")

        await ctx.send("Done!")

    @commands.command()
    @commands.guild_only()
    @commands.is_owner()
    async def register(self, ctx: commands.Context):
        """Register current guild to guild table."""

        if await self.bot.pool.fetchval("SELECT * FROM guild_table WHERE guild_id = $1", ctx.guild.id) is None:
            await self.bot.pool.execute("INSERT INTO guild_table (guild_id) VALUES ($1)", ctx.guild.id)
            return await ctx.send("Done!")
        
        await ctx.send("This guild is already registered.")


async def setup(bot: commands.Bot) -> None:

    await bot.add_cog(Owner(bot))
    await bot.add_cog(MasterSetup(bot))