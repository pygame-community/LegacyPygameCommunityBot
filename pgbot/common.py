"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file defines some constants and variables used across the whole codebase
"""

import io
import os
from typing import Optional, Union

import discord
import pygame

from dotenv import load_dotenv

if os.path.isfile(".env"):
    load_dotenv()  # take environment variables from .env

# declare type alias for any channel
Channel = Union[discord.TextChannel, discord.DMChannel, discord.GroupChannel]

# For commonly used variables
ints = discord.Intents.default()
ints.members = True  # needed for on_member_join
bot = discord.Client(intents=ints)
window = pygame.Surface((1, 1))  # This will later be redefined

cmd_logs = {}

# pygame community guild, or whichever is the 'primary' guild for the bot
guild: Optional[discord.Guild] = None

# IO object to redirect output to discord, gets patched later
stdout: Optional[io.StringIO] = None

# Tuple containing all admin commands, gets monkey-patched later
admin_commands = ()

log_channel: discord.TextChannel
arrivals_channel: discord.TextChannel
roles_channel: discord.TextChannel
guide_channel: discord.TextChannel
entries_discussion_channel: discord.TextChannel
console_channel: discord.TextChannel
db_channel: discord.TextChannel
rules_channel: discord.TextChannel
entry_channels = {}

__version__ = "1.5.3"

# BONCC quiky stuff
BONK = "<:pg_bonk:780423317718302781>"
PG_ANGRY_AN = "<a:pg_snake_angry_an:779775305224159232>"

TEST_MODE = "TEST_TOKEN" in os.environ
TOKEN = os.environ["TEST_TOKEN" if TEST_MODE else "TOKEN"]

TEST_USER_ID = int(os.environ["TEST_USER_ID"]) if "TEST_USER_ID" in os.environ else None

TEST_USER_IDS = (
    set(int(user_id) for user_id in os.environ["TEST_USER_IDS"].split())
    if "TEST_USER_IDS" in os.environ
    else set()
)

if TEST_USER_ID is not None:
    TEST_USER_IDS.add(TEST_USER_ID)


PREFIX = "pd!" if TEST_MODE else "pg!"
CMD_FUNC_PREFIX = "cmd_"

BASIC_MAX_FILE_SIZE = 8_000_000  # bytes

ZERO_SPACE = "\u200b"  # U+200B

DOC_EMBED_LIMIT = 3
BROWSE_MESSAGE_LIMIT = 500

# indicates whether the bot is in generic mode or not. Generic mode is useful
# when you are testing the bot on other servers. Generic mode limits features of
# the bot that requires access to server specific stuff
GENERIC = False

UNIQUE_POLL_MSG = "You cannot make multiple votes in this poll\n"


class ServerConstants:
    """
    Class of all server constants. If you ever want to make a copy of the bot
    run on your own server on non-generic mode, replicate this class, but
    with the constants from your server
    """

    BOT_ID = 772788653326860288

    SERVER_ID = 772505616680878080

    RULES_CHANNEL_ID = 772509621747187712
    ROLES_CHANNEL_ID = 772535163195228200
    GUIDE_CHANNEL_ID = 772528306615615500
    ARRIVALS_CHANNEL_ID = 774916117881159681
    LOG_CHANNEL_ID = 793250875471822930
    CONSOLE_CHANNEL_ID = 851123656880816138
    ENTRY_CHANNEL_IDS = {
        "showcase": 772507247540437032,
        "resource": 810516093273768016,
    }
    ENTRIES_DISCUSSION_CHANNEL_ID = 780351772514058291

    # eval is a pretty dangerous command, so grant it only for Admins and Senior Mages
    EVAL_ROLES = {772521884373614603, 772849669591400501}

    # Admin, Moderator, Senior Mage, Wizards, Lead Forgers
    ADMIN_ROLES = {
        772521884373614603,
        772508687256125440,
        772849669591400501,
        841338117968756766,
        839869589343961099,
    }

    # Specialties, Helpfulies, Verified pygame contributors, Server Boosters
    PRIV_ROLES = {
        774473681325785098,
        778205389942030377,
        780440736457031702,
        787473199088533504,
    }

    DIVIDER_ROLES = {836645525372665887, 836645368744771654, 842754237774692392}

    # IDs of rules messages, in the order from rule 1 to rule 7
    RULES = (
        799339450361577472,
        799339479445405746,
        799339501511639100,
        799339582620827680,
        799339603651067974,
        799339620810358885,
        819537779847200809,
    )
    
    # Data from https://developer.mozilla.org/en-US/docs/Web/HTTP/Status
    HTTP_RULES = {
        100: "Continue...",
        200: "OK :+1:",
        204: "?",
        301: "Rule moved permanently!",
        302: "Rule found!",
        303: "See other rules!",
        304: "Rule is still the same!",
        400: "I Don't understand!",
        401: "You must login to Discord to see this rule",
        402: "Support PyGame Community Server on Patreon",
        403: "Only for specific users!",
        404: "Not found",
        409: "Oops, I have some problems, taking timeout",
        410: "This rule has been deleted",
        413: "This rule is too big to be displayed",
        418: "Drink a tea",
        429: "Relax a bit",
        451: "FBI, open up",
        500: "I have some problems right now, sorry :sweat:",
        501: "This rule is still undecided",
        505: "Update PyGame to version 2.1",
        507: "Download more HDD",
        508: "Write pg!rules 508",
    }

    # NOTE: It is hardcoded in the bot to remove some messages in resource-entries,
    #       if you want to remove more, add the ID to the set below
    MSGS_TO_FILTER = {
        817137523905527889,
        810942002114986045,
        810942043488256060,
    }

    # Database channel
    DB_CHANNEL_ID = 838090567682490458


# Link to pygame snake logo
GUILD_ICON = "https://media.discordapp.net/attachments/793272780987826197/836600713672523826/Discord_Server_Animated_Logo_V5_512x512.gif"

BOT_WELCOME_MSG = {
    "greet": (
        "Hi",
        "Hello",
        "Welcome to **Pygame Community**",
        "Greetings",
        "Howdy",
        "Hi there, ",
        "Hey there",
        "*Hiss* Who's that? It's",
        "*Hiss* Welcome",
        "Hello there,",
        "Ooooh! Hello",
        "Hi there,",
        "*Hiss* Do I see a new user? *hiss*\n" + "Welcome to our wonderful chatroom",
        "Ooooh! It's",
        "Oooh! Look who has joined us, it's",
    ),
    "check": (
        "Check out our",
        "Make sure to check out the",
        "Take a look at our",
        "See our",
        "Please see our",
        "Be sure to read our",
        "Be sure to check the",
        "Be sure to check out our",
        "Read our",
        "Have a look at our",
        "To get started here, please read the",
    ),
    "grab": (
        ", grab",
        ". Then get some",
        ", take",
        ", then grab yourself some shiny",
        ". Get some fancy",
        ", get some",
        ", then get yourself some cool",
        ", then get yourself some",
        ", take some",
        ", then take some",
        ", then take some",
        ". Go get some cool roles at",
        ". Then go take some fancy",
        ", then grab some shiny",
    ),
    "end": (
        " and have fun!",
        ", then have fun with pygame!",
        ", then have fun with pygame! *hiss*",
        " and have a nice time!",
        " and enjoy your stay!",
        " and have some fun! *hisss*",
        " and have fun here!",
        " and have fun with pygame!",
        " and have a wonderful time!",
        " and join us!",
        " and join the fun!",
        " and have fun with pygame! *hisss*",
        " and have fun here! *hisss*",
    ),
}

ILLEGAL_ATTRIBUTES = (
    "__subclasses__",
    "__loader__",
    "__bases__",
    "__code__",
    "__getattribute__",
    "__setattr__",
    "__delattr_",
    "mro",
    "__class__",
    "__dict__",
)

DEAD_CHAT_TRIGGERS = {
    "the chat is dead",
    "the chat is ded",
    "this chat is dead",
    "this is a ded chat",
    "this is a dead chat",
    "chat dead",
    "chat ded",
    "chatded",
    "chatdead",
    "dead chat",
    "ded chat",
    "dedchat",
    "this chat ded",
    "this chat dead",
}

BOT_MENTION = "the bot" if GENERIC else f"<@!{ServerConstants.BOT_ID}>"

BOT_HELP_PROMPT = {
    "title": "Help",
    "color": 0xFFFF00,
    "description": f"""
