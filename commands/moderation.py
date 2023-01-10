import discord
from discord.ext import commands, tasks
from discord.ext.commands.cooldowns import BucketType
from discord.app_commands import describe

from datetime import timedelta
from typing import Optional, Literal
from helper.other import Paginator, offence_dm_embed_maker, offence_embed_maker, time_unparser, TimeParser, Confirm
import asyncpg

EMBED_COLOR = discord.Color.from_str('#e27a7a')

class Moderation(commands.Cog, name = "moderation"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_check(self, ctx: commands.Context) -> bool:
        if ctx.channel.type == discord.ChannelType.private:
            return False

        b_c = await self.bot.pool.fetchval("SELECT blacklisted_channels FROM guild_table WHERE guild_id = $1", ctx.guild.id)

        if b_c is not None and ctx.channel.id in b_c:
            return False
        return True

    @commands.cooldown(rate = 1, per = 5, type = BucketType.member)
    @describe(
        member = "The member to kick",
        reason = "Reason for kicking. Defaults to 'No reason given'"
    )
    @commands.has_guild_permissions(kick_members = True)
    @commands.hybrid_command(description = "Kick a member. Requires kick members permission")
    async def kick(self, ctx: commands.Context, member: discord.Member, *, reason: str = "No reason given"):
        
        if member.guild_permissions.kick_members:
            return await ctx.send("Cannot kick this user.\nThe user can kick members from this server.", ephemeral = True, delete_after = 5)
        
        if member.roles[-1] >= ctx.guild.me.roles[-1]:
            return await ctx.send("You need to place my role higher than the highest role of this member.", ephemeral = True, delete_after = 5)

        additional_message = await self.bot.pool.fetchval("SELECT offence_message FROM guild_table WHERE guild_id = $1", ctx.guild.id)

        dm_em = offence_dm_embed_maker("kicked", 'from', ctx.guild.name, reason = reason, additional_message = additional_message)
        
        kicked_member = member

        try:
            await member.send(embed = dm_em)
            sent = True
        except:
            sent = False
        
        await member.kick(reason = reason)
        em = offence_embed_maker("Kick", "kicked", kicked_member, ctx.author, reason, sent)

        await ctx.send(embed = em)

        # id serial primary key,
        # guild_id BIGINT NOT NULL,
        # user_id BIGINT NOT NULL,
        # punishment varchar (50) NOT NULL,
        # body TEXT,
        # created_by BIGINT NOT NULL,
        # created_on TIMESTAMP WITH TIME ZONE NOT NULL
        
        await self.bot.pool.execute("INSERT INTO offences (guild_id, user_id, punishment, body, created_by, created_on) VALUES ($1,$2,$3,$4,$5,$6)",
        ctx.guild.id, kicked_member.id, 'kick', reason, ctx.author.id, discord.utils.utcnow())

    @commands.cooldown(rate = 1, per = 5, type = BucketType.member)
    @describe(
        member = "The member to timeout",
        until = "Duration of timeout. 'd' for days, 'h' for hours, 'm' for minutes, 's' for seconds",
        reason = "The reason for the timeout"
    )
    @commands.has_guild_permissions(moderate_members = True)
    @commands.hybrid_command(description = "Times out a member", aliases = ['timeout'])
    async def mute(self, ctx: commands.Context, member: discord.Member, until: Optional[TimeParser], *, reason: str = "No reason given"):

        if member.guild_permissions.moderate_members:
            return await ctx.send("Cannot kick this user.\nThe user can kick members from this server.", ephemeral = True, delete_after = 5)
            
        if member.roles[-1] >= ctx.guild.me.roles[-1]:
            return await ctx.send("You need to place my role higher than the highest role of this member.", ephemeral = True, delete_after = 5)
        
        if until is None:
            until = timedelta(weeks = 1)

        if until > timedelta(days=28):
            return await ctx.send("Can only timeout for 28 days maximum.", ephemeral = True, delete_after = 5)
        try:
            await member.timeout(until, reason = reason)
        except:
            return await ctx.send("Failed to time out the user.", delete_after = 5, ephemeral = True)

        additional_message = await self.bot.pool.fetchval("SELECT offence_message FROM guild_table WHERE guild_id = $1", ctx.guild.id)

        dm_em = offence_dm_embed_maker('timed out', 'in', ctx.guild.name, reason, additional_message = additional_message,
        until = until + discord.utils.utcnow())

        try:
            await member.send(embed = dm_em)
            sent = True
        except:
            sent = False

        em = offence_embed_maker('Timeout', 'timed out', member, ctx.author, reason, sent, until + discord.utils.utcnow())

        await ctx.send(embed = em)

        await self.bot.pool.execute("INSERT INTO offences (guild_id, user_id, punishment, body, created_by, created_on) VALUES ($1,$2,$3,$4,$5,$6)",
        ctx.guild.id, member.id, f'timeout {time_unparser(until)}', reason, ctx.author.id, discord.utils.utcnow())

    @commands.cooldown(rate = 1, per = 5, type = BucketType.member)
    @describe(
        member = "The member to remove timeout from",
        reason = "The reason for removing timeout"
    )
    @commands.has_guild_permissions(moderate_members = True)
    @commands.hybrid_command(description = "Removes timeout from a member. This is not registered in the user's action logs", aliases = ['untimeout'])
    async def unmute(self, ctx: commands.Context, member: discord.Member, *, reason: str = "No reason given"):
        if not member.is_timed_out():
            return await ctx.send("Member is not timed out.", ephemeral = True, delete_after = 5)
        
        await member.timeout(None, reason = reason)

        dm_em = offence_dm_embed_maker('removed from timeout', 'in', ctx.guild, reason)

        try:
            await member.send(embed = dm_em)
            sent = True
        except:
            sent = False

        em = offence_embed_maker('Unmute', 'removed from timeout', member, ctx.author, reason, sent)

        await ctx.send(embed = em)

    @commands.cooldown(rate = 1, per = 5, type = BucketType.member)
    @describe(
        member = "The user to ban",
        ban_type = "'save' to not delete the messages, or 'del' to delete recent messages",
        until = "(Optional) Duration of ban. 'y' for years, 'o' for months, 'd' for days, 'h' for hours",
        reason = "The reason for the ban"
    )
    @commands.has_guild_permissions(ban_members = True)
    @commands.hybrid_command(description = "Bans the user, with optional timer and message deletion")
    async def ban(self, ctx: commands.Context, ban_type: Optional[Literal['save','del']],
    member: discord.Member | discord.User, until: Optional[TimeParser], *, reason: str = "No reason given"):
        try:
            await ctx.interaction.response.defer()
        except:
            pass

        if ban_type is None:
            ban_type = 'save'

        if type(member) is discord.Member:
            if member.guild_permissions.ban_members:
                return await ctx.send("Cannot ban this user.\nThe user can ban members from this server.", ephemeral = True, delete_after = 5)
            
            if member.roles[-1] >= ctx.guild.me.roles[-1]:
                return await ctx.send("You need to place my role higher than the highest role of this member.", ephemeral = True, delete_after = 5)

        additional_message = await self.bot.pool.fetchval("SELECT offence_message FROM guild_table WHERE guild_id = $1", ctx.guild.id)

        if until is not None:
            dm_em = offence_dm_embed_maker("banned", 'from', ctx.guild.name, reason = reason, additional_message = additional_message,
            until = discord.utils.utcnow() + until)
        
        else:
            dm_em = offence_dm_embed_maker("banned", 'from', ctx.guild.name, reason = reason, additional_message = additional_message)
        
        banned_member = member

        try:
            await member.send(embed = dm_em)
            sent = True
        except:
            sent = False

        delete_days = 1 if ban_type == 'del' else 0

        await ctx.guild.ban(member, reason = reason, delete_message_days = delete_days)

        await self.bot.pool.execute("DELETE FROM banned_users WHERE user_id=$1 and guild_id=$2", banned_member.id, ctx.guild.id)
        
        if until is not None:
            ban_em = offence_embed_maker('Ban', 'banned', banned_member, ctx.author, reason, sent, until = discord.utils.utcnow() + until)
            await self.bot.pool.execute("INSERT INTO banned_users(user_id,guild_id,wait_until) VALUES($1,$2,$3)",
            banned_member.id, ctx.guild.id, discord.utils.utcnow() + until)
            
        else:
            ban_em = offence_embed_maker('Ban', 'banned', banned_member, ctx.author, reason, sent)

        if ctx.interaction is None:
            await ctx.send(embed = ban_em)
        else:
            await ctx.interaction.followup.send(embed = ban_em)

        punishment = f"ban {time_unparser(until)}" if until is not None else 'ban'

        await self.bot.pool.execute("INSERT INTO offences(guild_id, user_id, punishment, body, created_by, created_on) VALUES($1,$2,$3,$4,$5,$6)",
        ctx.guild.id, banned_member.id, punishment, reason, ctx.author.id, discord.utils.utcnow())

    @commands.cooldown(rate = 1, per = 5, type = BucketType.member)
    @describe(
        member = "The user to unban",
        reason = "The reason for unbanning."
    )
    @commands.has_guild_permissions(ban_members = True)
    @commands.hybrid_command(description = "Unbans a member. This is not registered in the user's action logs")
    async def unban(self, ctx: commands.Context, member: discord.User, reason: str = "No reason given."):
        banned = False

        if member in [x.user async for x in ctx.guild.bans()]:
            await ctx.guild.unban(user = member, reason = reason)
            banned = True

            await self.bot.pool.execute("DELETE FROM banned_users where guild_id=$1 AND user_id=$2", ctx.guild.id, member.id)

        if banned:
            em = offence_embed_maker('Unban', 'unbanned', member, ctx.author, reason, False)
            return await ctx.send(embed = em)

        await ctx.send("User is not banned.", ephemeral=True, delete_after=3)

    @commands.cooldown(rate = 1, per = 5, type = BucketType.member)
    @describe(
        member = 'The member you want to warn',
        points = 'The number of points for the warn.',
        reason = 'Autocomplete enabled here. Automatically autocompletes points too.'
    )
    @commands.has_guild_permissions(moderate_members = True)
    @commands.hybrid_command(description = "Warn a user, with a specific number of points.")
    async def warn(self, ctx: commands.Context, member: discord.Member | discord.User, points: Optional[int], *, reason: str = "No reason given."):
        if ctx.interaction:
            await ctx.interaction.response.defer()
        conn = self.bot.pool

        autocompletes = await conn.fetch("SELECT * FROM autocompletes WHERE guild_id=$1",ctx.guild.id)

        for x in autocompletes:
            if reason in x['reason']:
                points = x['points']
                break

        if points is None:
            points = 1

        thresholds = await conn.fetch("SELECT * FROM autopunishments WHERE guild_id=$1 ORDER BY points ASC", ctx.guild.id)

        if points > 999 or points == 0:
            return await ctx.send("Invalid number of points", ephemeral = True, delete_after = 5)
        if points < 0:
            return await ctx.send("To reduce a user's points, use `pardon`", ephemeral = True, delete_after = 5)
        
        await conn.execute("INSERT INTO warns(guild_id, user_id, body, points, created_by, created_on) VALUES($1,$2,$3,$4,$5,$6)",
        ctx.guild.id, member.id, reason, points, ctx.author.id, discord.utils.utcnow())


        # adding points to user, along with retrieving total
        total_points = 0
        violated_offence = None

        for x in await conn.fetch("SELECT points FROM warns WHERE guild_id=$1 AND user_id=$2", ctx.guild.id, member.id):
            total_points += x['points']
            total_points = 0 if total_points < 0 else total_points

        if len(thresholds) > 0:
            violated_r = [record for record in thresholds if record['points'] <= total_points]

            if len(violated_r) > 0:
                violated_t = violated_r[-1]
            
                violated_offences = await conn.fetch(f"""SELECT * FROM offences
                WHERE guild_id=$1 AND user_id=$2 AND body LIKE '%{str(violated_t['points'])} points' AND pardoned = false""", 
                ctx.guild.id, member.id)

                if violated_offences == []:
                    violated_offence = violated_t
        
        # DM
        dm_em = discord.Embed(color = EMBED_COLOR, title = f"Moderator Action: you have been warned",
        description = f"You have been warned (`{points}` point{'s' if points > 1 else ''}) in **{ctx.guild.name}**.\n**Reason:** {reason}")

        additional_message = await self.bot.pool.fetchval("SELECT offence_message FROM guild_table WHERE guild_id = $1", ctx.guild.id)

        if additional_message is not None:
            dm_em.add_field(name = "Additional Message", value = additional_message, inline = False)
            
        if len(thresholds) > 0 and 'ban' in thresholds[-1]['p_type']:
            dm_em.add_field(name = "Maximum points", value = f"You get banned at {thresholds[-1]['points']} points.")

        try:
            await member.send(embed = dm_em)
            sent = True
        except:
            sent = False

        # making embed        
        warn_em = discord.Embed(color = EMBED_COLOR, title = f"Moderator Action: ` Warn `",
        description = f"User **`{member} (ID: {member.id})`** has been warned (`{points}` point{'s' if points > 1 else ''}).\n**Reason:** {reason}")
        
        warn_em.set_author(name = str(ctx.author), icon_url = ctx.author.display_avatar.url)

        warn_em.add_field(name = "User points", value = f"`{total_points} points`")

        no_max_threshold = "No maximum threshold is set.\nPlease use `/set warning` to setup the warning system."
        if len(thresholds) > 0:
            maximum_points = f"`{thresholds[-1]['points']} points`" if 'ban' in thresholds[-1]['p_type'] else f"`{no_max_threshold}`"
        else:
            maximum_points = no_max_threshold

        warn_em.add_field(name = "Maximum points", value = maximum_points)
    
        warn_em.set_footer(text = f"DM to the user {'has been sent' if sent else 'could not be sent'}")
    
        await ctx.send(embed = warn_em)

        # punishment
        if violated_offence is None:
            return
        
        view = Confirm(ctx.author)
        info_dict = {"kick": "Kick", "mute": "Timeout ", "ban": "Permanent ban", "bant": "Ban "}
        punishment = info_dict[violated_offence['p_type']]

        if violated_offence['p_type'] in ['mute','bant']:
            punishment += time_unparser(violated_offence['timer'])

        if member not in ctx.guild.members and violated_offence['p_type'] in ['mute', 'kick']:
            return

        msg = await ctx.send(f"User has exceeded limit of {violated_offence['points']} points for the punishment: {punishment}. Should I do it? (recommended)",
        view = view, ephemeral = True)
        
        await view.wait()
        await msg.delete()

        if view.value is not None:
            pun_reason = f"Exceeded warn limit - {violated_offence['points']} points"
            
            if violated_offence['p_type'] == 'kick':
                cmd = self.bot.get_command("kick")
                await ctx.invoke(cmd, member = member, reason = pun_reason)
            
            elif violated_offence['p_type'] == 'mute':
                cmd = self.bot.get_command("mute")
                await ctx.invoke(cmd, member = member, until = violated_offence['timer'], reason = pun_reason)
                
            elif violated_offence['p_type'] in ['ban','bant']:    
                cmd = self.bot.get_command("ban")
                
                if violated_offence['p_type'] == 'ban':
                    await ctx.invoke(cmd, ban_type = 'save', member = member, until = None, reason = pun_reason)
                else:
                    await ctx.invoke(cmd, ban_type = 'save', member = member, until = violated_offence['timer'], reason = pun_reason)

    @warn.autocomplete('reason')
    async def warn_autocomplete(self, itx: discord.Interaction, current: str):
        autocompletes = await self.bot.pool.fetch("SELECT * FROM autocompletes WHERE guild_id=$1",itx.guild.id)
        return [discord.app_commands.Choice(name=f"{x['points']} points: {x['reason']}",value=x['reason']) for x in autocompletes]

    @commands.cooldown(rate = 1, per = 5, type = BucketType.member)
    @describe(
        member = "The user to reduce points from",
        points = "The number of points for the pardon.",
        reason = "The reason for the pardon."
    )
    @commands.has_guild_permissions(moderate_members = True)
    @commands.hybrid_command(description = "Reduces a user's points.")
    async def pardon(self, ctx: commands.Context, member: discord.Member | discord.User, points: int, *, reason: str = "No reason given."):
        conn = self.bot.pool
        points = -abs(points)

        if points < -999 or points == 0:
            return await ctx.send("Invalid number of points", ephemeral = True, delete_after = 5)

        total_points = 0
        for x in await conn.fetch("SELECT points FROM warns WHERE guild_id=$1 AND user_id=$2", ctx.guild.id, member.id):
            total_points += x['points']
            total_points = 0 if total_points < 0 else total_points

        if total_points == 0:
            return await ctx.send("User has 0 warn points already.", ephemeral = True, delete_after = 5)

        await conn.execute("INSERT INTO warns(guild_id, user_id, body, points, created_by, created_on) VALUES($1,$2,$3,$4,$5,$6)",
        ctx.guild.id, member.id, reason, points, ctx.author.id, discord.utils.utcnow())

        total_points += points

        thresholds = await conn.fetch("SELECT * FROM autopunishments WHERE guild_id=$1 ORDER BY points ASC", ctx.guild.id)

        if len(thresholds) > 0:
            violated_r = [record for record in thresholds if record['points'] >= total_points]

            for violated_t in violated_r:
                await conn.execute(f"""UPDATE offences SET pardoned = true
                WHERE guild_id=$1 AND user_id=$2 AND body LIKE '%{violated_t['points']} points' AND pardoned = false""", 
                ctx.guild.id, member.id)

        # making embed        
        warn_em = discord.Embed(color = EMBED_COLOR, title = f"Moderator Action: ` Pardon `",
        description = f"User **`{member} (ID: {member.id})`** has been pardoned (`{points}` points).\n**Reason:** {reason}")
        
        warn_em.set_author(name = str(ctx.author), icon_url = ctx.author.display_avatar.url)

        warn_em.add_field(name = "User points", value = f"`{total_points} points`")

        no_max_threshold = "No maximum threshold is set.\nPlease use `/set warning` to setup the warning system."
        if len(thresholds) > 0:
            maximum_points = f"`{thresholds[-1]['points']} points`" if 'ban' in thresholds[-1]['p_type'] else f"`{no_max_threshold}`"
        else:
            maximum_points = no_max_threshold

        warn_em.add_field(name = "Maximum points", value = maximum_points)
    
        await ctx.send(embed = warn_em)

    @commands.cooldown(rate = 1, per = 5, type = BucketType.member)
    @describe(id = "The warn ID")
    @commands.has_guild_permissions(moderate_members = True)
    @commands.hybrid_command(description = "Deletes a user's warn")
    async def delwarn(self, ctx: commands.Context, id: int, *, reason: str = "No reason given"):
        id = abs(id)
        conn = self.bot.pool

        record = await conn.fetchrow("SELECT * FROM warns WHERE guild_id = $1 AND id = $2", ctx.guild.id, id)

        if record is None:
            return await ctx.send("Warn with this ID does not exist", ephemeral = True, delete_after = 5)

        await self.bot.pool.execute("DELETE FROM warns WHERE guild_id = $1 AND id = $2", ctx.guild.id, id)

        total_points = 0
        for x in await conn.fetch("SELECT points FROM warns WHERE guild_id=$1 AND user_id=$2", ctx.guild.id, record['user_id']):
            total_points += x['points']
            total_points = 0 if total_points < 0 else total_points

        thresholds = await conn.fetch("SELECT * FROM autopunishments WHERE guild_id=$1 ORDER BY points ASC", ctx.guild.id)

        if len(thresholds) > 0:
            violated_r = [record for record in thresholds if record['points'] >= total_points]

            for violated_t in violated_r:
                await conn.execute(f"""UPDATE offences SET pardoned = true
                WHERE guild_id=$1 AND user_id=$2 AND body LIKE '%{violated_t['points']} points' AND pardoned = false""", 
                ctx.guild.id, record['user_id'])

        warn_em = discord.Embed(color = EMBED_COLOR, title = f"Moderator Action: ` Warn delete `",
        description = f"Warn with ID `{record['id']}` has been deleted\n**Reason:** {reason}")
        
        warn_em.add_field(name = "User", value = f"{await self.bot.fetch_user(record['user_id'])} (ID: {record['user_id']})")
        warn_em.add_field(name = "Points", value = f"`{record['points']}`")
        warn_em.add_field(name = "Reason", value = record['body'], inline = False)
        warn_em.add_field(name = "Warned by", value = f"{await self.bot.fetch_user(record['created_by'])} (ID: {record['created_by']})")
        warn_em.add_field(name = "Warned on", value = discord.utils.format_dt(record['created_on'], 'd'))
        
        
        warn_em.set_author(name = str(ctx.author), icon_url = ctx.author.display_avatar.url)

        warn_em.set_footer(text = f"This user has {total_points} points")
    
        await ctx.send(embed = warn_em)

    @commands.cooldown(rate = 1, per = 10, type = BucketType.member)
    @describe(member = "The user to check the warnings of")
    @commands.has_guild_permissions(moderate_members = True)
    @commands.hybrid_command(description = "View user's warnings", aliases = ["warning"])
    async def warnings(self, ctx: commands.Context, *, member: discord.Member | discord.User):
        if ctx.interaction:
            await ctx.interaction.response.defer()
        
        warnings = await self.bot.pool.fetch("SELECT * FROM warns WHERE guild_id = $1 AND user_id = $2 ORDER BY id ASC", ctx.guild.id, member.id)

        if len(warnings) == 0:
            return await ctx.send("This user has no warnings.")
        total_points = 0
        for x in warnings:
            total_points += x['points']
            total_points = 0 if total_points < 0 else total_points


        em = discord.Embed(color = EMBED_COLOR, title = f"Warnings for `{str(member).replace('`','')}`", description = f"User points: `{total_points}`")
        em_list = [em]
        field_id = 0

        for rec in warnings:
            if field_id == 24:
                em = discord.Embed(color = EMBED_COLOR, title = f"Warnings for `{str(member).replace('`','')}`",
                description = f"User points: `{total_points}`")
                em_list.append(em)
                field_id = 0

            id = rec['id']
            points = rec['points']
            mod = await self.bot.fetch_user(rec['created_by'])
            created_on = discord.utils.format_dt(rec['created_on'], 'F')

            em.add_field(name = f"ID: `{id}`",
            value = f"**Points:** `{points}`\n**Moderator:** {mod.mention}\n**Warned on:** {created_on}\n**Reason:** {x['body'][:800]}")
            field_id += 1

        if len(em_list) == 1:
            await ctx.send(embed = em)
        else:
            view = Paginator(ctx.author, em_list)
            view.msg = await ctx.send(embed = em_list[0], view = view)
    
    @commands.cooldown(rate = 1, per = 10, type = BucketType.member)
    @describe(member = "The user to check the action logs of")
    @commands.has_guild_permissions(moderate_members = True)
    @commands.hybrid_command(description = "View user's action logs", aliases = ['actionlogs', 'logs', 'modlog', 'modlogs'])
    async def offences(self, ctx: commands.Context, *, member: discord.Member | discord.User):
        if ctx.interaction:
            await ctx.interaction.response.defer()
        
        offences = await self.bot.pool.fetch("SELECT * FROM offences WHERE guild_id = $1 AND user_id = $2 ORDER BY id ASC", ctx.guild.id, member.id)

        if len(offences) == 0:
            return await ctx.send("This user has no action logs.")
        
        actions = len(offences)

        em = discord.Embed(color = EMBED_COLOR, title = f"Action logs for `{str(member).replace('`','')}`",
        description = f"Actions on this user: `{actions}`")
        
        em_list = [em]
        field_id = 0
        chars = 0

        for rec in offences:
            if field_id == 24 or chars > 5000:
                em = discord.Embed(color = EMBED_COLOR, title = f"Action logs for `{str(member).replace('`','')}`",
                description = f"Actions on this user: `{actions}`")
                em_list.append(em)
                field_id = 0
                chars = 0
            else:
                field_id += 1
            mod = await self.bot.fetch_user(rec['created_by'])
            created_on = discord.utils.format_dt(rec['created_on'], 'F')

            name = f"Action: `{rec['punishment']}`"
            value = f"**Moderator:** {mod.mention}\n**Action on:** {created_on}\n**Reason:** {rec['body'][:900]}"

            em.add_field(name = name, value = value)
            chars += len(name) + len(value)

        if len(em_list) == 1:
            await ctx.send(embed = em)
        else:
            view = Paginator(ctx.author, em_list)
            view.msg = await ctx.send(embed = em_list[0], view = view)

class ModTask(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.data = []
        self.mod_task.add_exception_type(asyncpg.PostgresConnectionError)
        self.mod_task.start()

    def cog_unload(self):
        self.mod_task.cancel()

    @tasks.loop(minutes = 2)
    async def mod_task(self):
        try:
            banned_users = await self.bot.pool.fetch("SELECT * from banned_users")
        except asyncpg.UndefinedTableError:
            banned_users = []
    
        for record in banned_users:
            if record['wait_until'] > discord.utils.utcnow():
                continue
            
            try:
                guild = await self.bot.fetch_guild(record['guild_id'])
                user = await self.bot.fetch_user(record['user_id'])
            except:
                continue

            try:
                await guild.unban(user, reason = "Timer expired.")
            except:
                pass
            
            await self.bot.pool.execute("DELETE FROM banned_users WHERE id = $1", record['id'])


    @mod_task.before_loop
    async def before_mod_task(self):
        print('waiting...')
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Moderation(bot))
    await bot.add_cog(ModTask(bot))