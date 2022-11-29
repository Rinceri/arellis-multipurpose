import discord
from discord.ext import commands
from discord.ext.commands import BucketType
from discord import app_commands
from typing import Optional, Literal
from datetime import timedelta
from helper import poll_views
from helper.other import ColorParser
import aiohttp


EMBED_COLOR = discord.Color.from_str("#ddb857")

class MUtility(commands.Cog, name = "moderator utility", description = "Utility commands for moderators"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_check(self, ctx: commands.Context) -> bool:
        b_c = await self.bot.pool.fetchval("SELECT blacklisted_channels FROM guild_table WHERE guild_id = $1", ctx.guild.id)

        if b_c is not None and ctx.channel.id in b_c:
            return False
        return True

    @commands.hybrid_group(invoke_without_command = True)
    @commands.cooldown(rate = 1, per = 10, type = BucketType.member)
    async def emote(self, ctx: commands.Context):
        pass
    
    @emote.command(name = "create", description = "Adds an emote", aliases = ['add'])
    @commands.has_guild_permissions(manage_emojis = True)
    @commands.cooldown(rate = 1, per = 10, type = BucketType.member)
    @app_commands.describe(
        name = "Name for the emote",
        file = "Image file. Otherwise enter link/emoji.",
        emoji = "Either image URL or emoji."
    )
    async def e_create(self, ctx: commands.Context, name: str, file: Optional[discord.Attachment], *, emoji: Optional[str]):
        # TODO: check for name with regex
        name = ''.join(i for i in name if i.isalnum())
        
        if emoji is not None:
            try:
                p_emoji = await commands.PartialEmojiConverter().convert(ctx = ctx, argument = emoji)
                emoji = await p_emoji.read()
            except:
                try:
                    async with aiohttp.ClientSession() as cs:
                        async with cs.get(emoji) as get_con:
                            emoji = await get_con.read()
                            
                            if emoji is None:
                                raise
                except:
                    return await ctx.send("Invalid emoji/URL provided", ephemeral = True, delete_after = 5)

        elif file is not None:
            emoji = await file.read(use_cached = True)

        else:
            return await ctx.send("Attachment and emoji parameter both cannot be empty", ephemeral = True, delete_after = 5)
        
        try:
            ret = await ctx.guild.create_custom_emoji(name = name, image = emoji, reason = f"Created by {str(ctx.author)} (ID: {ctx.author.id})")
        
        except discord.errors.HTTPException:
            return await ctx.send("An error occurred while trying to upload the emoji. Perhaps the name or file/emoji parameter is not valid.",
            ephemeral = True, delete_after = 5)
        
        await ctx.send(f"Emoji created: {ret}")

    @emote.command(name = "delete", description = "Removes an emote", aliases = ['remove'])
    @commands.has_guild_permissions(manage_emojis = True)
    @commands.cooldown(rate = 1, per = 10, type = BucketType.member)
    async def e_delete(self, ctx: commands.Context, *, emoji: discord.Emoji):
        
        if emoji.guild != ctx.guild:
            return await ctx.send("Emote does not belong to this guild.", ephemeral = True, delete_after = 5)

        reason = f"Deleted by {str(ctx.author)} (ID: {ctx.author.id})"
        
        try:
            await emoji.delete(reason = reason)

        except discord.errors.HTTPException:
            return await ctx.send("An error occurred.", ephemeral = True, delete_after = 5)

        await ctx.send("Emoji has been deleted.")

    @emote.command(name = "edit", description = "Edit the name of an emote")
    @commands.has_guild_permissions(manage_emojis = True)
    @commands.cooldown(rate = 1, per = 10, type = BucketType.member)
    async def e_edit(self, ctx: commands.Context, emoji: discord.Emoji, *, name: str):
        
        if emoji.guild != ctx.guild:
            return await ctx.send("Emote does not belong to this guild.", ephemeral = True, delete_after = 5)

        try:
            ret = await emoji.edit(name = name, reason = f"Edited by {str(ctx.author)} (ID: {ctx.author.id})")
        
        except discord.errors.HTTPException:
            return await ctx.send("An error occurred.", ephemeral = True, delete_after = 5)
        
        await ctx.send(f"Emoji has been edited with the new name: {ret}")

    @emote.command(name = "info", description = "Get info for a particular emote")
    @commands.has_guild_permissions(manage_emojis = True)
    @commands.cooldown(rate = 1, per = 10, type = BucketType.member)
    async def e_info(self, ctx: commands.Context, *, emoji: discord.Emoji):

        try:
            emoji = await ctx.guild.fetch_emoji(emoji.id)
        except:
            return await ctx.send("This emoji does not exist for this guild.")

        em = discord.Embed(color = discord.Color.from_str('#ddb857'), title = f"{emoji} Emote info")
        
        info = {'name': f"**` {emoji.name} `**", 'ID': f"**` {emoji.id} `**", 'URL': f"[**` Click here `**]({emoji.url})",
        'Created on': discord.utils.format_dt(emoji.created_at, 'd'), 'Created by': emoji.user.mention}

        for name, value in info.items():
            em.add_field(name = name, value = value)
        
        em.set_thumbnail(url = emoji.url)
        em.set_footer(text = str(ctx.author), icon_url = ctx.author.display_avatar.url)

        await ctx.send(embed = em)


    @commands.hybrid_group(invoke_without_command = True)
    @commands.has_guild_permissions(manage_roles = True)
    @commands.cooldown(rate = 1, per = 10, type = BucketType.member)
    async def role(self, ctx: commands.Context):
        pass
    
    @commands.has_guild_permissions(manage_roles = True)
    @commands.cooldown(rate = 1, per = 10, type = BucketType.member)
    @role.command(name = "create", description = "Creates a role with no permissions at a given position")
    @app_commands.describe(
        name = "Name of the role. Defaults to 'new role'",
        under = "Below a specific role. Defaults to lowest",
        color = "Color of the role, in hex (e.g. #123456, 0x123456 or 123456). Leave it empty for default color",
        hoist = "Whether the role should be shown separately in the member list. Defaults to False",
        mentionable = "Whether the role should be mentionable by others. Defaults to False"
    )
    async def r_create(self, ctx: commands.Context, name: Optional[str], under: Optional[discord.Role], color: Optional[ColorParser], 
    hoist: bool = False, mentionable: bool = False):
        
        try:
            r = await ctx.guild.create_role(name = name, color = color, hoist = hoist, mentionable = mentionable,
            reason = f"Created by {ctx.author} (ID: {ctx.author.id})")
        except discord.errors.HTTPException:
            return await ctx.send("Creating the role failed.", ephemeral = True, delete_after = 5)


        em = discord.Embed(color = color, title = "Creating role", description = f"<:tick:1041403495137431654> Role {r.mention} has been created")
        
        msg = await ctx.send(embed = em)

        # key: under is a provided role, role is the for loop variable for roles, r is the created role
        if under is not None:
            for num, role in enumerate(ctx.guild.roles):
                if role == under:
                    try:
                        pos = {r: num-1}
                        await ctx.guild.edit_role_positions(positions = pos)
                        em.description += f"\n<:tick:1041403495137431654> Role has been positioned below {role}"
                    except:
                        em.description += "\n<:redcross:1041406665192390786> Could not adjust positions. Make sure the role chosen is below my role."
                    
                    break

            await msg.edit(embed = em)

    @commands.has_guild_permissions(manage_roles = True)
    @commands.cooldown(rate = 1, per = 10, type = BucketType.member)
    @role.command(name = "delete", description = "Removes a role")
    async def r_delete(self, ctx: commands.Context, *,role: discord.Role):
        name = role.name
        
        if role not in ctx.guild.roles:
            return await ctx.send("Role does not exist")

        try:
            await role.delete(reason = f"Deleted by {str(ctx.author)} (ID: {ctx.author.id})")
        
        except discord.errors.Forbidden:
            return await ctx.send("I do not have the permissions to delete this role.", ephemeral = True, delete_after = 5)
        
        else:
            await ctx.send(f"Role `{name.replace('`','')}` has been deleted.")

    @commands.has_guild_permissions(manage_roles = True)
    @commands.cooldown(rate = 1, per = 10, type = BucketType.member)
    @role.command(name = "edit", description = "Edits the role name, position and/or color.")
    @app_commands.describe(
        role = "Role to be edited",
        name = "Name of the role, if that needs to be changed",
        under = "Below a specific role, if that needs to be changed",
        color = "Color of the role, in hex (e.g. #123456, 0x123456 or 123456), if that needs to be changed"
    )
    async def r_edit(self, ctx: commands.Context, role: discord.Role, name: Optional[str], under: Optional[discord.Role], *,color: Optional[ColorParser]):

        if role not in ctx.guild.roles and under in ctx.guild.roles:
            return await ctx.send("Role does not exist")

        if name is not None or color is not None:
            try:
                if name is not None:
                    await role.edit(name = name)
                if color is not None:
                    await role.edit(color = color)
            except:
                return await ctx.send("Role could not be edited", ephemeral = True, delete_after = 5)

        if under is not None:
            for num, r in enumerate(ctx.guild.roles):
                if r == under:
                    try:
                        pos = {role: num-1}
                        await ctx.guild.edit_role_positions(positions = pos)
                        
                    except:
                        return await ctx.send("Role positioning failed", ephemeral = True, delete_after = 5)

                    break

        elif name is None and color is None:
            await ctx.send("Atleast one parameter except `role` must be filled.", ephemeral = True, delete_after = 5)
            return

        await ctx.send("Role has been edited")
    
    @commands.has_guild_permissions(manage_roles = True)
    @commands.cooldown(rate = 1, per = 10, type = BucketType.member)
    @role.command(name = "add", description = "Adds the role(s) (separate all roles with a space) to a user")
    async def r_add(self, ctx: commands.Context, member: discord.Member, *, role: commands.Greedy[discord.Role]):
        try:
            await member.add_roles(*role, reason = f"Added by {str(ctx.author)} (ID: {ctx.author.id})")
        except discord.errors.Forbidden:
            await ctx.send("I do not have the permissions to add this role to the user. Make sure my role is higher than this role.", 
            ephemeral = True, delete_after = 5)
        else:
            await ctx.send(f"Added the role(s) to `{str(member).replace('`','')}`")

    @commands.has_guild_permissions(manage_roles = True)
    @commands.cooldown(rate = 1, per = 10, type = BucketType.member)
    @role.command(name = "remove", description = "Removes the role(s) (separate all roles with a space) from a user")
    async def r_remove(self, ctx: commands.Context, member: discord.Member, *, role: commands.Greedy[discord.Role]):
        try:
            await member.remove_roles(*role, reason = f"Removed by {str(ctx.author)} (ID: {ctx.author.id})")
        except discord.errors.Forbidden:
            await ctx.send("I do not have the permissions to remove this role from the user. Make sure my role is higher than this role.", 
            ephemeral = True, delete_after = 5)
        else:
            await ctx.send(f"Removed the role(s) from `{str(member).replace('`','')}`")

    @commands.has_guild_permissions(manage_roles = True)
    @commands.cooldown(rate = 1, per = 10, type = BucketType.member)
    @role.command(name = "info", description = "Get info for a particular role")
    async def r_info(self, ctx: commands.Context, *, role: discord.Role):
        # EMBED CREATION
        em = discord.Embed(color = role.color, title = "Role info", description = role.mention)
        position = None        
        
        for num, r in enumerate(reversed(ctx.guild.roles)):
            if r == role:
                position = num

        if position is None:
            return await ctx.send("Role does not exist for this server", delete_after = 5, ephemeral = True)

        booster_role = ""
        if role.is_premium_subscriber():
            booster_role += " | Booster role"

        #AUTHOR SETTING
        em.set_author(name = f"#{position + 1} from top {booster_role}")

        #THUMBNAIL SETTING
        if role.display_icon is not None:
            em.set_thumbnail(url = role.display_icon.url)
        
        # FIELD 0
        em.add_field(name = "_ _", 
        value = f"**Name**: ` {role.name.replace('`','')} `\n**Color**: ` {str(role.color)} `\n**Number of members**: ` {len(role.members)} `")

        icon = f"[` Click here `]({role.display_icon.url})" if role.display_icon is not None else "` None `"

        # FIELD 1
        em.add_field(name = "_ _",
        value = f"**ID**: ` {role.id} `\n**Display icon**: {icon}\n**Created on**: {discord.utils.format_dt(role.created_at, 'd')}")

        def unparsed_perm(perm: discord.Permissions) -> str:
            unparser = {'add_reactions': 'Add reactions', 'administrator': 'Administrator',
            'attach_files': 'Attach files', 'ban_members': 'Ban members', 'change_nickname': 'Change nickname',
            'connect': 'Connect', 'create_instant_invite': 'Create instant invite', 'create_private_threads': 'Create private threads', 
            'create_public_threads': 'Create public threads', 'deafen_members': 'Deafen members', 'embed_links': 'Embed links', 
            'external_emojis': 'External emojis', 'external_stickers': 'External stickers', 'kick_members': 'Kick members',
            'manage_channels': 'Manage channels', 'manage_emojis': 'Manage emojis', 'manage_emojis_and_stickers': 'Manage emojis and stickers', 
            'manage_events': 'Manage events', 'manage_guild': 'Manage server', 'manage_messages': 'Manage messages', 
            'manage_nicknames': 'Manage nicknames', 'manage_permissions': 'Manage permissions', 'manage_roles': 'Manage roles', 
            'manage_threads': 'Manage threads', 'manage_webhooks': 'Manage webhooks', 'mention_everyone': 'Mention everyone', 
            'moderate_members': 'Timeout members', 'move_members': 'Move members', 'mute_members': 'Mute members', 
            'priority_speaker': 'Priority speaker', 'read_message_history': 'Read message history', 'read_messages': 'Read messages', 
            'request_to_speak': 'Request to speak', 'send_messages': 'Send messages', 
            'send_messages_in_threads': 'Send messages in threads', 'send_tts_messages': 'Send tts messages', 'speak': 'Speak', 
            'stream': 'Stream', 'use_application_commands': 'Use application commands', 'use_embedded_activities': 'Use embedded activities', 
            'use_external_emojis': 'Use external emojis', 'use_external_stickers': 'Use external stickers', 
            'use_voice_activation': 'Use voice activation', 'view_audit_log': 'View audit log', 'view_channel': 'View channel', 
            'view_guild_insights': 'View server insights'}

            return unparser[perm[0]]

        perms = '\n'.join([unparsed_perm(perm) for perm in role.permissions if perm[1]])[:1024]

        # FIELD 2
        em.add_field(name = "**Enabled Permissions**", inline = False,
        value = f"```yaml\n{perms}```" if perms != "" else "` None `")

        # FOOTER SETTING
        hoist = "not" if not role.hoist else ""
        mentionable = "not" if not role.mentionable else ""
        em.set_footer(text = f"This role is {hoist} hoisted, {mentionable} mentionable")

        await ctx.send(embed = em)


    @commands.hybrid_group(invoke_without_command = True)
    @commands.cooldown(rate = 1, per = 10, type = BucketType.member)
    async def channel(self, ctx: commands.Context):
        pass
    
    @commands.has_guild_permissions(manage_channels = True)
    @commands.cooldown(rate = 1, per = 10, type = BucketType.member)
    @channel.command(name = "create", aliases = ['add'], description = "Creates a channel, and can be hidden")
    @app_commands.describe(channel_type = "Type of channel, can be either 'text', 'voice', 'stage', or 'forum'",
    hidden = "If the channel should be hidden from everyone",
    name = "Name of the channel")
    async def c_create(self, ctx: commands.Context, channel_type: Optional[Literal['text', 'voice', 'stage', 'forum']], hidden: Optional[bool], *,
    name: str = "new-channel"):
        
        if channel_type is None:
            channel_type = 'text'

        if channel_type == 'stage' or channel_type == 'forum' and 'COMMUNITY' not in ctx.guild.features:
            return await ctx.send("Making this channel type requires Community mode to be enabled", ephemeral = True, delete_after = 10)

        if hidden is None:
            hidden = False

        VOICE_OVERWRITES = {ctx.guild.default_role: discord.PermissionOverwrite(connect=False, view_channel = False), 
        ctx.guild.me: discord.PermissionOverwrite(connect=True)}

        TEXT_OVERWRITES = {ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False), 
        ctx.guild.me: discord.PermissionOverwrite(read_messages=True)}

        if channel_type == 'text':
            name = ''.join([letter for letter in name.replace(' ','-') if letter == '-' or letter.isalnum()])
            if not hidden:
                channel = await ctx.guild.create_text_channel(name = name, category = ctx.channel.category,
                reason = f"Created by {str(ctx.author)} (ID: {ctx.author.id})")
            else:
                channel = await ctx.guild.create_text_channel(name = name, category = ctx.channel.category,
                reason = f"Created by {str(ctx.author)} (ID: {ctx.author.id})", overwrites = TEXT_OVERWRITES)

        elif channel_type == 'voice':
            if not hidden:
                channel = await ctx.guild.create_voice_channel(name = name, category = ctx.channel.category,
                reason = f"Created by {str(ctx.author)} (ID: {ctx.author.id})")
            
            else:
                channel = await ctx.guild.create_voice_channel(name = name, category = ctx.channel.category,
                reason = f"Created by {str(ctx.author)} (ID: {ctx.author.id})", overwrites = VOICE_OVERWRITES)
                                
        elif channel_type == 'stage':
            if not hidden:
                channel = await ctx.guild.create_stage_channel(name = name, category = ctx.channel.category,
                reason = f"Created by {str(ctx.author)} (ID: {ctx.author.id})", topic = "None")
            
            else:
                channel = await ctx.guild.create_stage_channel(name = name, category = ctx.channel.category,
                reason = f"Created by {str(ctx.author)} (ID: {ctx.author.id})", overwrites = VOICE_OVERWRITES, topic = "None")
                
        elif channel_type == 'forum':
            name = ''.join([letter for letter in name.replace(' ','-') if letter == '-' or letter.isalnum()])
            if not hidden:
                channel = await ctx.guild.create_forum(name = name, category = ctx.channel.category,
                reason = f"Created by {str(ctx.author)} (ID: {ctx.author.id})")
            else:
                channel = await ctx.guild.create_forum(name = name, category = ctx.channel.category,
                reason = f"Created by {str(ctx.author)} (ID: {ctx.author.id})", overwrites = TEXT_OVERWRITES)

        else:
            return await ctx.send("Invalid type given.", ephemeral = True, delete_after = 5)

        await ctx.send(f"{channel.mention} has been created.")

    @commands.has_guild_permissions(manage_channels = True)
    @commands.cooldown(rate = 1, per = 10, type = BucketType.member)
    @channel.command(name = "delete", aliases = ['remove'], description = "Deletes the channel")
    @app_commands.describe(channel = "Deletes the channel")
    async def c_delete(self, ctx: commands.Context, *,
    channel: Optional[discord.TextChannel | discord.VoiceChannel | discord.ForumChannel | discord.StageChannel]):
        if channel is None:
            channel = ctx.channel
        
        name = channel.name

        if channel.guild != ctx.guild:
            return await ctx.send("Channel does not exist", ephemeral = True, delete_after = 5)

        await channel.delete(reason = f"Deleted by {str(ctx.author)} (ID: {ctx.author.id})")

        if channel != ctx.channel:
            await ctx.send(f"Channel `{name.replace('`','')}` has been deleted.")

    @commands.has_guild_permissions(manage_channels = True)
    @commands.cooldown(rate = 1, per = 10, type = BucketType.member)
    @channel.command(name = "edit", description = "Allows editing the channel name or slowmode")
    @app_commands.describe(channel = "The channel to be edited", name = "(Optional) New channel name",
    slowmode = "(Optional) Slowmode, in seconds. Ranges from 0 to 21600")
    async def c_edit(self, ctx: commands.Context, channel: discord.TextChannel | discord.VoiceChannel | discord.ForumChannel | discord.StageChannel,
    slowmode: Optional[int], *, name: Optional[str]):
        
        ret = None

        if channel not in ctx.guild.channels:
            return await ctx.send("Channel does not exist", ephemeral = True, delete_after = 5)

        if name is not None:
            if type(channel) in [discord.TextChannel, discord.ForumChannel]:
                name = ''.join([letter for letter in name.replace(' ','-') if letter == '-' or letter.isalnum()])

            ret = await channel.edit(name = name, reason = f"Edited by {str(ctx.author)} (ID: {ctx.author.id})")

        if slowmode is not None:
            if (slowmode <= 21600) and (slowmode >= 0):
                ret = await channel.edit(slowmode_delay = slowmode)
            else:
                return await ctx.send("Invalid slowmode", ephemeral = True, delete_after = 5)

        elif name is None:
            return await ctx.send("Atleast one parameter except `channel` must be filled.", ephemeral = True, delete_after = 5)
        
        await ctx.send(f"{ret.mention} has been edited")

    #################################################################################################################

    @commands.cooldown(rate = 1, per = 10, type = BucketType.member)
    @commands.has_guild_permissions(moderate_members = True)
    @commands.hybrid_command(description = "Shows all emotes for the current server", aliases = ['emojis'])
    async def emotes(self, ctx: commands.Context):
        em = discord.Embed(color = EMBED_COLOR, title = "All emotes for this server", description = "Click on the index for the URL")
        em_list = [em]
        value = ""
        em.add_field(name = "_ _", value = "_ _", inline = False)
        field_id = 0

        for num, emote in enumerate(ctx.guild.emojis):
            if len(value) > 900:
                em.set_field_at(field_id, name = "_ _", value = value, inline = False)

                if field_id == 24:
                    em = discord.Embed(color = EMBED_COLOR)
                    em_list.append(em)
                    field_id = 0
                
                value = ""
                em.add_field(name = "_ _", value = "_ _", inline = False)
                field_id += 1

            value += f"{emote} [`[{num+1}]`]({emote.url}) "
            
        em.set_field_at(field_id, name = "_ _", value = value, inline = False)
        await ctx.send(embed = em)
            
    @commands.cooldown(rate = 1, per = 10, type = BucketType.member)
    @commands.has_guild_permissions(manage_nicknames = True)
    @commands.hybrid_command(aliases = ['setnick','nick'], description = "Sets a member's nickname")
    async def nickname(self, ctx: commands.Context, member: discord.Member, *, nickname: str):
        if len(nickname) > 80:
            return await ctx.send("Nickname is too long", ephemeral = True, delete_after = 5)
        
        await member.edit(nick = nickname, reason = f"Pinned by {ctx.author} (ID: {ctx.author.id})")
        await ctx.send(f"Nickname has been changed to `{nickname.replace('`','')}`")

    @commands.cooldown(rate = 1, per = 10, type = BucketType.member)
    @commands.has_guild_permissions(manage_messages = True)
    @commands.hybrid_command(description = "Pins/unpins the message")
    async def pin(self, ctx: commands.Context, message: discord.Message = None):
        
        if message is None:
            if ctx.message.reference and isinstance(ctx.message.reference.resolved, discord.Message):
                message = ctx.message.reference.resolved
            else:
                return await ctx.send("Your message must reply to the message you want to pin", delete_after = 5, ephemeral = True)
        elif message.guild != ctx.guild:
            return await ctx.send("Message does not exist", delete_after = 5, ephemeral = True)

        if not message.pinned:
            await message.pin(reason = f"Pinned by {ctx.author} (ID: {ctx.author.id})")
            await ctx.send("Message has been pinned", ephemeral = True, delete_after = 10)
        else:
            await message.unpin(reason = f"Unpinned by {ctx.author} (ID: {ctx.author.id})")
            await ctx.send("Message has been unpinned", ephemeral = True, delete_after = 10)

    @commands.cooldown(rate = 1, per = 10, type = BucketType.member)
    @commands.has_guild_permissions(manage_messages = True)
    @commands.hybrid_command(description = "Purges a number of messages or a specific message or of a specific user.", aliases = ['delete'])
    @app_commands.describe(
        member = "(Optional) Deleting a specific member's message(s)",
        number = "(Optional) Number of messages to delete. This is 1 by default. This is ignored if message parameter is also filled.",
        message = "(Optional) Deleting a specific message. Replying works too (but in slash commands, fill in message link or ID)"
    )
    async def purge(self, ctx: commands.Context, member: Optional[discord.Member], number: Optional[int], message: discord.Message = None):
        
        number = 1 if number is None else number

        if not ctx.interaction:
            await ctx.message.delete()
        else:
            await ctx.interaction.response.defer()

        if message is None and ctx.message.reference and isinstance(ctx.message.reference.resolved, discord.Message):
            message = ctx.message.reference.resolved
        
        if message is not None and message.guild == ctx.guild:
            await message.delete()
            await ctx.send(f"Deleted the message!", ephemeral = True, delete_after = 5)

            if number != 1 or member is not None:
                await ctx.send("Deleted the message!\nYou have entered other parameters too. \
Leave the message parameter empty (and don't reply to a message) to execute with those parameters.", ephemeral = True, delete_after = 5)

            return

        def is_s(num):
            return 's' if num > 1 else ''


        if number > 500 or number <= 0:
            return await ctx.send("Invalid number. Keep it under 500 and above 0", ephemeral = True, delete_after = 5)

        if member is None:
            counter = 0

            async for message in ctx.channel.history(limit = number):
                counter += 1

            deleted = await ctx.channel.purge(limit = counter, bulk = True, after = discord.utils.utcnow() - timedelta(days = 14), oldest_first = False,
            reason = f"Action by {ctx.author} (ID :{ctx.author.id})")
            
            try:
                await ctx.send(f"Purged {len(deleted)} message{is_s(len(deleted))}", ephemeral = True, delete_after = 5)
            except discord.errors.NotFound:
                pass

            return
        
        else:
            global check_messages_deleted
            check_messages_deleted = 0
            
            def check(m: discord.Message) -> bool:
                global check_messages_deleted
                if check_messages_deleted < number:                    
                    if m.author == member:
                        check_messages_deleted += 1
                        return True
                else:
                    return False
        
            limit = 100 if number <= 100 else 750
            counter = 0
            async for message in ctx.channel.history(limit = limit):
                counter += 1

            deleted = await ctx.channel.purge(limit = counter, bulk = True,
            after = discord.utils.utcnow() - timedelta(days = 14), oldest_first = False, check = check,
            reason = f"Action by {ctx.author} (ID :{ctx.author.id})")

            try:
                await ctx.send(f"Purged {len(deleted)} message{is_s(len(deleted))}", ephemeral = True, delete_after = 5)
            except discord.errors.NotFound:
                pass

    @commands.cooldown(rate = 1, per = 10, type = BucketType.member)
    @commands.has_guild_permissions(moderate_members = True)
    @commands.hybrid_command(description = "Creates a poll, and can be sent to another channel optionally. Send all options with a comma.")
    @app_commands.describe(
        channel = "The channel the poll should be sent in. Defaults to current channel",
        multi_option = "If the user should be able to select multiple options. Defaults to True.",
        title = "Title of the poll. If not using slash command, use quotations if the title is more than one word",
        options = "Options to display. Send all options separated with comma. Maximum 23 options"
    )
    async def poll(self, ctx: commands.Context, channel: Optional[discord.TextChannel], multi_option: Optional[bool], title: str, *, options: str):
        
        if channel is None:
            channel = ctx.channel
        
        if channel.guild != ctx.guild:
            return await ctx.send("Invalid channel", ephemeral = True, delete_after = 5)

        if multi_option is None:
            multi_option = True

        option_list = [option.strip() for option in options.split(',')]

        if len(option_list) <= 1 or len(option_list) > 23:
            return await ctx.send("Your poll must have between 2 and 23 options", ephemeral = True, delete_after = 5)

        body_list = [f"**Option {num+1}**: {option}" for num, option in enumerate(option_list)]
        
        body = '\n'.join(body_list)
        em = discord.Embed(title = title, color = EMBED_COLOR, description = body)

        em.set_footer(text = f"Created by {ctx.author}")

        view = poll_views.Poll(len(option_list), self.bot.pool)

        view.msg = await channel.send(embed = em, view = view)

        await ctx.send("Done!", ephemeral = True, delete_after = 5)

        await self.bot.pool.execute(
        "INSERT INTO poll_table (message_id, creator_id, poll_options, multi_option, option_votes, used_users) VALUES ($1,$2,$3,$4,$5,$6)",
        view.msg.id, ctx.author.id, body_list, multi_option, [0] * len(option_list), '{}')


async def setup(bot: commands.Bot):
    
    await bot.add_cog(MUtility(bot))