Hey there, do you want to use {BOT_MENTION} ?
My command prefix is `{PREFIX}`.
If you want me to run your code, use Discord's code block syntax.
Learn more about Discord code formatting **[HERE](https://discord.com/channels/772505616680878080/774217896971730974/785510505728311306)**.
If you want to know about a specifc command run {PREFIX}help [command], for example {PREFIX}help exec.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━""",
}

BYDARIO_QUOTE = """
> Yea, if is dead bring it back to life or let it rest in peace
> When you are death ppl dont go to your tomb and say: dead person
> I know because I am dead and noone comes to visit me
<@!691691416799150152>
"""

SHAKESPEARE_QUOTES = (
    """
To be, or not to be, that is the question
— SHAKESPEARE, _Hamlet_, Act 3 Scene 1, lines 56-83; Hamlet
""",
    """
All the world's a stage,
And all the men and women merely players
— SHAKESPEARE, _As You Like It_, Act 2 Scene 7, lines 139-40; Jacques to Duke Senior and his companions
""",
    """
We are such stuff
As dreams are made on;
and our little life
Is rounded with a sleep
— SHAKESPEARE, _The Tempest_, Act 4 Scene 1, lines 156-58; Prospero to Miranda and Ferdinand
""",
    """
Out, out brief candle!
Life's but a walking shadow, a poor player,
That struts and frets his hour upon the stage.
— SHAKESPEARE, _Macbeth_, Act 5 Scene 5, Lines 23-25; Macbeth to Seyton
""",
    """
Be not afraid of greatness. Some are born great, some achieve greatness, and some have greatness thrust upon 'em.
— SHAKESPEARE, _Twelfth Night_, Act 2 Scene 5, Lines 139-41; Malvolio
""",
    """
When we are born we cry that we are come
To this great stage of fools
— SHAKESPEARE, _King Lear_, Act 4 Scene 6, lines 178-79; King Lear to Gloucester
""",
    """
The web of our life is of a mingled yarn, good and ill together
— SHAKESPEARE, _All's Well That Ends Well_, Act 4 Scene 3, lines 68-69; One lord to another
""",
    """
You cannot, sir, take from me anything that I will not more willingly part withal - except my life, except my life, except my life
— SHAKESPEARE, _Hamlet_, Act 2 Scene 2, lines 213-17; Hamlet
""",
)
