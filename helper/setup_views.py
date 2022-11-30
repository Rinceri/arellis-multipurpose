import discord
from discord.ext.commands import Bot
from asyncpg import Connection
import traceback, sys
from datetime import timedelta
from helper.other import TimeParser
from helper.join_view import VerifyMessageView


EMBED_COLOR = discord.Color.from_str("#9fca77")

# ADDITIONAL MESSAGE VIEWS

class AdditionalMessage(discord.ui.View):
    def __init__(self, author: discord.Member, pool):
        super().__init__(timeout = 300)
        self.author = author
        self.pool = pool
    
    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        await self.msg.edit(view = self)

    async def interaction_check(self, itx: discord.Interaction, /) -> bool:
        if self.author == itx.user:
            return True
        await itx.response.send_message("You are not authorized for this interaction.", ephemeral = True)
        return False
    
    @discord.ui.button(label = "Set message", style = discord.ButtonStyle.green)
    async def set_message(self, itx: discord.Interaction, button: discord.ui.Button):
        await itx.response.send_modal(AdditionalMessageModal(self.pool, self.msg))

class AdditionalMessageModal(discord.ui.Modal):
    def __init__(self, pool, msg: discord.Message) -> None:
        super().__init__(title = "Set additional message", timeout = 300)
        self.message = discord.ui.TextInput(label = "Enter here", style = discord.TextStyle.long, placeholder = "Leave empty to remove message",
        required = False, max_length = 1024)
        self.add_item(self.message)
        self.pool = pool
        self.msg = msg

    async def on_submit(self, itx: discord.Interaction, /):
        if self.message.value.replace(' ', '') == "":
            offence_message = None
        else:
            offence_message = self.message.value.strip()
        
        await self.pool.execute("UPDATE guild_table SET offence_message = $1 WHERE guild_id = $2", offence_message, itx.guild.id)

        if offence_message is None:
            await itx.response.send_message("Removed additional message.", ephemeral = True)
            self.msg.embeds[0].description = 'None has been set'
            await self.msg.edit(embed = self.msg.embeds[0])
        else:
            await itx.response.send_message(f"Set message to: {offence_message}", ephemeral = True)
            self.msg.embeds[0].description = offence_message
            await self.msg.edit(embed = self.msg.embeds[0])

        self.stop()

# VERIFICATION SETUP VIEW

class VerificationView(discord.ui.View):
    def __init__(self, author: discord.Member, pool):
        super().__init__(timeout = 300)
        self.author = author
        self.pool = pool

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        await self.msg.edit(view = self)

    async def interaction_check(self, itx: discord.Interaction, /) -> bool:
        if self.author == itx.user:
            return True
        await itx.response.send_message("You are not authorized for this interaction.", ephemeral = True)
        return False

    async def on_error(self, itx: discord.Interaction, error: Exception, item, /) -> None:
        await itx.response.send_message("An error occurred. Make sure I have manage channel and roles permissions.", ephemeral = True)

    @discord.ui.button(label = "Create channel (and role if not found)")
    async def create_channel(self, itx: discord.Interaction, button: discord.ui.Button):
        await itx.response.defer(ephemeral = True, thinking = True)
        role_id = await self.pool.fetchval("SELECT verify_role FROM join_stats WHERE guild_id = $1", itx.guild.id)
        
        if role_id is not None:
            role = itx.guild.get_role(role_id)
            if role is None:
                role_id = None
            elif role > itx.guild.me.roles[-1]:
                role_id = None

        if role_id is None:
            role = await itx.guild.create_role(reason = "verify role", name = "not verified")
            
        for channel in itx.guild.channels:
            if channel.permissions_for(role).read_messages:
                await channel.edit(overwrites = {role: discord.PermissionOverwrite(read_messages = False)})

        overwrites = {itx.guild.default_role: discord.PermissionOverwrite(read_messages = False, send_messages = False),
        role: discord.PermissionOverwrite(read_messages = True, send_messages = False),
        itx.guild.me: discord.PermissionOverwrite(read_messages = True, send_messages = True)}

        channel = await itx.guild.create_text_channel(name = "verify-here", reason = "Verification channel", position = 0,
        topic = "Press 'Verify here' to get a code which is used for verification.", overwrites = overwrites)

        em = discord.Embed(color = EMBED_COLOR, title = "Verify by clicking the button",
        description = "Click the button, then enter the code you see in the new message.")

        view = VerifyMessageView(self.pool)

        msg = await channel.send(embed = em, view = view)

        await self.pool.execute("UPDATE join_stats SET verify_role = $1, verify_channel = $2, verify_message = $3 WHERE guild_id = $4",
        role.id, channel.id, msg.id, itx.guild.id)

        self.msg.embeds[0].description = f"Channel {channel.mention}\nRole used: {role.mention}"
        button.disabled = True
        await self.msg.edit(embed = self.msg.embeds[0], view = self)

        await itx.followup.send(f"Created channel {channel.mention}\nRole: {role.mention}")

        self.stop()

