import sys, os, time, asyncio
import discord, pygame, numpy
from typing import Union
os.environ["SDL_VIDEODRIVER"] = "dummy"
pygame.init()
dummy = pygame.display.set_mode((69, 69))

import karma, commands, util

bot = discord.Client()
prefix = 'pg!'
admin_roles = (772521884373614603, 772508687256125440, 772849669591400501)

@bot.event
async def on_ready():
	karma.init()
	print('PygameBot ready!')
	while True:
		await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="discord.io/pygame_community"))
		await asyncio.sleep(2.5)
		await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.playing, name="in discord.io/pygame_community"))
		await asyncio.sleep(2.5)

@bot.event
async def on_member_join(user: discord.Member):
	await karma.vote(user, 0)

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
		if is_admin:
			await commands.admin_command(msg, util.split(msg.content[len(prefix):]), prefix)
		else:
			await commands.user_command(msg, util.split(msg.content[len(prefix):]), prefix)


@bot.event
async def on_message_delete(msg: discord.Message):
	pass

@bot.event
async def on_message_edit(before: discord.Message, after: discord.Message):
	pass

@bot.event
async def on_reaction_add(reaction: discord.Reaction, user: Union[discord.Member, discord.User]):
	msg = reaction.message
	if type(msg.channel) == discord.DMChannel:
		return
	if type(reaction.emoji) == discord.Emoji:
		emoji = reaction.emoji.name
	elif type(reaction.emoji) == discord.PartialEmoji:
		emoji = reaction.emoji.name
		if not reaction:
			emoji = ''
	else:
		emoji = reaction.emoji

	if user.id != msg.author:
		if emoji == '👍':
			await karma.vote(msg.author, 1)
		if emoji == '👎':
			await karma.vote(msg.author, -1)

@bot.event
async def on_reaction_remove(reaction: discord.Reaction, user: Union[discord.Member, discord.User]):
	msg = reaction.message
	if type(msg.channel) == discord.DMChannel:
		return
	if type(reaction.emoji) == discord.Emoji:
		emoji = reaction.emoji.name
	elif type(reaction.emoji) == discord.PartialEmoji:
		emoji = reaction.emoji.name
		if not reaction:
			emoji = ''
	else:
		emoji = reaction.emoji

	if user.id != msg.author:
		if emoji == '👍':
			await karma.vote(msg.author, -1)
		if emoji == '👎':
			await karma.vote(msg.author, 1)

with open('token.txt') as token:
	bot.run(token.read())
