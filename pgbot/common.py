"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present pygame-community

This file defines some constants and variables used across the whole codebase,
as well as other small helpful constructs.
"""

import asyncio
import io
import json
import os
from typing import Optional, Union

import discord
from discord.ext import commands
import pygame
import snakecore

from dotenv import load_dotenv

if os.path.isfile(".env"):
    load_dotenv()  # take environment variables from .env

# declare type alias for any channel
Channel = Union[discord.TextChannel, discord.DMChannel, discord.Thread, discord.GroupChannel]
cmd_logs = {}
_global_task_set: set[asyncio.Task] = set()  # prevents asyncio.Task objects from disappearing due
# to reference loss, not to be modified manually


def hold_task(task: asyncio.Task):
    """Store an `asyncio.Task` object in a container to place a protective reference
    on it in order to prevent its loss. The given task will be given a callback
    that automatically removes it from the container when it is done.

    Args:
        task (asyncio.Task): The task.
    """
    if task in _global_task_set:
        return

    _global_task_set.add(task)
    task.add_done_callback(_global_task_set_remove_callback)


def _global_task_set_remove_callback(task: asyncio.Task):
    if task in _global_task_set:
        _global_task_set.remove(task)

    task.remove_done_callback(_global_task_set_remove_callback)


recent_response_messages: dict[int, discord.Message] = {}

# pygame community guild, or whichever is the 'primary' guild for the bot
guild: Optional[discord.Guild] = None

# IO object to redirect output to discord, gets patched later
stdout: Optional[io.StringIO] = None

log_channel: discord.TextChannel
arrivals_channel: discord.TextChannel
roles_channel: discord.TextChannel
guide_channel: discord.TextChannel
entries_discussion_channel: discord.TextChannel
console_channel: discord.TextChannel
db_channel: discord.TextChannel
rules_channel: discord.TextChannel
entry_channels = {}
entry_message_deletion_dict = {}

__version__ = "1.5.3"

TEST_MODE = "TEST_TOKEN" in os.environ
TOKEN = os.environ["TEST_TOKEN" if TEST_MODE else "TOKEN"]

TEST_USER_ID = int(os.environ["TEST_USER_ID"]) if "TEST_USER_ID" in os.environ else None

TEST_USER_IDS = (
    set(int(user_id) for user_id in os.environ["TEST_USER_IDS"].split()) if "TEST_USER_IDS" in os.environ else set()
)

if TEST_USER_ID is not None:
    TEST_USER_IDS.add(TEST_USER_ID)


COMMAND_PREFIX = "pd!" if TEST_MODE else "pg!"

DEFAULT_FILESIZE_LIMIT = 8_000_000  # bytes

DEFAULT_EMBED_COLOR = 0xFFFFAA
DOC_EMBED_LIMIT = 3
BROWSE_MESSAGE_LIMIT = 500

# indicates whether the bot is in generic mode or not. Generic mode is useful
# when you are testing the bot on other servers. Generic mode limits features of
# the bot that requires access to server specific stuff
GENERIC = False

# For commonly used variables
ints = discord.Intents.default()
ints.members = True  # needed for on_member_join
ints.message_content = True  # needed for message content
bot = snakecore.command_handler.Bot(
    command_prefix=commands.when_mentioned_or("pd!" if TEST_MODE else "pg!"),
    intents=ints,
    help_command=None,
)
pygame_display = pygame.Surface((1, 1))  # This will later be redefined


class GuildConstants:
    """
    Namespace class of all primary guild constants.  By default, this class namespace contains constants
    used by the main PygameCommunityBot instance in the 'Pygame Community' Discord server.
    If you ever want to make a copy of the bot run on your own server on non-generic mode, replicate this class, but
    with the constants from your server.
    """

    BOT_ID = 772788653326860288

    GUILD_ID = 772505616680878080

    RULES_CHANNEL_ID = 772509621747187712
    ROLES_CHANNEL_ID = 772535163195228200
    GUIDE_CHANNEL_ID = 772528306615615500
    ARRIVALS_CHANNEL_ID = 774916117881159681
    LOG_CHANNEL_ID = 793250875471822930
    CONSOLE_CHANNEL_ID = 851123656880816138
    ENTRY_CHANNEL_IDS = {
        "showcase": 772507247540437032,
        "discussion": 780351772514058291,
    }
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

    # Database channel
    DB_CHANNEL_ID = 838090567682490458

    # remember to maintain the scores here in descending order
    WC_ROLES = (
        (42, 889170053013061683),  # Legendary Guardian
        (30, 889169676398100480),  # Elite Guardian
        (15, 889169351645749311),  # Guardian
        (1, 889168765479178240),  # Apprentice
    )

    WC_SCORING = (
        ("Legendary Guardian ⚜️💫", 42),
        ("Elite Guardian ⚜️", 30),
        ("Guardian ⚜️", 15),
        ("Apprentice ⚜️", 1),
    )

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


ILLEGAL_EXEC_ATTRIBUTES = (
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

BOT_HELP_DIALOG_FSTRING = """
Hey there, do you want to use {0} ?
My command prefix is `{1}`.
If you want me to run your code, use Discord's code block syntax.
If you want to know about a specifc command run `{1}help [command]`.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""
