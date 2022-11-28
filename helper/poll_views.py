import discord
from asyncpg import Connection
import json
import traceback, sys

EMBED_COLOR = discord.Color.from_str("#ddb857")

class Poll(discord.ui.View):
    def __init__(self, options: int, pool: Connection):
        super().__init__(timeout = None)
        self.pool = pool
        for num in range(1, options+1):
            self.add_item(PollButton(num, pool))
        
        self.remove_item(self.result_callback)
        self.remove_item(self.poll_end_callback)
    
        self.add_item(self.result_callback)
        self.add_item(self.poll_end_callback)

    async def on_error(self, interaction: discord.Interaction, error: Exception, item, /) -> None:
        traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
    
    @discord.ui.button(label = "Results", custom_id = 'result', style = discord.ButtonStyle.green)
    async def result_callback(self, itx: discord.Interaction, button: discord.ui.Button):
        record = await self.pool.fetchrow("SELECT * FROM poll_table WHERE message_id = $1", itx.message.id)
        used_users: dict = json.loads(record['used_users'])
        
        if str(itx.user.id) not in used_users.keys():
            return await itx.response.send_message("You have not voted for any option", ephemeral = True)
        
        option_votes = record['option_votes']

        total = sum(option_votes)

        desc = '\n'.join([f'`{int((votes / total) * 100)}%` for option {option_num + 1}' for option_num, votes in enumerate(option_votes)])
        
        em = discord.Embed(color = EMBED_COLOR, title = "Results", description = desc)

        await itx.response.send_message(embed = em, ephemeral = True)
    
    @discord.ui.button(label = "End poll", custom_id = "end_poll", style = discord.ButtonStyle.gray)
    async def poll_end_callback(self, itx: discord.Interaction, button: discord.ui.Button):
        record = await self.pool.fetchrow("SELECT * FROM poll_table WHERE message_id = $1", itx.message.id)
        if itx.user.id == record['creator_id']:
            end_view = EndView()
            await itx.response.send_message("Are you sure?", view = end_view, ephemeral= True)
            await end_view.wait()

            if end_view.close:
                total = sum(record['option_votes'])
                total = total if total != 0 else 1
                body = '\n'.join([f'{option}\n`{int((votes / total) * 100)}%`' for option, votes in zip(record['poll_options'], record['option_votes'])])
                msg: discord.Message = await itx.channel.fetch_message(record['message_id'])
                em = msg.embeds[0]
                em.description = body
                await msg.edit(embed = em, view = None)
                await self.pool.execute("DELETE FROM poll_table WHERE message_id = $1", record['message_id'])
                await itx.edit_original_response(content = "Done!", view= None)
                self.stop()
        else:
            await itx.response.send_message("You are not authorized to end this interaction", ephemeral = True)

class PollButton(discord.ui.Button):
    def __init__(self, num: int, pool: Connection):
        super().__init__(label = f"Option {num}", custom_id = f"option_{num}", style = discord.ButtonStyle.blurple)
        
        self.num = num
        self.pool = pool

    async def callback(self, itx: discord.Interaction):
        record = await self.pool.fetchrow("SELECT * FROM poll_table WHERE message_id = $1", itx.message.id)

        used_users: dict = json.loads(record['used_users'])
        # {'user_id':List[option_num]}

        if str(itx.user.id) in used_users.keys():
            if not record['multi_option']:
                return await itx.response.send_message("You have already voted for this poll", ephemeral = True)

            if self.num in used_users[f'{itx.user.id}']:
                return await itx.response.send_message("You have already voted this option", ephemeral = True)
            
            used_users[f'{itx.user.id}'].append(self.num)
        
        else:
            
            used_users[f'{itx.user.id}'] = [self.num]
        
        option_votes = record["option_votes"]
        option_votes[self.num - 1] += 1
        
        await self.pool.execute("UPDATE poll_table SET option_votes = $1, used_users = $2 WHERE message_id = $3",
        option_votes, json.dumps(used_users), itx.message.id)
        
        await itx.response.send_message("Your vote has been registered!", ephemeral = True)

class EndView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout = 60)
        self.close = False

    @discord.ui.button(label = "Yes", style = discord.ButtonStyle.red)
    async def yes_button(self, itx: discord.Interaction, button: discord.ui.Button):
        self.close = True
        self.stop()

