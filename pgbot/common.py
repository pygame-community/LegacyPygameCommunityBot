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
SERVER_ID = 772505616680878080

# Misc
# Pet command constants
PET_COST = 0.1
JUMPSCARE_THRESHOLD = 20.0
PET_INTERVAL = 60.0

# BONCC quiky stuff
BONK = "<:pg_bonk:780423317718302781>"
PG_ANGRY_AN = "<a:pg_snake_angry_an:779775305224159232>"
BONCC_THRESHOLD = 10

# Constants
VERSION = "1.5.0"
TEST_MODE = "TEST_TOKEN" in os.environ
TEST_USER_ID = int(os.environ["TEST_USER_ID"]) if "TEST_USER_ID" in os.environ else None

TEST_USER_IDS = (
    set(int(user_id) for user_id in os.environ["TEST_USER_IDS"].split())
    if "TEST_USER_IDS" in os.environ
    else set()
)

if TEST_USER_ID is not None:
    TEST_USER_IDS.add(TEST_USER_ID)

TOKEN = os.environ["TEST_TOKEN" if TEST_MODE else "TOKEN"]
PREFIX = "pd!" if TEST_MODE else "pg!"

RULES_CHANNEL_ID = 772509621747187712
ROLES_CHANNEL_ID = 772535163195228200
GUIDE_CHANNEL_ID = 772528306615615500
ARRIVALS_CHANNEL_ID = 774916117881159681
LOG_CHANNEL_ID = 793250875471822930
ENTRY_CHANNEL_IDS = {"showcase": 772507247540437032, "resource": 810516093273768016}
ENTRIES_DISCUSSION_CHANNEL_ID = 780351772514058291
RESOURCE_ENTRIES_CHANNEL_ID = 810516093273768016

CMD_FUNC_PREFIX = "cmd_"

GUILD_LEVEL = 1
GUILD_MAX_FILE_SIZE = 8000000

# Admin, Moderator, Senior Mage, Wizards
ADMIN_ROLES = {
    772521884373614603,
    772508687256125440,
    772849669591400501,
    841338117968756766,
}

# AvaxarXapaxa, BaconInvader, MegaJC, Ankith
ADMIN_USERS = {
    414330602930700288,
    265154376409153537,
    444116866944991236,
    763015391710281729,
}

# Specialties, Helpfulies, Verified pygame contributors, Server Boosters
PRIV_ROLES = {
    774473681325785098,
    778205389942030377,
    780440736457031702,
    787473199088533504,
}

DIVIDER_ROLES = {836645525372665887, 836645368744771654}

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

ESC_BACKTICK_3X = "\u200b`\u200b`\u200b`\u200b"  # U+200B
ZERO_SPACE = "\u200b"  # U+200B

# Database channel
DB_CHANNEL_ID = 838090567682490458

# First is normal clock db message, second is testclock db message
DB_CLOCK_MSG_IDS = (838299905574830080, 838300106880057394)
DB_BLACKLIST_MSG_IDS = (840523987901087765, 840525722292584458)

DOC_EMBED_LIMIT = 3

# Link to pygame snake logo
PYGAME_SNEK = "https://media.discordapp.net/attachments/793272780987826197/836600713672523826/Discord_Server_Animated_Logo_V5_512x512.gif"

ROLE_PROMPT = {
    "title": [
        "Get more roles",
        "You need more roles for this channel (It's written everywhere!)",
        "I won't stop until you get more roles",
    ],
    "message": [
        "Hey there {0}, are you a @ Pygame Newbie, @ Pygame Regular or a "
        "@ Pygame Pro, or even a @ Pygame Contributor?\n"
        "Tell <@!235148962103951360> in <#772535163195228200>!",
    ],
}

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

BYDARIO_QUOTE = """
> Yea, if is dead bring it back to life or let it rest in peace
> When you are death ppl dont go to your tomb and say: dead person
> I know because I am dead and noone comes to visit me
<@!691691416799150152>
"""
