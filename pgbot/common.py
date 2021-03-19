import os

import discord
import pygame


# For commonly used variables
bot = discord.Client()
window = pygame.Surface((1, 1))  # This will later be redefined

log_channel: discord.TextChannel

cmd_logs = {}

# Misc

# Constants
VERSION = "1.0"
TOKEN = os.environ["TOKEN"]
PREFIX = os.environ["PREFIX"]

LOG_CHANNEL_ID = int(os.environ["LOG_CHANNEL_ID"])

MUTED_ROLE = 772534687302156301

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

# PGC Specialties, PGC Helpfulies
PRIV_ROLES = {
    774473681325785098,
    778205389942030377
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

ESC_CODE_BLOCK_QUOTE = "\u200e`\u200e`\u200e`\u200e"

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

INCLUDE_FUNCTIONS = """
def print(*values, sep=" ", end="\\n"):
    global output
    output.text = str(output.text)
    output.text += sep.join(map(str, values)) + end
"""

EXP_TITLES = [
    'An exception occurred while trying to execute the command:',
    'An exception occured:',
]
