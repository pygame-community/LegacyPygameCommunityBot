import os
import discord
from dotenv import load_dotenv
import pygame

if os.path.isfile(".env"):
    load_dotenv()  # take environment variables from .env

# For commonly used variables
ints = discord.Intents.default()
ints.members = True  # needed for on_member_join
bot = discord.Client(intents=ints)
window = pygame.Surface((1, 1))  # This will later be redefined

log_channel: discord.TextChannel
arrivals_channel: discord.TextChannel
roles_channel: discord.TextChannel
guide_channel: discord.TextChannel
entries_discussion_channel: discord.TextChannel
entry_channels = {}

cmd_logs = {}

BOT_ID = 772788653326860288

# Misc
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

# Constants
VERSION = "1.4.0"
TEST_MODE = "TEST_TOKEN" in os.environ
TOKEN = os.environ["TEST_TOKEN" if TEST_MODE else "TOKEN"]
PREFIX = "pd!" if TEST_MODE else "pg!"

ROLES_CHANNEL_ID = 772535163195228200
GUIDE_CHANNEL_ID = 772528306615615500
ARRIVALS_CHANNEL_ID = 774916117881159681
LOG_CHANNEL_ID = 793250875471822930
ENTRY_CHANNEL_IDS = {
    "showcase": 772507247540437032,
    "resource": 810516093273768016
}
ENTRIES_DISCUSSION_CHANNEL_ID = 780351772514058291

MUTED_ROLE = 772534687302156301
BOT_SUS_ROLE = 829281419125719070

# PGC Admin, PGC Moderator, PGC Wizards
ADMIN_ROLES = {
    772521884373614603,
    772508687256125440,
    772849669591400501,
}

# AvaxarXapaxa, BaconInvader, MegaJC, Ankith
ADMIN_USERS = {
    414330602930700288,
    265154376409153537,
    444116866944991236,
    763015391710281729
}

# Specialties, Helpfulies, Verified pygame contributors, Server Boosters
PRIV_ROLES = {
    774473681325785098,
    778205389942030377,
    780440736457031702,
    787473199088533504,
}

# Beginner, Regular, Pro, Contributor
COMPETENCE_ROLES = {
    772536799926157312,
    772536976262823947,
    772537033078997002,
    772537232594698271,
}

# PGC #regulars-pygame-help, #beginners-help
PYGAME_CHANNELS = {772507303781859348, 772816508015083552}

CLOCK_TIMEZONES = [
    (3600 * -4, 'Ghast', (176, 111, 90)),
    (0, 'BaconInvader', (123, 196, 63)),
    (3600 * 2, 'MegaJC', (255, 28, 28)),
    (3600 * 2, 'bydariogamer', (255, 28, 28)),
    (3600 * 2, 'pirosalma', (255, 28, 28)),
    (3600 * 2, 'CozyFractal', (255, 28, 28)),
    (3600 * 3, 'k4dir', (66, 135, 245)),
    (3600 * 5.5, 'Ankith', (240, 140, 0)),
    (3600 * 7, 'Avaxar', (64, 255, 192)),
]

ESC_BACKTICK_3X = "\u200b`\u200b`\u200b`\u200b"  # U+200B
ZERO_SPACE = "\u200b"  # U+200B

DOC_EMBED_LIMIT = 3

ROLE_PROMPT = {
    "title": [
        "Get more roles",
        "You need more roles for this channel (It's written everywhere!)",
        "I won't stop until you get more roles"
    ],

    "message": [
        "Hey there {0}, are you a @ Pygame Newbie, @ Pygame Regular or a @ Pygame Pro,"
        "or even a @ Pygame Contributor?\n"  # Broke down line limit
        "Tell <@!235148962103951360> in <#772535163195228200>!",
    ]
}

EXC_TITLES = [
    'An exception occurred while trying to execute the command:',
    'An exception occured:',
]

BOT_WELCOME_MSG = {
    "greet": (
        "Hi", "Hello", "Welcome to Pygame Community", "Greetings",
        "Howdy", "Hi there, ", "Hey there", "*Hiss* Who's that? It's",
        "*Hisss* Welcome", "Hello there,", "Ooooh! Hello", "Hi there,",
        "*Hiss* Do I see a new user? *hisss*\n\nWelcome to our wonderful chatroom",
    ),

    "check": (
        "Check out our", "Make sure to check out the",
        "Take a look at our", "See our", "Please see our",
        "Be sure to read our", "Be sure to check the",
        "Be sure to check out our",
    ),

    "grab": (
        ", grab", ". Then get some", ", take", ", then grab yourself some shiny", ". Get some fancy", ", get some",
        ", then get yourself some cool", ", then get yourself some", ", take some",
        ", then take some", ", then take some", ". Then go take some fancy",
        ", then grab some shiny",
    ),

    "end": (
        " and have fun!", ", then have fun with pygame!", ", then have fun with pygame! *hiss* ",
        " and have a nice time!", " and enjoy your stay!", " and have some fun! *hissss*", " and have fun here!",
        " and have fun with pygame!", " and have fun with pygame! *hisssss*",
        " and have fun here! *hissss*",
    ),

}

ILLEGAL_ATTRIBUTES = (
    "__subclasses__", "__loader__", "__bases__", "__code__",
    "__getattribute__", "__setattr__", "__delattr_", "mro",
    "__class__", "__dict__"
)

BOT_HELP_PROMPT = {
    "title": "Help",
    "color": 0xFFFF00,

    "body": f"""
Hey there, do you want to use <@{BOT_ID}> ?
My command prefix is `{PREFIX}`.
If you want me to run your code, use Discord's code block syntax.
Learn more about Discord code formatting **[HERE](https://discord.com/channels/772505616680878080/774217896971730974/785510505728311306)**.
If you want to know about a specifc command run {PREFIX}help [command], for example {PREFIX}help exec.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━""",
}
