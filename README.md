# PygameCommunityBot

The [Pygame Community Discord](https://discord.gg/kD2Qq9tbKm) bot

The bot is capable of doing a lot of stuff, the command prefix is `pg!`.
For help on all the bot commands, run `pg!help`.

The bot is licensed under the [MIT license](LICENSE).

## Contributing

- Check out the guide at [CONTRIBUTING.md](docs/CONTRIBUTING.md)

## Setting up the bot on test mode

- When you get the 'sorcerer' role on the discord server, you will be given the token of  the test bot.
- You can then run the bot locally on your local setup to test the bot.
- Make sure you have python 3.9 or above, install the deps with `pip install -r requirements.txt`

- Make a `.env` file at the base dir (this is git-ignored), and set it like

```py
TEST_TOKEN = "bot token goes here"
TEST_USER_ID = 1234567890 # your discord ID
```

- Run the `main.py` file, and you should see a dev version of the bot fire up

## Running the bot on your server

- In addition to the above steps, if you want to get the bot started on your own server, you'd need to make some code changes, in the `common.py` file, you would either need to set the bot on "generic" mode, where the server specific features are disabled, or alternatively, rewrite `GuildConstants` class, but with the constants from your server. Don't forget to revert these changes when you send us a PR!
