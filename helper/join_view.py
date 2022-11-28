import discord
from random import randint

class VerifyMessageView(discord.ui.View):
    def __init__(self, pool):
        super().__init__(timeout = None)
        self.pool = pool
    
    async def interaction_check(self, itx: discord.Interaction, /) -> bool:
        verify_role = await self.pool.fetchval("SELECT verify_role FROM join_stats WHERE guild_id = $1", itx.guild_id)
        role = itx.guild.get_role(verify_role) if verify_role is not None else None

        if role is None or role > itx.guild.me.roles[-1]:
            await itx.response.send_message("Role for verification is inaccesible", ephemeral = True)
            return False
        
        if role in itx.user.roles:
            return True
        
        await itx.response.send_message(f"You need the {role.mention} role for verification.", ephemeral = True)
        return False

    @discord.ui.button(label = 'Verify here', custom_id = 'verify_here', style = discord.ButtonStyle.green)
    async def verify_here(self, itx: discord.Interaction, button: discord.ui.Button):
        role_ids = await self.pool.fetchrow("SELECT verify_role, join_role_u FROM join_stats WHERE guild_id = $1", itx.guild_id)
        vrole = itx.guild.get_role(role_ids['verify_role'])
        jrole = itx.guild.get_role(role_ids['join_role_u']) if role_ids['join_role_u'] is not None else None

        num = randint(1000, 9999)
        await itx.response.send_modal(VerifyCodeModal(vrole, jrole, str(num)))

class VerifyCodeModal(discord.ui.Modal):
    def __init__(self, vrole: discord.Role, jrole: discord.Role | None, num: str) -> None:
        self.vrole = vrole
        self.jrole = jrole
        self.num = num
        super().__init__(title = f"Enter code: {self.num}", timeout = 60, custom_id = 'verify_modal')

        self.code_inp = discord.ui.TextInput(label = "Enter here", min_length = len(self.num), max_length = len(self.num))
        self.add_item(self.code_inp)

    async def on_submit(self, itx: discord.Interaction, /) -> None:
        if self.code_inp.value != self.num:
            return await itx.response.send_message("Wrong code entered. Verification failed.", ephemeral = True)
        
        await itx.user.remove_roles(self.vrole, reason = "Verification complete")
        
        if self.jrole is not None: 
            await itx.user.add_roles(self.jrole, reason = "User join role")

        await itx.response.send_message("Verified.", ephemeral = True)