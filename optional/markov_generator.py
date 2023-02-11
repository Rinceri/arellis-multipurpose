import discord
from discord.ext import commands
from random import choice
import asyncio
from re import sub
from discord.ext.commands.cooldowns import BucketType

# NOTE: THIS IS JUST SOME NOTES THAT I JOTTED WHILE TRYING TO UNDERSTAND HOW TO MAKE THE MARKOV CHAIN SENTENCE GENERATOR

"""
HOW CORPUS SENTENCES CAN LOOK LIKE:
"<s>Hey guys how is it going?</s>"
"<s>hey dude, you doing good></s>
"<s>yo guys? are you there !?</s>"
"<s>bruh</s>"
"<s>bro really said 'you suck'</s>"

HOW STORED TRIGRAMS WILL LOOK LIKE (EXAMPLES):
"<s>Hey guys how"
"guys how is"
"is it going?</s>"
"<s>Hey dude, you"
"dude, you doing"
"you doing good></s>"
"<s>yo guys? are"
"guys? are you"
"are you there!?</s>"
"<s>bruh</s>"
... "said 'you suck'</s>"

SO HOW IT WILL BE MADE:
# REMOVE LEADING, TRAILING SPACES OR \n, EXTRA SPACES (1+) OR \n (1+), SPACES BEFORE SPECIAL CHARACTERS ONLY
# ADD <s> AT START, </s> AT END
# SPLIT SENTENCE BY ' '
# ADD IT TO CORPUS TRIGRAM ARRAY, AND STORE IN DATABASE

DEFINITION OF ALGORITHM:
# WE RANDOMLY PICK OUR FIRST N-GRAM, WHICH STARTS WITH <s> (for example '<s>bruh</s>' OR '<s>Hey guys how' OR '<s>Hey guys</s>')
# IF TRAILING </s>, DISPLAY SENTENCE WITHOUT THE <s></s>
# ELSE, BEGIN LOOP UNTIL CHARS >= 2000 OR </s> REACHED
# PICK NEW WORD BASED ON SECOND-LAST AND LAST WORD
# DISPLAY SENTENCE

TABLE
.-----------------------------------------------------------------------.
|  guild_id [BIGINT]  |  channel_id [BIGINT]  |  trigrams [ARRAY TEXT]  |
:                     :                       :                         :

"""

class MarkovGenerator(commands.Cog, name = "markov"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_check(self, ctx: commands.Context) -> bool:
        """
        Checks whether command is DM-executed / disabled / executed in a blacklisted channel
        """

        if ctx.channel.type == discord.ChannelType.private:
            return False

        b_c = await self.bot.pool.fetchval("SELECT blacklisted_channels FROM guild_table WHERE guild_id = $1", ctx.guild.id)

        if b_c is not None and ctx.channel.id in b_c:
            return False
        return True

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author == self.bot.user:
            return

        prefix = await self.bot.pool.fetchval("SELECT prefix FROM guild_table WHERE guild_id = $1", message.guild.id)
        if prefix is None:
            prefix = '-'

        if message.content.startswith((prefix, self.bot.user.mention)):
            return
        
        try:
            data = await self.bot.pool.fetchrow("SELECT * FROM markov_table WHERE guild_id = $1", message.guild.id)
            if data['channel_id'] != message.channel.id:
                return
        except:
            return

        def trigram_maker(content: str):
            new_content = sub(r"\s([?.!,'](?:\s|$))", r'\1', content.strip().replace('\n','. ').lower())
            new_content = '<s>' + new_content + '</s>'
            word_list = new_content.split()
            trigram_list = []
            counter = 0

            for idx, word in enumerate(word_list):
                if idx + 1 == len(word_list) or idx + 2 == len(word_list):
                    if counter == 0:
                        trigram_list = [' '.join(word_list)]
                    break
                counter = 1
                trigram = word + ' ' + word_list[idx + 1] + ' ' + word_list[idx + 2]
                trigram_list.append(trigram)
            return trigram_list

        trigram_list = await asyncio.to_thread(trigram_maker, message.content)
        
        full_list = data['trigrams'] + trigram_list
        
        await self.bot.pool.execute("UPDATE markov_table SET trigrams = $1 WHERE guild_id = $2", full_list, message.guild.id)


    @commands.cooldown(rate = 1, per = 30, type = BucketType.user)
    @commands.hybrid_command(name = "generate", description = "Generate one or more sentences based on the Markov model and N-Grams.")
    async def generate(self, ctx: commands.Context):
        if ctx.interaction:
            await ctx.interaction.response.defer(thinking = True)
        
        data = await self.bot.pool.fetchrow("SELECT * FROM markov_table WHERE guild_id = $1", ctx.guild.id)

        if data is None:
            return await ctx.send("I cannot generate a sentence unless you have registered me here! Use `/set generation`", delete_after = 5)
        elif data['trigrams'] == []:
            return await ctx.send("Not enough data to generate a sentence!", delete_after = 5)
        
        # MARKOV CHAIN SENTENCE GENERATOR:
        def markov_generator(trigram_corpus: list[str]):
            sentence = choice([x for x in trigram_corpus if x.startswith('<s>')])

            while not sentence.endswith('</s>') and len(sentence) < 2000:
                second_n_third_word = ' '.join(sentence.split(' ')[-2:])
                new_word = choice([x for x in trigram_corpus if x.startswith(second_n_third_word+' ')])
                sentence += ' ' + new_word.split()[2]

            return sentence.replace('<s>','').replace('</s>','')

        sentence = await asyncio.to_thread(markov_generator, data['trigrams'])

        await ctx.send(discord.utils.escape_mentions(sentence))

    @commands.has_guild_permissions(administrator = True)
    @commands.cooldown(rate = 1, per = 5, type = BucketType.member)
    @commands.hybrid_command(name = "generation", description = "Setup the markov chain text generator", aliases = ['markov'])
    async def setup_generator(self, ctx: commands.Context, channel: discord.TextChannel):
        if channel.guild != ctx.guild:
            return await ctx.send("Channel does not exist in this server")
        
        if await self.bot.pool.fetchval("SELECT EXISTS (SELECT 1 FROM markov_table WHERE guild_id = $1)", ctx.guild.id):
            await self.bot.pool.execute("UPDATE markov_table SET channel_id = $1 WHERE guild_id = $2", channel.id, ctx.guild.id)
        else:
            await self.bot.pool.execute("INSERT INTO markov_table (guild_id, channel_id) VALUES ($1, $2)", ctx.guild.id, channel.id)

        await ctx.send("Done!")

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MarkovGenerator(bot))