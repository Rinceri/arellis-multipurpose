import discord
from random import choices
import string
from captcha.image import ImageCaptcha

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

        code = ''.join(choices(string.ascii_uppercase + string.digits, k = 5))
        image = ImageCaptcha()

        image_bytes = image.generate(code)

        view = VerifyModalView(vrole = vrole, jrole = jrole, code = code)
        await itx.response.send_message("**Enter the code given in the image below**", 
        file = discord.File(image_bytes, "v_code.png"), ephemeral = True, view = view)

        view.msg = await itx.original_response()

class VerifyModalView(discord.ui.View):
    def __init__(self, *, vrole, jrole, code):
        super().__init__(timeout = 80)
        self.vrole = vrole
        self.jrole = jrole
        self.code = code
    
    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        try:
            await self.msg.edit(view = self)
        except:
            pass
    
    @discord.ui.button(label = "Enter code", style = discord.ButtonStyle.green)
    async def verify_modal_callback(self, itx: discord.Interaction, button: discord.ui.Button):
        await itx.response.send_modal(VerifyCodeModal(self.vrole, self.jrole, self.code, self.msg))

class VerifyCodeModal(discord.ui.Modal):
    def __init__(self, vrole: discord.Role, jrole: discord.Role | None, code: str, msg) -> None:
        self.vrole = vrole
        self.jrole = jrole
        self.code = code
        self.msg = msg
        super().__init__(title = f"Enter code given in image", timeout = 60, custom_id = 'verify_modal')

        self.code_inp = discord.ui.TextInput(label = "Enter here", min_length = len(self.code), max_length = len(self.code))
        self.add_item(self.code_inp)

    async def on_submit(self, itx: discord.Interaction, /) -> None:
        if self.code_inp.value.upper() != self.code:
            await itx.response.send_message("Wrong code entered. Verification failed.", ephemeral = True)
        else:
            await itx.user.remove_roles(self.vrole, reason = "Verification complete")
        
            if self.jrole is not None: 
                await itx.user.add_roles(self.jrole, reason = "User join role")

            await itx.response.send_message("Verified.", ephemeral = True)
        try:
            await self.msg.delete()
        except:
            pass
        
        self.stop()
