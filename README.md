# **Arellis bot**

### A multipurpose discord bot

The bot uses [discord.py](https://github.com/Rapptz/discord.py) library, with [PostgreSQL](https://www.postgresql.org/).

[Invite it!](https://discord.com/api/oauth2/authorize?client_id=1046742411994472448&permissions=8&scope=bot%20applications.commands)

This bot is still in improvement; [join the server](https://discord.gg/gjRfPR8Rcm) to report bugs or suggest features!

## Hosting the bot on your own?

### Requirements:
- discord.py version 2.1
- Python 3.8 or higher
- asyncpg (and consequently postgreSQL)

### Steps:
1. Go to [Discord developers](https://discord.com/developers/applications) site, and create a new application
2. Go to **Bot** tab and **Add bot**
3. Go to the section called "Privileged Gateway Intents" and enable the last two intents (can enable the first one as well but not required)
4. If you have the bot token copied, paste it in the `main.py` file where `TOKEN = 'TOKEN'`. **DO NOT SHARE THIS TOKEN WITH ANYONE**

5. Create database in postgreSQL, note the database name, username, and password
6. Paste it in the `main.py` file where `DB_NAME = "name"`. `DB_USERNAME = "username"`, `DB_PASSWORD = "password"` respectively

7. Go back to the developer site, go to **OAuth2 / URL Generator** tab, enable scopes `bot` and `application.commands`
8. Enable whatever permissions you want (I recommend `Administrator` for proper functioning).
9. Copy the generated URL, and use it to invite the bot.

10. Run the `main.py` file
11. Run the commands `-dbsetup` and then `-register` to setup database.

And we're done!
