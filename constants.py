TOKEN = open('token.txt').read()
PREFIX = 'pg!'

PGCOMMUNITY = 772505616680878080
NEAXTURE = 757729636045160618
ALLOWED_SERVERS = set((PGCOMMUNITY, NEAXTURE))

# PGC Admin, PGC Moderator, PGC Wizards, NXT Admin, NXT Moderator, NXT PG Bot Developers
ADMIN_ROLES = set((772521884373614603, 772508687256125440, 772849669591400501, 757845292526731274, 757845497795838004, 783219011294724137))

# PGC Specialties, PGC Helpfulies, NXT Developers
PRIV_ROLES = set((774473681325785098, 778205389942030377, 757845720819826718))

# AvaxarXapaxa, BaconInvader, MegaJC, Neuxbane, Ankith
ADMIN_USERS = set((414330602930700288, 265154376409153537, 444116866944991236, 590160104871952387, 763015391710281729))

# PGC pygame beginner, PGC pygame regular, PGC pygame pro, PGC pygame contributor
COMPETENCE_ROLES = set((772536799926157312, 772536976262823947, 772537033078997002, 772537232594698271))

# PGC #pygame, #beginners-help
PYGAME_CHANNELS = set((772507303781859348, 772816508015083552))

SCRIPT_PRINT = """

def print(*values, sep=" ", end="\\n"):
	values = list(values)
	output.text = str(output.text)
	
	for i in range(len(values)):
		values[i] = str(values[i])
		output.text += sep.join(values) + end

"""

INCLUDE_FUNCTIONS = {
	"print": SCRIPT_PRINT
}


ROLE_PROMPT = {
	"title": [],
	"message": []
}
