import os
TOKEN = os.environ.get("TOKEN", "")
PREFIX = "pg!"

VERSION = "1.2.0"

LOG_CHANNEL = 793250875471822930
BLOCKLIST_CHANNEL = 793269297954422804

BOT_ID = 772788653326860288

# Pet command constants
PET_COST = 0.1
JUMPSCARE_THRESHOLD = 20.0
PET_INTERVAL = 60.0

# BONCC quiky stuff
BONK = "<:pg_bonk:780423317718302781>"
PG_ANGRY_AN = "<a:pg_snake_angry_an:779775305224159232>"
SORRY_CHANCE = 0.5
BONCC_THRESHOLD = 10
BONCC_PARDON = 3

# PGC Admin, PGC Moderator, PGC Wizards
ADMIN_ROLES = {
    772521884373614603,
    772508687256125440,
    772849669591400501,
}

# PGC Specialties, PGC Helpfulies
PRIV_ROLES = {774473681325785098, 778205389942030377}

MUTED_ROLE = 772534687302156301

# AvaxarXapaxa, BaconInvader, MegaJC, Ankith
ADMIN_USERS = {
    414330602930700288,
    265154376409153537,
    444116866944991236,
    763015391710281729
}

# PGC pygame beginner, PGC pygame regular, PGC pygame pro, PGC pygame contributor
COMPETENCE_ROLES = {
    772536799926157312,
    772536976262823947,
    772537033078997002,
    772537232594698271,
}

# PGC #pygame, #beginners-help
PYGAME_CHANNELS = {772507303781859348, 772816508015083552}

# String Constants
ESC_CODE_BLOCK_QUOTE = "\u200e`\u200e`\u200e`\u200e"

EXP_TITLES = [
    'An exception occurred while trying to execute the command:',
    'An exception occured:',
]

ROLE_PROMPT = {
    "title": [
        "Get more roles",
        "You need more roles for this channel (It's written everywhere!)",
        "I won't stop until you get more roles"
    ],

    "message": [
        "Hey there {0}, are you a @ Pygame Newbie, @ Pygame Regular or a @ Pygame Pro, or even a @ Pygame Contributor?\n" +\
        "Tell <@!235148962103951360> in <#772535163195228200>!",       
    ]
}


INCLUDE_FUNCTIONS = """
def print(*values, sep=" ", end="\\n"):
    global output
    output.text = str(output.text)
    output.text += sep.join(map(str, values)) + end
"""

CLOCK_TIMEZONES = [
    (3600 * -4, 'Ghast', (176, 111, 90)),
    (0, 'BaconInvader', (123, 196, 63)),
    (3600, 'MegaJC', (229, 25, 247)),
    (3600, 'bydariogamer', (229, 25, 247)),
    (3600, 'zoldalma', (229, 25, 247)),
    (3600 * 2, 'CozyFractal', (255, 28, 28)),
    (3600 * 3, 'k4dir', (66, 135, 245)),
    (3600 * 5.5, 'Ankith', (240, 140, 0)),
    (3600 * 7, 'Avaxar', (64, 255, 192)),
]


BOT_HELP_PROMPT = {
    "title": [
        "Help",
    ],

    "message": ["""
Hey there, do you want to use <@772788653326860288> ?
My command prefix is `pg`.

**Get Help**
```
!help
!doc
!clock
```
**Run Code**
```
!exec
```

**Play With Me :snake:**
```
!pet
!vibecheck
!sorry
!boncccheck
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
__**Get Help:**__
`pg!help` - Ask me for help

`pg!doc {module.Class.method}` - Look up the docstring of a Python/Pygame object, e.g `builtins.string` or `pygame.Rect`

`pg!clock` - 24 Hour Clock showing @ Helpfulie ☉ 's who are available to help

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
__**Run Code:**__
`pg!exec {python code block}` - Run python code in an isolated environment. `import` is not available. Various methods of builtin objects have been disabled for security reasons. The available preimported modules are: `math, cmath, random, re, time, string, itertools, pygame`.

If you want me to run your code, use Discord's code block syntax.
Learn more about Discord code formatting [**here.**](https://discord.com/channels/772505616680878080/774217896971730974/785510505728311306)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
__**Play With Me :snake: :**__
`pg!pet` - Pet me :3 . Don't pet me too much or I will get mad.

`pg!vibecheck` - Check my mood.

`pg!sorry` - You were hitting me, "<:pg_bonk:780423317718302781>" and you're now trying to apologize? Let's see what I'll say :unamused:

`pg!boncccheck` -  Check how many times you have done me harm.
    """],

    "color": [0xFF00FF]
}
