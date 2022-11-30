import discord
from discord.ext import commands
from typing import List, Optional, Literal
from datetime import datetime, timedelta


class Paginator(discord.ui.View):
    def __init__(self, author: discord.User, list_of_embeds: List[discord.Embed]):
        super().__init__(timeout = 60)
        self.list_of_embeds = list_of_embeds
        self.author = author
        self.page_number = 1
        
        for child in self.children:
            if child.custom_id == 'page_num':
                child.label = f'1/{len(self.list_of_embeds)}'
        
    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        
        await self.msg.edit(view = self)

    async def interaction_check(self, itx: discord.Interaction) -> bool:
        self.msg = itx.message
        if itx.user == self.author:
            return True
        await itx.response.send_message("You are not authorized for this interaction.", ephemeral = True)
    
    @discord.ui.button(label = "First page", disabled = True, style = discord.ButtonStyle.blurple, custom_id = 'first_page')
    async def first_page(self, itx: discord.Interaction, button: discord.ui.Button):
        self.page_number = 1

        for child in self.children:
            if child.custom_id == 'previous_page':
                child.disabled = True
            elif child.custom_id == 'page_num':
                child.label = f"1/{len(self.list_of_embeds)}"
            else:
                child.disabled = False
        
        button.disabled = True

        await self.msg.edit(embed = self.list_of_embeds[0], view = self)
        await itx.response.send_message("You are on first page", ephemeral = True, delete_after = 1)
    
    @discord.ui.button(label = "Previous page", disabled = True, style = discord.ButtonStyle.blurple, custom_id = 'previous_page')
    async def previous_page(self, itx: discord.Interaction, button: discord.ui.Button):
        
        self.page_number -= 1

        for child in self.children:
            if child.custom_id == 'first_page' and self.page_number == 1:
                child.disabled = True
            elif child.custom_id == 'page_num':
                child.label = f"{self.page_number}/{len(self.list_of_embeds)}"
            else:
                child.disabled = False
        
        if self.page_number == 1:
            button.disabled = True

        await self.msg.edit(embed = self.list_of_embeds[self.page_number - 1], view = self)
        await itx.response.send_message(f"You are on page {self.page_number}", ephemeral = True, delete_after = 1)

    @discord.ui.button(label = "pg", disabled = True, style = discord.ButtonStyle.grey, custom_id = 'page_num')
    async def page_num(self, itx: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(label = "Next page", style = discord.ButtonStyle.blurple, custom_id = 'next_page')
    async def next_page(self, itx: discord.Interaction, button: discord.ui.Button):
        
        self.page_number += 1

        for child in self.children:
            if child.custom_id == 'last_page' and self.page_number == len(self.list_of_embeds):
                child.disabled = True
            elif child.custom_id == 'page_num':
                child.label = f"{self.page_number}/{len(self.list_of_embeds)}"
            else:
                child.disabled = False
        
        if self.page_number == len(self.list_of_embeds):
            button.disabled = True

        await self.msg.edit(embed = self.list_of_embeds[self.page_number - 1], view = self)
        await itx.response.send_message(f"You are on page {self.page_number}", ephemeral = True, delete_after = 1)

    @discord.ui.button(label = "Last page", style = discord.ButtonStyle.blurple, custom_id = 'last_page')
    async def last_page(self, itx: discord.Interaction, button: discord.ui.Button):
        self.page_number = len(self.list_of_embeds)

        for child in self.children:
            if child.custom_id == 'next_page':
                child.disabled = True
            elif child.custom_id == 'page_num':
                child.label = f"{self.page_number}/{len(self.list_of_embeds)}"
            else:
                child.disabled = False
        
        button.disabled = True

        await self.msg.edit(embed = self.list_of_embeds[self.page_number - 1], view = self)
        await itx.response.send_message(f"You are on page {self.page_number}", ephemeral = True, delete_after = 1)

EMBED_COLOR = discord.Color.from_str("#9fca77")

class Confirm(discord.ui.View):
    # taken from discord.py view examples
    def __init__(self, author: discord.Member):
        super().__init__(timeout = 180)
        self.value = None
        self.author = author

    async def interaction_check(self, interaction: discord.Interaction, /) -> bool:
        if self.author == interaction.user:
            return True
        return False

    @discord.ui.button(label='Confirm', style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = True
        self.stop()

    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()

def offence_dm_embed_maker(action_past: str, preposition: Optional[Literal['from', 'in']], server: str, reason: str, additional_message: str | None = None,
until: datetime = None) -> discord.Embed:
    if preposition is None:
        preposition = 'from'
    dm_em = discord.Embed(color = EMBED_COLOR, title = f"Moderator Action: you have been {action_past}",
    description = f"You have been {action_past} {preposition} **{server}**.\n**Reason:** {reason}")

    if additional_message is not None:
        dm_em.add_field(name = "Additional Message", value = additional_message, inline = False)
    
    if until is not None:
        dm_em.description = f"You have been {action_past} from **{server}**.\n**Ends {discord.utils.format_dt(until,'R')}**\n**Reason:** {reason}"

    return dm_em

def offence_embed_maker(action: str, action_past: str,  user: discord.Member | discord.User, mod: discord.Member, reason: str, sent: bool,
until: datetime = None) -> discord.Embed:
    em = discord.Embed(color = EMBED_COLOR, title = f"Moderator Action: ` {action} `",
    description = f"User **`{user} (ID: {user.id})`** has been {action_past}.\n**Reason:** {reason}")

    em.set_author(name = str(mod), icon_url = mod.display_avatar.url)
    
    if until is not None:
        em.description = f"""User **`{user} (ID: {user.id})`** has been {action_past}.
**Ends {discord.utils.format_dt(until,'R')}**
**Reason:** {reason}"""

    em.set_footer(text = f"DM to the user {'has been sent' if sent else 'could not be sent'}")

    return em

class TimeParser:
    @classmethod
    async def convert(cls, ctx, argument: str) -> timedelta | None:
        time = argument.replace(" ","")
        parsed_amount = ""
        seconds = 0

        if time.isnumeric():
            return timedelta(hours=int(time))

        for x in time:
            is_tt = True
            if x.isnumeric():
                parsed_amount += x
                is_tt = False

            elif x not in ['s','m','h','d','w','o']:
                x = 'h'

            if is_tt and parsed_amount!='':
                parsed_amount = int(parsed_amount)
                if x == 's':
                    seconds += parsed_amount
                elif x == 'm':
                    seconds += parsed_amount*60
                elif x == 'h':
                    seconds += parsed_amount*3600
                elif x == 'd':
                    seconds += parsed_amount*3600*24
                elif x == 'w':
                    seconds += parsed_amount*3600*24*7
                elif x == 'o':
                    seconds += parsed_amount*3600*24*28
                
                parsed_amount = ""
        
        if seconds == 0:
            raise commands.BadArgument(message = "Could not parse")
        
        return timedelta(seconds=seconds)

class ColorParser:
    @classmethod
    async def convert(cls, ctx, argument: str):
        if argument.startswith('0x') or argument.startswith('#') or argument.startswith('0x#'):
            return discord.Color.from_str(argument)
        try:
            if len(argument) == 6:
                return discord.Color.from_str(f"#{argument}")
            raise
        except:
            raise commands.BadArgument("Invalid color code provided")

def time_unparser(time:timedelta) -> str:
    ret = []
    if time is None:
        time = timedelta()
    days = time.days
    seconds = time.seconds
    if days >= 1:
        ret.append(f"{days}d")
    
    if seconds >= 3600:
        hours = int(seconds/3600)
        ret.append(f"{hours}h")
        
        seconds -= hours*3600

    if seconds >=60:
        minutes = int(seconds/60)
        ret.append(f"{minutes}m")
        seconds -= minutes*60
    
    if seconds > 0:
        ret.append(f"{seconds}s")

    return " ".join(ret)
