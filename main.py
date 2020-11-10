import sys, os, time, asyncio
import discord, pygame, numpy
from typing import Union
os.environ["SDL_VIDEODRIVER"] = "dummy"
pygame.init()
dummy = pygame.display.set_mode((69, 69))

import commands, util

bot = discord.Client()
prefix = 'pg!'
admin_roles = [772521884373614603, 772508687256125440, 772849669591400501, 757845292526731274, 757845497795838004]
admin_users = [414330602930700288, 265154376409153537, 444116866944991236, 590160104871952387]
allowed_servers = [772505616680878080, 757729636045160618]

introch_id = 774916117881159681
intro_channel = None

@bot.event
async def on_ready():
	global intro_channel

	print('PygameBot ready!\nThe bot is in:')
	for server in bot.guilds:
		if server.id not in allowed_servers:
			await server.leave()
			continue
		print('-', server.name)
		for ch in server.channels:
			print('  +', ch.name)
			if server.id == 772505616680878080 and ch.id == 774916117881159681:
				intro_channel = ch

	while True:
		await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="discord.io/pygame_community"))
		await asyncio.sleep(2.5)
		await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.playing, name="in discord.io/pygame_community"))
		await asyncio.sleep(2.5)

@bot.event
async def on_member_remove(user: discord.Member):
	await util.sendEmbed(intro_channel, '', f'{user} left!')

@bot.event
async def on_message(msg: discord.Message):
	if msg.author.bot:
		return
	if type(msg.channel) == discord.DMChannel:
		await msg.channel.send('Please do commands at the server!')
	if msg.content.startswith(prefix):
		is_admin = False
		for role in msg.author.roles:
			if role.id in admin_roles:
				is_admin = True
				break
		try:
			if is_admin or msg.author.id in admin_users:
				await commands.admin_command(msg, util.split(msg.content[len(prefix):]), prefix)
			else:
				await commands.user_command(msg, util.split(msg.content[len(prefix):]), prefix)
		except discord.errors.Forbidden:
			pass

with open('token.txt') as token:
	bot.run(token.read())
