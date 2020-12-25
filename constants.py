TOKEN = open("token.txt").read()
PREFIX = "pg!"

VERSION = "1.0.0"

PGCOMMUNITY = 772505616680878080
NEAXTURE = 757729636045160618
ALLOWED_SERVERS = {PGCOMMUNITY, NEAXTURE}

# PGC Admin, PGC Moderator, PGC Wizards, NXT Admin, NXT Moderator, NXT PG Bot Developers
ADMIN_ROLES = {
    772521884373614603,
    772508687256125440,
    772849669591400501,
    757845292526731274,
    757845497795838004,
    783219011294724137,
}

# PGC Specialties, PGC Helpfulies, NXT Developers
PRIV_ROLES = {774473681325785098, 778205389942030377, 757845720819826718}

# AvaxarXapaxa, BaconInvader, MegaJC, Neuxbane, Ankith
ADMIN_USERS = {
    414330602930700288,
    265154376409153537,
    444116866944991236,
    590160104871952387,
    763015391710281729,
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

CHANNEL_LINKS = {
    791176841150332959: 775317562715406336,  # NXT Gateway #pygame-community-bot=> PGC #bot-maintenance
    775317562715406336: 791176841150332959,  # PGC #bot-maintenance => NXT Gateway #pygame-community-bot
}

SCRIPT_PRINT = """
def print(*values, sep=" ", end="\\n"):
    output.text = str(output.text)
    output.text += sep.join(map(str, values)) + end

"""

INCLUDE_FUNCTIONS = {"print": SCRIPT_PRINT}


ROLE_PROMPT = {"title": [], "message": []}

CLOCK_TIMEZONES = [
    (3600 * -5, 'MichaelCPalmer', (200, 140, 120)),
    (0, 'BaconInvader', (161, 255, 84)),
    (3600, 'MegaJC', (128, 0, 192)),
    (3600 * 2, 'jtiai', (240, 140, 200)),
    (3600 * 3, 'k4dir', (158, 110, 255)),
    (3600 * 7, 'Avaxar', (64, 255, 192))
]
