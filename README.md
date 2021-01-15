# PygameCommunityBot
The [Pygame Community Discord](https://discord.gg/kD2Qq9tbKm) bot

## User commands
- `pg!doc {module.submodule.class.method}` gives the documentation docstring from the specified module, submodule, class, function or method.
- `pg!exec {code}` executes the code argument (The code must be inside a code block, otherwise it won't work).
- `pg!clock` sends a 24 hour clock which shows the current time for listed users.
- `pg!pet` pets the snek.
- `pg!vibecheck` too much petting? Check if snek is **angery**.

#### Sandbox specifications
- The sandbox has a timeout timer for executed code of 2 seconds for normal users and 5 seconds for privileged users.
- The sandbox automatically shut off if the bot's total memory usage is over 268435456 bytes, by default.
- Imports and specific built-in functions are removed. Several modules are pre-imported, such as: `pygame` `math` `cmath` `random` `re` `time` `timeit` `string` `itertools`.
- To output something, there's `output.text` which gives the text output (The `print` is re-implemented which concatenates the the `value` argument to `output.text` plus the specified `sep` and `end` arguments) as a `str` and `output.img` which gives the image output as a `pygame.Surface`.

## Admin commands
- `pg!eval {code}` evaluate a one line code (The code shouldn't be inside a code block) without any container/limitation, helpful for debugging.
- `pg!sudo {message}` speaks back the message as if the bot's the one who's talking.
- `pg!emsudo {hex}, {title}, {body}, [image_url]` `pg!emsudo {title}, {body}` sends an embed back with the arguments such as the hex color, title, and the body content.
- `pg!sudo-edit {message_id} {message}` edits a message that was sent from the bot by the message ID.
- `pg!emsudo-edit {message_id}, {hex}, {title}, {body}, [image_url]` `pg!emsudo-edit {message_id}, {title}, {body}` edits the embed of a message that was sent from the bot by the message ID.
- `pg!heap` returns the application's total memory usage.
- `pg!stop` stops the bot.


## Setting up the bot
This is a guide on how to set up this bot for your own server, we appreciate it if you credit us and link the discord server!
- Make a discord bot application [here](https://discord.com/developers/applications)
- Make sure you have python installed, and install these dependencies: `discord.py`, `pygame`, and `psutil`
- Create a `token.txt` file containing your bot application's token
- Now, you need to modify the attributes of the bot

## Modifying the bot
To modify attributes about the bot, you can edit `constants.py`
- `LOG_CHANNEL`, put the channel ID of your specified log channel where it sends the invoked commands ran by users
- `BLOCKLIST_CHANNEL`, put the channel ID of the channel that you would fill up with user IDs that'll be blocked from using the bot
- `ADMIN_ROLES`, put the admin roles' ID that could invoke admin commands
- `ADMIN_USERS`, put the admin users' ID that could invoke admin commands
- `PRIV_ROLES`, put the priviledged roles' ID that could invoke user commands with additional features
- `COMPETENCE_ROLES` `PYGAME_CHANNELS`,  these are [Pygame Community Discord](https://discord.gg/kD2Qq9tbKm) specific things, you can leave these ones empty
- `CLOCK_TIMEZONES`, put the list of timezones and names the clock would display `(GMT_OFFSET_SECONDS, NAME, RGB_COLOR)`