# WARN SETUP VIEWS

class WarnView(discord.ui.View):
    def __init__(self, author: discord.User, bot: Bot, field_0, field_1):
        super().__init__(timeout = 600)
        self.author = author
        self.bot = bot
        self.field_0 = field_0
        self.field_1 = field_1

    async def interaction_check(self, itx:discord.Interaction, /) -> bool:
        if itx.user == self.author:
            self.msg = itx.message
            return True
        await itx.response.send_message("You are not authorized for this interaction.", ephemeral = True)
        return False

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        await self.msg.edit(view = self)

    @discord.ui.button(label="Add threshold",style=discord.ButtonStyle.blurple,row=0)
    async def addt(self,itx:discord.Interaction,button:discord.ui.Button):
        thresholds = await self.bot.pool.fetch("SELECT * FROM autopunishments WHERE guild_id=$1",itx.guild.id)
        if len(thresholds)>=10:
            return await itx.response.send_message("You can only have 10 thresholds maximum.",ephemeral=True)
        await itx.response.send_modal(AddThreshold(self.bot.pool,self.msg,self.field_0,self.field_1))


    @discord.ui.button(label="Remove threshold",style=discord.ButtonStyle.blurple,row=0)
    async def removet(self,itx:discord.Interaction,button:discord.ui.Button):
        if await self.bot.pool.fetchval("SELECT EXISTS (SELECT 1 FROM autopunishments WHERE guild_id=$1)",itx.guild.id):
            options = [discord.SelectOption(label=x['points'],value=x['id']) for x in await self.bot.pool.fetch("SELECT id,points FROM autopunishments\
                WHERE guild_id=$1",itx.guild.id)]
            view = RemoveThreshold(self.author,self.bot.pool,self.msg,options,self.field_0,self.field_1)
            await itx.response.send_message("Press **Submit** to submit.",view=view)
            button.disabled = True
            await self.msg.edit(view=self)
            await view.wait()
            button.disabled = False
            await self.msg.edit(view=self)
            a = await itx.original_response()
            await a.delete()

        else:
            await itx.response.send_message("No thresholds have been set.", ephemeral = True)
    

    @discord.ui.button(label="Add autocomplete",style=discord.ButtonStyle.blurple,row=1)
    async def adda(self,itx:discord.Interaction,button:discord.ui.Button):
        if await self.bot.pool.fetchval("SELECT COUNT(*) FROM autocompletes WHERE guild_id=$1",itx.guild.id)<25:
            await itx.response.send_modal(AddAutocomplete(self.bot.pool,self.msg,self.field_1))
        else:
            return await itx.response.send_message("Maximum 25 autocompletes.")
    
    @discord.ui.button(label="Remove autocomplete",style=discord.ButtonStyle.blurple,row=1)
    async def removea(self,itx:discord.Interaction,button:discord.ui.Button):
        if await self.bot.pool.fetchval("SELECT EXISTS (SELECT 1 FROM autocompletes WHERE guild_id=$1)",itx.guild.id):
            options = [
                discord.SelectOption(label = x['reason'][:100], value = x['id'], description = x['points']) 
                for x in await self.bot.pool.fetch("SELECT * FROM autocompletes WHERE guild_id=$1", itx.guild.id)
                ]
                
            view = RemoveAutocomplete(self.author,self.bot.pool,self.msg,options,self.field_1)
            
            await itx.response.send_message("Press **Submit** to submit.",view=view)
            await view.wait()
            a = await itx.original_response()
            await a.delete()
        else:
            await itx.response.send_message("No autocomplete responses have been set.",ephemeral=True)

