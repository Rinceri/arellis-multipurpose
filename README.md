# **Arellis bot**
![arellis only](https://user-images.githubusercontent.com/105272951/210510607-4a07dc8a-d4ef-4058-b0da-4b0d709ef2cc.png)

### A multipurpose discord bot

The bot uses [discord.py](https://github.com/Rapptz/discord.py) library, with [PostgreSQL](https://www.postgresql.org/).

[Invite it!](https://discord.com/api/oauth2/authorize?client_id=1061852563084947546&permissions=8&scope=bot%20applications.commands)

This bot is still in improvement; [join the server](https://discord.gg/gjRfPR8Rcm) to report bugs or suggest features!

## Hosting the bot on your own?

### Requirements:
Python 3.8 or higher is needed. Check your version with `python --version`

Install dependencies with `python3 -m pip install -U -r requirements.txt`

### Steps:
1. Go to [Discord developers](https://discord.com/developers/applications) site, and create a new application
2. Go to **Bot** tab and **Add bot**
3. Go to the section called "Privileged Gateway Intents" and enable the last two intents (can enable the first one as well but not required)
4. Copy the bot token. **DO NOT SHARE THIS TOKEN WITH ANYONE.**

5. Create database in postgreSQL, note the database name, username, and password
6. Create a env file called `.env` with the following format:
```
TOKEN = your_bot_token_here
DB_NAME = database_name
DB_USERNAME = db_username
DB_PASSWORD = db_password
```
6. Save it in the root directory (same level as `main.py`)

7. Go back to the developer site, go to **OAuth2 / URL Generator** tab, enable scopes `bot` and `application.commands`
8. Enable whatever permissions you want (I recommend `Administrator` for proper functioning).
9. Copy the generated URL, and use it to invite the bot.

10. Run the `main.py` file
11. Run the commands `-dbsetup` and then `-register` to setup database.
12. Run the command `-sync` to sync all slash commands.

And we're done!

## Credits
Thanks to zezo3021#6852 — bug tester
