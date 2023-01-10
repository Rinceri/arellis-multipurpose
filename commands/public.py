import discord
from discord.ext import commands
from discord.ext.commands.cooldowns import BucketType
from asyncpg import Connection
from typing import Optional
from random import choice

EMBED_COLOR = discord.Color.from_str("#ddb857")
SERVER_LINK = "https://discord.gg/gjRfPR8Rcm"
GITHUB_LINK = "https://github.com/Rinceri/arellis-multipurpose"


class Tags(commands.Cog, name = "tags", description = "Tags return specified text when they are called"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_check(self, ctx: commands.Context) -> bool:
        if ctx.channel.type == discord.ChannelType.private:
            return False

        b_c = await self.bot.pool.fetchval("SELECT blacklisted_channels FROM guild_table WHERE guild_id = $1", ctx.guild.id)

        if b_c is not None and ctx.channel.id in b_c:
            return False
        return True

    @commands.hybrid_group(invoke_without_command = True)
    async def tag(self, ctx: commands.Context, *, name: str):
        view = self.bot.get_command('tag view')

        await ctx.invoke(view, name = name)

    @tag.command(name = "create", description = "Creates a tag with a given unique name. If using text command, quote the name parameter")
    async def t_create(self, ctx: commands.Context, name: str, *, content: str):
        conn: Connection = self.bot.pool

        server_tags = await conn.fetch("SELECT tag_name, aliases FROM tags WHERE guild_id = $1", ctx.guild.id)
        
        name = name.strip().lower()

        if len(name) > 255:
            return await ctx.send("Tag name is too long. Keep it below 255 characters", ephemeral = True, delete_after = 5)

        aliases = [alias for server_tag in server_tags for alias in server_tag['aliases']]

        if name in [server_tag['tag_name'] for server_tag in server_tags] or name in aliases:
            return await ctx.send("Tag with this name already exists", ephemeral = True, delete_after = 5)

        content = discord.utils.escape_mentions(content)

        await conn.execute("INSERT INTO tags(guild_id, tag_name, body, created_by, created_on, aliases) VALUES($1,$2,$3,$4,$5,$6)",
        ctx.guild.id, name, content, ctx.author.id, discord.utils.utcnow(), [])

        await ctx.send("Tag has been created")

    @tag.command(name = "delete", description = "Deletes a tag, or all of a user, or an alias. Should be either administrator or tag owner to do so")
    async def t_delete(self, ctx: commands.Context, user: Optional[discord.Member], *, name: Optional[str]):
        conn: Connection = self.bot.pool
        if name is not None:
            name = name.strip().lower()

        if user is not None:
            if ctx.author.guild_permissions.administrator or ctx.author == user:
                await conn.execute("DELETE FROM tags WHERE created_by = $1 and guild_id = $2", user.id, ctx.guild.id)
                return await ctx.send("Tag(s) have been deleted")
            else:
                return await ctx.send("You do not have permission to delete this user's tags", ephemeral = True, delete_after = 5)

        server_tags = await conn.fetch("SELECT * FROM tags WHERE guild_id = $1", ctx.guild.id)
    
        for server_tag in server_tags:
            if name in server_tag['aliases']:
                tag_id = server_tag['id']
                
                if server_tag['created_by'] == ctx.author.id or ctx.author.guild_permissions.administrator:
                    aliases:list = server_tag['aliases']
                    aliases.remove(name)

                    await conn.execute("UPDATE tags SET aliases = $1 WHERE id = $2", aliases, tag_id)

                    return await ctx.send("Alias has been removed")
                
                else:
                    return await ctx.send("You do not have permission to delete this user's aliases", ephemeral = True, delete_after = 5)

            elif name in server_tag['tag_name']:
                tag_id = server_tag['id']

                if server_tag['created_by'] == ctx.author.id or ctx.author.guild_permissions.administrator:
                    await conn.execute("DELETE FROM tags WHERE id = $1", tag_id)
                    return await ctx.send("Done!")
                else:
                    return await ctx.send("You do not have permission to delete this user's tag", ephemeral = True, delete_after = 5)

        await ctx.send("Tag/alias does not exist", ephemeral = True, delete_after = 5)

    @tag.command(name = "edit", description = "Edits the tag content. Should be tag owner to do so")
    async def t_edit(self, ctx: commands.Context, name: str, *, new_content: str):
        conn: Connection = self.bot.pool
        name = name.strip().lower()

        record = await conn.fetchrow("SELECT * FROM tags WHERE tag_name = $1 and guild_id = $2", name, ctx.guild.id)

        if record is None:
            return await ctx.send("Tag with this name does not exist", ephemeral = True, delete_after = 5)

        if record['created_by'] != ctx.author.id:
            return await ctx.send("You need to be the tag owner to edit this", ephemeral = True, delete_after = 5)

        content = discord.utils.escape_mentions(new_content)

        await conn.execute("UPDATE tags SET body = $1 WHERE id = $2", content, record['id'])

        await ctx.send("Tag has been edited")

    @tag.command(name = "alias", descriptiom = "Creates an alias for an existing tag. 10 aliases maximum per tag.")
    async def t_alias(self, ctx: commands.Context, name: str, *, alias: str):
        
        conn: Connection = self.bot.pool
        name = name.strip().lower()
        alias = alias.strip().lower()

        if len(alias) > 255:
            return await ctx.send("Tag alias is too long. Keep it under 255 characters", ephemeral = True, delete_after = 5)

        record = await conn.fetchrow("SELECT * FROM tags WHERE tag_name = $1 and guild_id = $2", name, ctx.guild.id)
        server_aliases = await conn.fetch("SELECT tag_name, aliases FROM tags WHERE guild_id = $1", ctx.guild.id)
        
        if record is None:
            return await ctx.send("Tag with this name does not exist", ephemeral = True, delete_after = 5)

        if alias in [alias for server_tag in server_aliases for alias in server_tag['aliases']] or\
            alias in [tag_name['tag_name'] for tag_name in server_aliases]:
            return await ctx.send("Alias already exists for a tag.", ephemeral = True, delete_after = 5)

        aliases = record['aliases']

        if len(aliases) >= 10:
            return await ctx.send("Maximum 10 aliases for a tag", ephemeral = True, delete_after = 5)

        aliases.append(alias)

        await conn.execute("UPDATE tags SET aliases = $1 WHERE id = $2", aliases, record['id'])

        await ctx.send("Tag has been aliased")

    @tag.command(name = "view", description = "View a tag's content, either with its name or alias")
    async def t_view(self, ctx: commands.Context, *, name: str):
        tag = await self.bot.pool.fetchval("SELECT body FROM tags WHERE guild_id = $1 AND (tag_name = $2 or $2 = ANY(aliases))",
        ctx.guild.id, name.strip().lower())

        if tag is None:
            return await ctx.send("Tag does not exist.", ephemeral = True, delete_after = 5)

        await ctx.send(tag)

    @tag.command(name = "claim", description = "Claim a tag, if the owner has left the server")
    async def t_claim(self, ctx: commands.Context, *, name: str):

        tag = await self.bot.pool.fetchrow("SELECT * FROM tags WHERE guild_id = $1 AND (tag_name = $2 or $2 = ANY(aliases))",
        ctx.guild.id, name.strip().lower())

        if tag is None:
            return await ctx.send("Tag does not exist.", ephemeral = True, delete_after = 5)

        try:
            await ctx.guild.fetch_member(tag['created_by'])
        except discord.errors.NotFound:
            pass
        else:
            return await ctx.send("Member is in server", ephemeral = True, delete_after = 5)

        await self.bot.pool.execute("UPDATE tags SET created_by = $1 WHERE id = $2", ctx.author.id, tag['id'])

        await ctx.send("Tag has been claimed")

    @tag.command(name = "info", description = "Get info for a tag")
    async def t_info(self, ctx: commands.Context, *, name: str):
        
        tag = await self.bot.pool.fetchrow("SELECT * FROM tags WHERE guild_id = $1 AND (tag_name = $2 or $2 = ANY(aliases))",
        ctx.guild.id, name.strip().lower())

        if tag is None:
            return await ctx.send("Tag with this name/alias does not exist", ephemeral = True, delete_after = 5)
        
        try:
            author = await self.bot.fetch_user(tag['created_by'])
            mention_author = author.mention
        except discord.errors.NotFound:
            author = tag['created_by']
            mention_author = author
        
        try:
            await ctx.guild.fetch_member(tag['created_by'])
            still = True
        except discord.errors.NotFound:
            still = False

        em = discord.Embed(color = discord.Color.from_str("#ddb857"), title = tag['tag_name'],
        description = f"""**Created by**: {mention_author} (`{author}` is {'still' if still else 'not'} in server)
**Created on**: {discord.utils.format_dt(tag['created_on'], 'D')}""")

        field_val = ', '.join(f"`{alias.replace('`','')}`" for alias in tag['aliases']) if len(tag['aliases']) >= 1 else "`None`"
        em.add_field(name = 'Aliases', value = field_val)

        em.set_footer(text = f"Requested by {ctx.author}", icon_url = ctx.author.display_avatar.url)

        await ctx.send(embed = em)

    @tag.command(name = "transfer", description = "Transfers a tag to another user. Need to be administrator or tag owner.")
    async def t_transfer(self, ctx: commands.Context, member: discord.Member, *, name: str):
        tag = await self.bot.pool.fetchrow("SELECT * FROM tags WHERE guild_id = $1 AND (tag_name = $2 or $2 = ANY(aliases))",
        ctx.guild.id, name.strip().lower())

        if tag is None:
            return await ctx.send("Tag with this name/alias does not exist", ephemeral = True, delete_after = 5)
        
        if tag['created_by'] == ctx.author.id or ctx.author.guild_permissions.administrator:
            pass
        else:
            return await ctx.send("You need to be tag owner or administrator to transfer this tag.", ephemeral = True, delete_after = 5)

        await self.bot.pool.execute("UPDATE tags SET created_by = $1 WHERE id = $2", member.id, tag['id'])

        await ctx.send(f"Tag has been transferred to `{member}`")

class PUtility(commands.Cog, name = "public utility"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_check(self, ctx: commands.Context) -> bool:
        if ctx.channel.type == discord.ChannelType.private:
            return False

        b_c = await self.bot.pool.fetchval("SELECT blacklisted_channels FROM guild_table WHERE guild_id = $1", ctx.guild.id)

        if b_c is not None and ctx.channel.id in b_c:
            return False
        return True

    @commands.cooldown(rate = 1, per = 5, type = BucketType.user)
    @commands.command(hidden = True, description = "bottle is best fr") # this just a hidden command for fun lol
    async def bottle(self, ctx: commands.Context):
        lis = ['misterlustre#3885 got five comically long metal spoons down his throat', 'unnamed#1680 likes women', 'i hate nestle',
        'https://cdn.discordapp.com/attachments/723334075024277532/1047157602620026920/Synthol_man_kiss_meme.mp4']
        await ctx.send(choice(lis))

    @commands.cooldown(rate = 1, per = 5, type = BucketType.member)
    @commands.hybrid_command(description = "Gives the attachemnt link(s) in replied message or message passed in (either through ID or link)")
    async def givelink(self, ctx: commands.Context, message: discord.Message = None):

        if message is None and ctx.message.reference and isinstance(ctx.message.reference.resolved, discord.Message):
            message = ctx.message.reference.resolved
        
        if message is None:
            return await ctx.send("Message parameter must be filled either with ID, message link or reply", ephemeral = True, delete_after = 5)
        
        attachment_list = [f"`{attachment.url}`" for attachment in message.attachments]

        if attachment_list == []:
            return await ctx.send("Message has no attachments", ephemeral = True, delete_after = 5)

        content = '\n'.join(attachment_list)

        await ctx.send(content, ephemeral = True)

    @commands.has_guild_permissions()
    @commands.cooldown(rate = 1, per = 10, type = BucketType.member)
    @commands.hybrid_command(aliases = ['guildinfo'], description = "Get info for the current server.")
    async def serverinfo(self, ctx: commands.Context):
        em = discord.Embed(title = ctx.guild.name, color = EMBED_COLOR,
        description = f"**Owner**: {ctx.guild.owner.mention} (ID: {ctx.guild.owner_id})")

        # AUTHOR
        icon_url = ctx.guild.icon.url if ctx.guild.icon is not None else None
        em.set_author(icon_url = icon_url, name = f"ID {ctx.guild.id}")

        # FIELDS
        field_dict_1 = {'Created on': discord.utils.format_dt(ctx.guild.created_at, 'D'),
            'Vanity URL': ctx.guild.vanity_url if ctx.guild.vanity_url is not None else "```None```"}

        for key, item in field_dict_1.items():
            em.add_field(name = key, value = item)

        em.add_field(name = "Description", value = f"```{ctx.guild.description}```" if ctx.guild.description is not None else "```None```",
        inline = False)


        guild: discord.Guild = await self.bot.fetch_guild(ctx.guild.id)
        field_dict_2 = {'Members': f"```{guild.approximate_member_count} ({guild.approximate_presence_count} active)```",
            'Roles': f"```{len(ctx.guild.roles)}```"}

        for key, item in field_dict_2.items():
            em.add_field(name = key, value = item)

        text = len(ctx.guild.text_channels)
        voice = len(ctx.guild.voice_channels)
        stage = len(ctx.guild.stage_channels)
        forum = len(ctx.guild.forums)

        channel_val = f"{text} text, {voice} voice, {stage} stage, {forum} forum"

        total_channels = f"---> total {text + voice + stage + forum}"

        em.add_field(name = "Channels", value = "```diff\n{0}\n{1}```".format(channel_val, total_channels), inline = False)

        static_emojis = 0
        animated_emojis = 0

        for emoji in ctx.guild.emojis:
            if emoji.animated:
                animated_emojis += 1
            else:
                static_emojis += 1

        emoji_val = f"""```Static emojis: {static_emojis}/{ctx.guild.emoji_limit} used
Animated emojis: {animated_emojis}/{ctx.guild.emoji_limit} used
Stickers: {len(ctx.guild.stickers)}/{ctx.guild.sticker_limit} used```"""
        
        em.add_field(name = "Emojis and Stickers", value = emoji_val)

        # IMAGE AND THUMBNAIL
        if ctx.guild.banner is not None:
            em.set_image(url = ctx.guild.banner.url)

        if ctx.guild.icon is not None:
            em.set_thumbnail(url = ctx.guild.icon.url)

        # FOOTER
        em.set_footer(text = f"Requested by {ctx.author}", icon_url = ctx.author.display_avatar.url)

        # SEND
        await ctx.send(embed = em)

    @commands.cooldown(rate = 1, per = 10, type = BucketType.member)
    @commands.hybrid_command(aliases = ['botinfo'], description = "Get info for the bot")
    async def info(self, ctx: commands.Context):
        
        body = f"""The bot uses **discord.py** library. Created by **bottle#9957**.

The bot is relatively new, so recommend us features, or report bugs at {SERVER_LINK}

It's open-source! View the code at {GITHUB_LINK}

The bot is in {len(self.bot.guilds)} servers."""
        
        em = discord.Embed(title = "Arellis", color = EMBED_COLOR, description = body)

        await ctx.send(embed = em)

    @commands.cooldown(rate = 1, per = 10, type = BucketType.member)
    @commands.has_guild_permissions(moderate_members = True)
    @commands.hybrid_command(aliases = ['whois', 'ui'], description = "Get info for a server member. Requires timeout member permission.")
    async def userinfo(self, ctx: commands.Context, *, member: discord.Member = None):
        
        if member is None:
            member = ctx.author

        join_date = discord.utils.format_dt(member.joined_at, 'D')
        reg_date = discord.utils.format_dt(member.created_at, 'D')
        since = discord.utils.format_dt(member.joined_at, 'R')
        
        body = f"{member.mention} (` ID: {member.id} `)\n\nJoined on **{join_date}** and account created on **{reg_date}** (joined **{since}**)"

        em = discord.Embed(color = discord.Color.from_str('#ddb857'), description = body)

        em.set_author(name = member, icon_url = member.display_avatar.url)
        em.set_thumbnail(url = member.display_avatar.url)

        em.add_field(name = "User avatar URL", value = f"[Click here]({member.avatar.url})")
        
        if member.guild_avatar is not None:
            em.add_field(name = "Server avatar URL", value = f"[Click here]({member.guild_avatar.url})")

        if member.banner is not None:
            em.add_field(name = "Banner URL", value = f"[Click here]({member.banner.url})")

        em.set_footer(text = f"Requested by {ctx.author}", icon_url = ctx.author.display_avatar.url)
        
        await ctx.send(embed = em)


async def setup(bot: commands.Bot):
    
    await bot.add_cog(Tags(bot))
    await bot.add_cog(PUtility(bot))