class AddThreshold(discord.ui.Modal):
    def __init__(self, pool: Connection, parent_msg: discord.Message, field_0, field_1) -> None:
        super().__init__(title="Add Threshold", timeout=600)
        self.pool = pool
        self.parent_msg = parent_msg
        self.field_0 = field_0
        self.field_1 = field_1

        self.threshold_points = discord.ui.TextInput(label="Points for threshold",placeholder="The number of points to reach this threshold",max_length=3)
        self.threshold_ptype = discord.ui.TextInput(label="Punishment Type",placeholder="'Ban' for ban. 'Kick' for kick. 'Timeout' or 'Mute' for timeout")
        self.threshold_timer = discord.ui.TextInput(label="Timer (Ignore if permanent ban/kick)",
        placeholder="'o' for months, 'w' for weeks, 'd' for days, 'h' for hours, 'm' for minutes. Example: '2o  12h 5m'",
        required=False)
        
        self.add_item(self.threshold_points)
        self.add_item(self.threshold_ptype)
        self.add_item(self.threshold_timer)

    async def on_submit(self, itx: discord.Interaction, /):
        thresholds = await self.pool.fetch("SELECT * FROM autopunishments WHERE guild_id=$1",itx.guild.id)

        try:
            tpoints = int(self.threshold_points.value)
            if tpoints <= 0:
                raise
        except:
            return await itx.response.send_message("Invalid number of points",ephemeral=True)

        if tpoints in [int(x['points']) for x in thresholds]:
            return await itx.response.send_message("A threshold for this number of points already exists!",ephemeral=True)

        if self.threshold_ptype.value.lower() not in ['ban','kick','timeout','mute']:
            return await itx.response.send_message("Invalid punishment type entered.",ephemeral=True)

        try:
            timer = await TimeParser.convert(itx, argument = str(self.threshold_timer.value.lower()))
        except:
            timer = timedelta(days = 0)

        if self.threshold_ptype.value.lower() in ['mute',"timeout"]  and (timer.days >= 27 or (timer.days==0 and timer.seconds==0)):
            timer = timedelta(days=28)

        if (timer.days==0 and timer.seconds==0) or self.threshold_ptype.value.lower() == 'kick':
            timer = None

        ban_points = [int(x['points']) for x in thresholds if x['p_type']=='ban']
        if len(ban_points)==1:
            if ban_points[0] < tpoints or (self.threshold_ptype.value.lower()=='ban' and timer is None):
                return await itx.response.send_message("Permanent ban already exists.",ephemeral=True)
    
        info_dictt = {"timeout":"mute","ban":"bant","mute":"mute"}
        info_dict = {"kick":"kick","ban":"ban"}
        p_type = info_dictt[self.threshold_ptype.value.lower()] if timer is not None else info_dict[self.threshold_ptype.value.lower()]

        await self.pool.execute("INSERT INTO autopunishments (guild_id,points,p_type,timer) VALUES($1,$2,$3,$4)",itx.guild.id,tpoints,p_type,timer)
        
        
        field0_value = '\n'.join(await self.field_0())
        self.parent_msg.embeds[0].set_field_at(index=0,name="Thresholds",value=f"```{field0_value}```")
        
        max_rec = await self.pool.fetchrow("SELECT * FROM autopunishments WHERE guild_id=$1 AND p_type='ban'",itx.guild.id)

        self.parent_msg.embeds[0].set_field_at(index=1,name="Maximum",value=await self.field_1(max_rec))
        await self.parent_msg.edit(embed=self.parent_msg.embeds[0])

        await itx.response.send_message("Done!",ephemeral=True)

    async def on_error(self, itx: discord.Interaction, error: Exception, /) -> None:
            print('Ignoring exception in command {}:'.format(itx.command), file=sys.stderr)
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

class ThresholdDropdown(discord.ui.Select):
    def __init__(self,options:discord.SelectOption):
        super().__init__(placeholder='Select modules', min_values=1,max_values=len(options), options=options,row=0)

    async def callback(self, itx: discord.Interaction):
        self.view.modules = self.values
        await itx.response.send_message(f"Alright! Now, press **Submit** to store them.",ephemeral=True)

class RemoveThreshold(discord.ui.View):
    def __init__(self, author: discord.User, pool: Connection, parent_msg: discord.Message, options: discord.SelectOption, field_0, field_1):
        super().__init__(timeout=300)
        self.add_item(ThresholdDropdown(options))
        self.options = options
        self.modules = []
        self.author = author
        self.pool = pool
        self.parent_msg = parent_msg
        self.field_0 = field_0
        self.field_1 = field_1

    async def interaction_check(self, itx: discord.Interaction, /) -> bool:
        if itx.user==self.author:
            return True
        await itx.response.send_message("You are not authorized for this interaction.",ephemeral=True)
        return False

    async def on_error(self, itx: discord.Interaction, error: Exception, item) -> None:
            print('Ignoring exception in command {}:'.format(itx.command), file=sys.stderr)
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

    @discord.ui.button(label='Submit',row=1)
    async def submit(self, itx: discord.Interaction, button: discord.ui.Button):
        if self.modules == []:
            return await itx.response.send_message("You have not selected any thresholds to remove",ephemeral=True)
    
        await self.pool.executemany("DELETE FROM autopunishments WHERE id=$1",[(int(x),) for x in self.modules])
        
        field0_value = '\n'.join(await self.field_0())
        self.parent_msg.embeds[0].set_field_at(index=0,name="Thresholds",value=f"```{field0_value}```")
        
        max_rec = await self.pool.fetchrow("SELECT * FROM autopunishments WHERE guild_id=$1 AND p_type='ban'",itx.guild.id)

        self.parent_msg.embeds[0].set_field_at(index=1,name="Maximum",value=await self.field_1(max_rec))
        await self.parent_msg.edit(embed=self.parent_msg.embeds[0])

        self.stop()


