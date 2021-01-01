# PygameCommunityBot
The unofficial [Pygame Community Discord](https://discord.gg/kD2Qq9tbKm) bot

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
- `pg!emsudo {hex}, {title}, {body}` `pg!emsudo {title}, {body}` sends an embed back with the arguments such as the hex color, title, and the body content.
- `pg!heap` returns the application's total memory usage.
- `pg!stop` stops the bot.
