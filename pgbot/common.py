"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present pygame-community

This file defines some constants and variables used across the whole codebase,
as well as other small helpful constructs.
"""

import asyncio
import datetime
import io
import json
import os
import re
import sys
from typing import Optional, TypedDict, Union
from typing_extensions import NotRequired

import discord
from discord.ext import commands
import pygame
import snakecore

from dotenv import load_dotenv

if os.path.isfile(".env"):
    load_dotenv()  # take environment variables from .env

# declare type alias for any channel
Channel = Union[
    discord.TextChannel, discord.DMChannel, discord.Thread, discord.GroupChannel
]
cmd_logs = {}
_global_task_set: set[
    asyncio.Task
] = set()  # prevents asyncio.Task objects from disappearing due
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

old_stdout = sys.stdout
old_stderr = sys.stderr

log_channel: discord.TextChannel
arrivals_channel: discord.TextChannel
roles_channel: discord.TextChannel
guide_channel: discord.TextChannel
entries_discussion_channel: discord.TextChannel
console_channel: discord.TextChannel
storage_channel: discord.TextChannel
rules_channel: discord.TextChannel
entry_channels = {}
entry_message_deletion_dict = {}


class BadHelpThreadData(TypedDict):
    thread_id: int
    last_cautioned_ts: int
    alert_message_ids: set[int]


class InactiveHelpThreadData(TypedDict):
    thread_id: int
    last_active_ts: float
    alert_message_id: NotRequired[int]


bad_help_thread_data: dict[int, BadHelpThreadData] = {}
inactive_help_thread_data: dict[int, InactiveHelpThreadData] = {}


CAUTION_WHILE_MESSAGING_COOLDOWN: int = 900
THREAD_TITLE_TOO_SHORT_SLOWMODE_DELAY: int = 300
THREAD_TITLE_MINIMUM_LENGTH: int = 20

UPVOTE_THREADS = {1026850063013658715: "⬆️"}

__version__ = "1.6.1"
# boolean guard to prevent double-initialization
pgbot_initialized: bool = False

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


COMMAND_PREFIX = "pd!" if TEST_MODE else "pg!"

DEFAULT_FILESIZE_LIMIT = 8_000_000  # bytes

DEFAULT_EMBED_COLOR = 0xFFFFAA
DOC_EMBED_LIMIT = 3
BROWSE_MESSAGE_LIMIT = 500
FORUM_THREAD_TAG_LIMIT = 5

# indicates whether the bot is in generic mode or not. Generic mode is useful
# when you are testing the bot on other servers. Generic mode limits features of
# the bot that requires access to server specific stuff
GENERIC = False

# For commonly used variables
ints = discord.Intents.default()
ints.members = True  # needed for on_member_join
ints.message_content = True  # needed for message content
bot = snakecore.commands.Bot(
    command_prefix=commands.when_mentioned_or(COMMAND_PREFIX),
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
    HELP_FORUM_CHANNEL_IDS = {
        "newbies": 1022292223708110929,  # newbies-help-🔰
        "regulars": 1019741232810954842,  # regulars-pygame-help
        "python": 1022244052088934461,  # python-help
    }

    INVALID_HELP_THREAD_TITLE_TYPES = {
        "thread_title_too_short",
        "member_asking_for_help",
        "member_exclaiming_about_not_working_code",
        "member_asking_for_code",
        "member_asking_about_problem_with_code",
    }

    INVALID_HELP_THREAD_TITLE_SCANNING_ENABLED = {
        "thread_title_too_short": True,
        "member_asking_for_help": True,
        "member_exclaiming_about_not_working_code": True,
        "member_asking_for_code": True,
        "member_asking_about_problem_with_code": True,
    }
    INVALID_HELP_THREAD_TITLE_REGEX_PATTERNS = {
        "thread_title_too_short": re.compile(
            r"^(.){1," f"{THREAD_TITLE_MINIMUM_LENGTH-1}" r"}$", flags=re.IGNORECASE
        ),
        "member_asking_for_help": re.compile(
            r"[\s]*(^help\s*|help\?*?$|(can|does|is\s+)?(pl(ease|s)|(some|any)(one|body)|you|(need|want)|(can|(want|available|around|willing|ready)(\s*to)))\s*help)(?!(s|ed|er|ing))(\s*me(\s*please)?|pl(ease|s)|with)?\s*",
            re.IGNORECASE,
        ),
        "member_exclaiming_about_not_working_code": re.compile(
            r"[\s]*((why\s+)?(is('nt)?|does(\s+not|'nt)?)?\s*(my|the|this)?)\s*(this|code|game|pygame(\s*(game|program|code|project|assignment)?))\s*(((is|does)(\s*not|n't)?|not)\s*work(s|ed|ing)?)",
            re.IGNORECASE,
        ),
        "member_asking_for_code": re.compile(
            r"(?<!How\s)(?<!How\sdo\s)(?<!How\sdoes\s)(?<!I\s)((can('t|not)?|will)\s+)?(?<!How\scan\s)(please|pls|(some|any)(one|body)|(available|around|willing|ready|want)(\s*to))(\s*help(\s*me)?)?\s*(write|make|create|code|program|fix|correct|implement)(?!ing|ed)(\s*(a|my|the|this))?\s*(this|code|game|pygame(\s*(game|program|code)?))?\s*(for)?\s*(me(\s*please)?|please)?\s*",
            re.IGNORECASE,
        ),
        "member_asking_about_problem_with_code": re.compile(
            r"[\s]*((why|what('s)?\s+)(is('nt)?|does(\s+not|'nt)|am\s*i\s*(doing|having))?\s*((wrong|the\s*(problem|issue))?\s*(with(in)?|in(side)?)\s*)?(my|the|this)?)\s*(this|code|game|pygame(\s*(game|program|code)?))\s*",
            re.IGNORECASE,
        ),
    }
    INVALID_HELP_THREAD_TITLE_EMBEDS = {
        "thread_title_too_short": {
            "title": "Whoops, your help post title must be at least "
            f"{THREAD_TITLE_MINIMUM_LENGTH} characters long",
            "description": "Your help post title must be at least "
            f"**{THREAD_TITLE_MINIMUM_LENGTH}** characters long, so I'm "
            "forced to put a slowmode delay of "
            f"{THREAD_TITLE_TOO_SHORT_SLOWMODE_DELAY//60} minute{'s'*(THREAD_TITLE_TOO_SHORT_SLOWMODE_DELAY > 60)} "
            " on your post <:pg_sad:863165920038223912>.\n\n"
            "To make changes to your post's title, either right-click on it "
            "(desktop/web) or click and hold on it (mobile), then click on "
            "**'Edit Post'**. Use the input field called 'POST TITLE' in the "
            "post settings menu to change your post title. Remember to save "
            "your changes.\n\n"
            "**Thank you for helping us maintain clean help forum channels "
            "<:pg_robot:837389387024957440>**\n\n"
            "This alert and the slowmode should disappear after you have made appropriate changes.",
            "color": 0x36393F,
        },
        "member_asking_for_help": {
            "title": "Please don't ask for help in your post title (no need to). "
            "We'd love to help you either way!",
            "description": "Instead of asking for help or mentioning that you need "
            "help with something, please write a post title and starter message "
            "that describes the actual issue you're having in more detail. "
            "Also send code snippets, screenshots and other media, error messages, etc."
            "\n\n**[Here's why!](https://www.dontasktoask.com)**\n\n"
            "To make changes to your post's title, either right-click on it "
            "(desktop/web) or click and hold on it (mobile), then click on "
            "**'Edit Post'**. Use the input field called 'POST TITLE' in the "
            "post settings menu to change your post title. Remember to save "
            "your changes.\n\n"
            "This alert should disappear after you have made appropriate changes.",
            "color": 0x36393F,
            "footer": {
                "text": "I'm still learning, so I might make mistakes and "
                "occasionally raise a false alarm. 😅"
            },
        },
        "member_exclaiming_about_not_working_code": {
            "title": "Something doesn't work? Please tell us what.",
            "description": "Edit your help post title and your starter message "
            "to describe the problem that led to that diagnosis. What made your code "
            "stop working? What are you trying to do?\n"
            "Remember to send along code snippets, screenshots and other media, error "
            "messages, etc.\n\n"
            "To make changes to your post's title, either right-click on it "
            "(desktop/web) or click and hold on it (mobile), then click on "
            "**'Edit Post'**. Use the input field called 'POST TITLE' in the "
            "post settings menu to change your post title. Remember to save "
            "your changes.\n\n"
            "This alert should disappear after you have made appropriate changes.",
            "color": 0x36393F,
            "footer": {
                "text": "I'm still learning, so I might make mistakes and "
                "occasionally raise a false alarm. 😅"
            },
        },
        "member_asking_for_code": {
            "title": "Please don't ask if anybody can, wants to, or will fix, correct "
            "or write your code, game, project or assignment for you!",
            "description": "All helpers here are volunteers, who show people how to "
            "improve or implement things in their code by themselves. They don't do "
            "all the work for them. Show us what you are working on, what you've "
            "tried, as well as where you got stuck. "
            "Remember to send along code snippets, screenshots and other media, error "
            "messages, etc.\n\n"
            "To make changes to your post's title, either right-click on it "
            "(desktop/web) or click and hold on it (mobile), then click on "
            "**'Edit Post'**. Use the input field called 'POST TITLE' in the "
            "post settings menu to change your post title. Remember to save "
            "your changes.\n\n"
            "This alert should disappear after you have made appropriate changes.",
            "color": 0x36393F,
            "footer": {
                "text": "I'm still learning, so I might make mistakes and "
                "occasionally raise a false alarm. 😅"
            },
        },
        "member_asking_about_problem_with_code": {
            "title": "There's a problem with your code, game, project or assignment? "
            "Please tell us what are you struggling with.",
            "description": "Use your help post title and your starter message "
            "to describe how the problems with it came up. What made your code stop "
            "working? What are you trying to do? "
            "Remember to send along code snippets, screenshots and other media, error "
            "messages, etc.\n\n"
            "To make changes to your post's title, either right-click on it "
            "(desktop/web) or click and hold on it (mobile), then click on "
            "**'Edit Post'**. Use the input field called 'POST TITLE' in the "
            "post settings menu to change your post title. Remember to save "
            "your changes.\n\n"
            "This alert should disappear after you have made appropriate changes.",
            "color": 0x36393F,
            "footer": {
                "text": "I'm still learning, so I might make mistakes and "
                "occasionally raise a false alarm. 😅"
            },
        },
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
    STORAGE_CHANNEL_ID = 838090567682490458

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
            "*Hiss* Do I see a new user? *hiss*\n"
            + "Welcome to our wonderful chatroom",
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
