import sys, os, time, asyncio
import discord, pygame, numpy
from typing import Union

import commands, util
from constants import *

os.environ['SDL_VIDEODRIVER'] = 'dummy'
pygame.init()
dummy = pygame.display.set_mode((69, 69))
bot = discord.Client()

@bot.event
async def on_ready():
	print('PygameBot ready!\nThe bot is in:')
	for server in bot.guilds:
		if server.id not in ALLOWED_SERVERS:
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

	if msg.content.startswith(PREFIX):
		is_admin = False
		is_priv = False
		for role in msg.author.roles:
			if role.id in ADMIN_ROLES:
				is_admin = True
			elif role.id in PRIV_ROLES:
				is_priv = True
		try:
			if is_admin or (msg.author.id in ADMIN_USERS):
				await commands.admin_command(msg, msg.content[len(PREFIX):].split(), PREFIX)
			else:
				await commands.user_command(msg, msg.content[len(PREFIX):].split(), PREFIX, is_priv, False)
		except discord.errors.Forbidden:
			pass

	if msg.channel.guild.id == PGCOMMUNITY:
		has_a_competence_role = False
		for role in msg.author.roles:
			if role.id in COMPETENCE_ROLES:
				has_a_competence_role = True

		if not has_a_competence_role and msg.channel.id in PYGAME_CHANNELS:
			mg = await util.sendEmbed(msg.channel, 'Get more roles!', 'Hey there, are you a beginner, intermediate or pro in pygame, or even a contributor? Tell Carl-Bot in <#772535163195228200>!')
			await asyncio.sleep(15)
			await mg.delete()

bot.run(TOKEN)