class AddAutocomplete(discord.ui.Modal):
    def __init__(self,pool: Connection, parent_msg: discord.Message, field_1) -> None:
        super().__init__(title="Add Autocomplete response", timeout=600)
        self.pool = pool
        self.parent_msg = parent_msg
        self.field_1 = field_1

        self.reason = discord.ui.TextInput(label="Autocomplete reason",placeholder="Suggestions for warn 'reason'",max_length=88)
        self.autocomplete_points = discord.ui.TextInput(label="Points",placeholder="The number of points for the corresponding reason.",max_length=3)
        
        self.add_item(self.autocomplete_points)
        self.add_item(self.reason)
    
    async def on_submit(self, itx: discord.Interaction, /) -> None:
        autocompletes = await self.pool.fetch("SELECT * FROM autocompletes WHERE guild_id=$1",itx.guild.id)

        try:
            tpoints = int(self.autocomplete_points.value)
            if tpoints <= 0:
                raise
        except:
            return await itx.response.send_message("Invalid number of points",ephemeral=True)

        if self.reason.value in [x['reason'] for x in autocompletes]:
            return await itx.response.send_message("Autocomplete reason has to be unique!",ephemeral=True)

        await self.pool.execute("INSERT INTO autocompletes(guild_id,points,reason) VALUES($1,$2,$3)",itx.guild.id,tpoints,self.reason.value)

        choose_color = await self.pool.fetchrow("SELECT * FROM autopunishments WHERE guild_id=$1 AND p_type='ban'",itx.guild.id)

        self.parent_msg.embeds[0].set_field_at(index=1,name="Maximum",value=await self.field_1(choose_color))
        await self.parent_msg.edit(embed=self.parent_msg.embeds[0])

        await itx.response.send_message("Done!",ephemeral=True)

    async def on_error(self, itx: discord.Interaction, error: Exception, /) -> None:
            print('Ignoring exception in command {}:'.format(itx.command), file=sys.stderr)
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

class AutocompleteDropdown(discord.ui.Select):
    def __init__(self,options:discord.SelectOption):
        super().__init__(placeholder='Select autocompletes', min_values=1,max_values=len(options), options=options,row=0)

    async def callback(self, itx: discord.Interaction):
        self.view.responses = self.values
        await itx.response.send_message(f"Alright! Now, press **Submit** to store them.",ephemeral=True)

class RemoveAutocomplete(discord.ui.View):
    def __init__(self, author: discord.User, pool: Connection, parent_msg: discord.Message, options: discord.SelectOption, field_1):
        super().__init__(timeout=300)
        self.add_item(AutocompleteDropdown(options))
        self.responses = []
        self.author = author
        self.pool = pool
        self.parent_msg = parent_msg
        self.field_1 = field_1

    async def interaction_check(self, itx: discord.Interaction, /) -> bool:
        if itx.user==self.author:
            return True
        await itx.response.send_message("You are not authorized for this interaction.",ephemeral=True)
        return False

    async def on_error(self, itx: discord.Interaction, error: Exception, item) -> None:
            print('Ignoring exception in command {}:'.format(itx.command), file=sys.stderr)
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

    @discord.ui.button(label='Submit',row=1)
    async def submit(self, itx: discord.Interaction, button: discord.ui.Button):
        if self.responses == []:
            return await itx.response.send_message("You have not selected any autocompletes to remove",ephemeral=True)
    
        await self.pool.executemany("DELETE FROM autocompletes WHERE id=$1",[(int(x),) for x in self.responses])
        
        choose_color = await self.pool.fetchrow("SELECT * FROM autopunishments WHERE guild_id=$1 AND p_type='ban'",itx.guild.id)
        self.parent_msg.embeds[0].set_field_at(index=1,name="Maximum",value=await self.field_1(choose_color))
        await self.parent_msg.edit(embed=self.parent_msg.embeds[0])

        self.stop()



