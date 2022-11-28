import discord
from discord.ext import commands
from discord.ext.commands.cooldowns import BucketType
from typing import Optional
from helper.setup_views import AdditionalMessage, VerificationView, WarnView
from helper.other import time_unparser

EMBED_COLOR = discord.Color.from_str("#9fca77")

class Setup(commands.Cog, name = "setup"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_check(self, ctx: commands.Context) -> bool:
        # THIS IS ADMIN ONLY COG. ONLY PREFIX IS PUBLICALLY VIEWABLE
        
        if ctx.author.guild_permissions.administrator:
            return True
        elif ctx.command.name == "prefix" and len(ctx.args) == 0:
            prefix = await self.bot.pool.fetchval("SELECT prefix FROM guild_table WHERE guild_id = $1", ctx.guild.id)
            return await ctx.send(f"Prefix for this server is **`{prefix if prefix is not None else '-'}`**", delete_after = 10)
        else:
            await ctx.send("You do not have permissions to run this command.", ephemeral = True, delete_after = 5)
        return False

    @commands.cooldown(rate = 1, per = 5, type = BucketType.member)
    @commands.command(description = "Get or set the prefix")
    async def prefix(self, ctx: commands.Context, *, prefix: Optional[str]):
        if prefix is None:

            try:
                prefix = await self.bot.pool.fetchval("SELECT prefix FROM guild_table WHERE guild_id = $1", ctx.guild.id)
            except:
                prefix = None
        
            return await ctx.send(f"Prefix for this server is **`{prefix if prefix is not None else '-'}`**", delete_after = 10)
        
        if len(prefix) > 20:
            return await ctx.send("Prefix is too long. Keep it under 20 characters.", delete_after = 5)
        
        await self.bot.pool.execute("UPDATE guild_table SET prefix = $1 WHERE guild_id = $2", prefix, ctx.guild.id)

        await ctx.send(f"New prefix for the bot is: `{prefix}`")

    @commands.cooldown(rate = 1, per = 10, type = BucketType.member)
    @commands.hybrid_command(description = "Blacklist/whitelist channels from using commands.")
    async def blacklist(self, ctx: commands.Context, channels: commands.Greedy[discord.TextChannel] = None):
        b_c: list = await self.bot.pool.fetchval("SELECT blacklisted_channels FROM guild_table WHERE guild_id = $1", ctx.guild.id)

        if channels is not None:
            for channel in channels:
                if channel.guild != ctx.guild:
                    continue
                if channel.id in b_c:
                    b_c.remove(channel.id)
                else:
                    b_c.append(channel.id)
            
            await self.bot.pool.execute("UPDATE guild_table SET blacklisted_channels = $1 WHERE guild_id = $2", b_c, ctx.guild.id)

        desc_list = [ctx.guild.get_channel(c).mention for c in b_c] if len(b_c) > 0 else ['None']
        em = discord.Embed(color = EMBED_COLOR, title = "Blacklisted channels", description = '\n'.join(desc_list))

        await ctx.send(embed = em)

    @commands.cooldown(rate = 1, per = 5, type = BucketType.member)
    @commands.hybrid_group(invoke_without_command = True)
    async def set(self, ctx: commands.Context):
        pass
    
    @commands.cooldown(rate = 1, per = 5, type = BucketType.member)
    @set.command(description = "Set the additional DM message sent to the user during moderator actions", aliases = ['dm', 'dms'])
    async def message(self, ctx: commands.Context):
        
        add_msg = await self.bot.pool.fetchval("SELECT offence_message FROM guild_table WHERE guild_id = $1", ctx.guild.id)
        
        em = discord.Embed(color = EMBED_COLOR, title = "Additional message:", description = add_msg if add_msg is not None else 'None has been set')
        em.set_footer(text = "Set the additional DM message sent to the user during moderator actions (such as appeal server/form link)")
        
        view = AdditionalMessage(ctx.author, self.bot.pool)
        view.msg = await ctx.send(embed = em, view = view)

    @commands.cooldown(rate = 1, per = 5, type = BucketType.member)
    @set.command(description = "Setup verification for the server.", aliases = ['verify'])
    async def verification(self, ctx: commands.Context):
        join_stats = await self.bot.pool.fetchrow("SELECT * FROM join_stats WHERE guild_id = $1", ctx.guild.id)

        if join_stats is None:
            await self.bot.pool.execute("INSERT INTO join_stats (guild_id) VALUES ($1)", ctx.guild.id)
            join_stats = await self.bot.pool.fetchrow("SELECT * FROM join_stats WHERE guild_id = $1", ctx.guild.id)

        try:
            channel = await ctx.guild.fetch_channel(join_stats['verify_channel'])
            channel = channel.mention
        except:
            channel = "None has been set"
        
        try:
            role = ctx.guild.get_role(join_stats['verify_role'])
            if role > ctx.guild.me.roles[-1]:
                raise
            role = role.mention
        except:
            role = "None has been set"

        em = discord.Embed(color = EMBED_COLOR, title = "Verification setup",
        description = f"Channel: {channel}\nRole used: {role}")
        em.add_field(name = "How this works",
        value = "When the user joins, a role is given, which allows only viewing the verification channel. After verifying, the role is removed, and can\
optionally add another role (use `/joinrole` for that)")

        view = VerificationView(ctx.author, self.bot.pool)
        view.msg = await ctx.send(embed = em, view = view)

    @commands.cooldown(rate = 1, per = 5, type = BucketType.member)
    @set.command(description = "Gives a role upon joining, to a bot or user (works with verification system)", aliases = ['joinrole'])
    @discord.app_commands.describe(
        user_role = "Role to be given to the user",
        bot_role = "Role to be given to the bot",
        disable = "Set to true to set user role and bot role to none."
    )
    async def joinroles(self, ctx: commands.Context, user_role: Optional[discord.Role], bot_role: Optional[discord.Role], disable: Optional[bool]):
        if ctx.interaction:
            await ctx.interaction.response.defer()
        if disable is None:
            disable = False
        
        join_stats = await self.bot.pool.fetchrow("SELECT * FROM join_stats WHERE guild_id = $1", ctx.guild.id)

        if join_stats is None:
            await self.bot.pool.execute("INSERT INTO join_stats (guild_id) VALUES ($1)", ctx.guild.id)

        if disable:
            await self.bot.pool.execute("UPDATE join_stats SET join_role_u = NULL, join_role_b = NULL where guild_id = $1", ctx.guild.id)

        if user_role is not None and not disable:
            if user_role.guild == ctx.guild and user_role < ctx.guild.me.roles[-1]:
                await self.bot.pool.execute("UPDATE join_stats SET join_role_u = $1 WHERE guild_id = $2", user_role.id, ctx.guild.id)
            else:
                return await ctx.send("User role is inaccessible. Make sure it is below my top role.", ephemeral = True, delete_after = 5)

        if bot_role is not None and not disable:
            if bot_role.guild == ctx.guild and bot_role < ctx.guild.me.roles[-1]:
                await self.bot.pool.execute("UPDATE join_stats SET join_role_b = $1 WHERE guild_id = $2", bot_role.id, ctx.guild.id)
            else:
                return await ctx.send("Bot role is inaccessible. Make sure it is below my top role.", ephemeral = True, delete_after = 5)
                
        join_stats = await self.bot.pool.fetchrow("SELECT * FROM join_stats WHERE guild_id = $1", ctx.guild.id)

        if join_stats['join_role_u'] is None and join_stats['join_role_b'] is None:
            status = "Disabled"
        else:
            status = "Enabled"

        jr_u = ctx.guild.get_role(join_stats['join_role_u']).mention if join_stats['join_role_u'] is not None else "None"
        jr_b = ctx.guild.get_role(join_stats['join_role_b']).mention if join_stats['join_role_b'] is not None else "None"

        em = discord.Embed(color = EMBED_COLOR, title = f"{status}: Join roles", description = f"**User role**: {jr_u}\n**Bot role**: {jr_b}")

        await ctx.send(embed = em)

    @commands.cooldown(rate = 1, per = 5, type = BucketType.member)
    @set.command(name = "warning", description = "Setup the warning system.", aliases = ['warnings'])
    async def s_warning(self, ctx: commands.Context):
        '''
        Set up warning thresholds and autocompletes
        '''
        conn = self.bot.pool
        
        # EMBED DEFINITION
        em = discord.Embed(color = EMBED_COLOR, title = "Warnings")

        # SETTING UP FIELD 0, THRESHOLDS
        async def field_0():
            info = await conn.fetch("SELECT * FROM autopunishments WHERE guild_id=$1 ORDER BY points ASC", ctx.guild.id)
            info_dict = {"kick": "Kick", "mute": "Timeout ", "ban": "Permanent ban", "bant": "Ban "}
            threshold_value = [] # list of thresholds, unparsed

            if info == []:
                threshold_value.append("None")
            else:
                for x in info:
                    punishment = info_dict[x['p_type']]
                    if punishment in ['Timeout ','Ban ']:
                        punishment += time_unparser(x['timer'])

                    val = f"{x['points']} points; {punishment}"
                    threshold_value.append(val)
            return threshold_value

        field0_value = '\n'.join(await field_0())

        em.add_field(name = "Thresholds", value = f"```{field0_value}```")

        # SETTING UP FIELD 1, AUTOCOMPLETES
        async def field_1(max_points_rec):
            autocomplete_info = await conn.fetch("SELECT * FROM autocompletes WHERE guild_id=$1", ctx.guild.id)
            
            autocomplete_val = []
            if autocomplete_info == []:
                autocomplete_val = "None"
            else:
                for x in autocomplete_info:
                    autocomplete_val.append(f"`{x['reason']}` `{x['points']}`")
                autocomplete_val = ", ".join(autocomplete_val)
            
            maximum = "None" if max_points_rec is None else max_points_rec['points']

            return f"{maximum}\n\n**Autocomplete**\n{autocomplete_val}"

        max_points_rec = await conn.fetchrow("SELECT * FROM autopunishments WHERE guild_id=$1 AND p_type = 'ban'", ctx.guild.id)

        em.add_field(name = "Maximum", value = await field_1(max_points_rec))

        # SENDING MESSAGE
        view = WarnView(ctx.author, self.bot, field_0, field_1)
        view.msg = await ctx.send(embed=em,view=view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Setup(bot))