import sys, os, time, asyncio
import discord, pygame, numpy
from typing import Union
os.environ["SDL_VIDEODRIVER"] = "dummy"
pygame.init()
dummy = pygame.display.set_mode((69, 69))

import commands, util

bot = discord.Client()
prefix = 'pg!'

# PGC Admin, PGC Moderator, PGC Wizards, NXT Devistrator, NXT Moderator
admin_roles = set((772521884373614603, 772508687256125440, 772849669591400501, 757845292526731274, 757845497795838004))

# PGC Specialties, PGC Helpfulies, NXT Developer, NXT Contributor
priv_roles = set((774473681325785098, 778205389942030377, 757845720819826718, 757846873930203218))

# AvaxarXapaxa, BaconInvader, MegaJC, Neuxbane
admin_users = set((414330602930700288, 265154376409153537, 444116866944991236, 590160104871952387))

# PGC pygame beginner, PGC pygame regular, PGC pygame pro, PGC pygame contributor
competence_roles = set((772536799926157312, 772536976262823947, 772536976262823947, 772537033078997002))

# PGC (Pygame Community Server), NXT (Neaxture)
allowed_servers = set((772505616680878080, 757729636045160618))


@bot.event
async def on_ready():
	print('PygameBot ready!\nThe bot is in:')
	for server in bot.guilds:
		if server.id not in allowed_servers:
			await server.leave()
			continue
		print('-', server.name)
		for ch in server.channels:
			print('  +', ch.name)

	while True:
		await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="discord.io/pygame_community"))
		await asyncio.sleep(2.5)
		await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.playing, name="in discord.io/pygame_community"))
		await asyncio.sleep(2.5)


@bot.event
async def on_message(msg: discord.Message):
	if msg.author.bot:
		return

	if type(msg.channel) == discord.DMChannel:
		await msg.channel.send('Please do commands at the server!')
		return

	if msg.content.startswith(prefix):
		is_admin = False
		is_priv = False
		for role in msg.author.roles:
			if role.id in admin_roles:
				is_admin = True
			elif role.id in priv_roles:
				is_priv = True
		try:
			if is_admin or (msg.author.id in admin_users):
				await commands.admin_command(msg, util.split(msg.content[len(prefix):]), prefix)
			else:
				await commands.user_command(msg, util.split(msg.content[len(prefix):]), prefix, is_priv, False)
		except discord.errors.Forbidden:
			pass

	if msg.channel.guild.id == 772505616680878080: # In the pygame community discord server
		has_a_competence_role = False
		for role in msg.author.roles:
			if role.id in competence_roles:
				has_a_competence_role = True

		if not has_a_competence_role and msg.channel.id in [772507303781859348, 772816508015083552]: # PGC #pygame, #beginners-help
			mg = await util.sendEmbed(msg.channel, 'What are you?', 'Are you a beginner, intermediate, pro, or a contributor in pygame? Please choose in <#772535163195228200>')
			await asyncio.sleep(5)
			await mg.delete()


with open('token.txt') as token:
	bot.run(token.read())
