import sys, os, time, asyncio
import discord, pygame, numpy, threading
from typing import Union

# Safe subscripting
def safeSub(li: list, ind: int):
	try:
		return li[ind]
	except IndexError:
		return ''

# Formats time with a prefix
def formatTime(t: float, decimal_places=4):
	dec = 10**decimal_places

	if t < 1e-09:
		return f'{int(t*1e+12*dec)/dec} ps'
	elif t < 1e-06:
		return f'{int(t*1e+09*dec)/dec} ns'
	elif t < 1e-03:
		return f'{int(t*1e+06*dec)/dec} \u03bcs'
	elif t < 1.0:
		return f'{int(t*1e+03*dec)/dec} ms'

	return f'{int(t*dec)/dec} s'

# Formats memory size with a prefix
def formatByte(b: int, decimal_places=3):
	dec = 10**decimal_places

	if b < 1e+03:
		return f'{int(b*dec)/dec} B'
	elif b < 1e+06:
		return f'{int(b*1e-03*dec)/dec} KB'
	elif b < 1e+09:
		return f'{int(b*1e-06*dec)/dec} MB'
	else:
		return f'{int(b*1e-09*dec)/dec} GB'

# Filters mention to get ID '<@!6969>' to 6969
def filterID(mention):
	a = mention.split('<')
	a = ''.join(a).split('@')
	a = ''.join(a).split('!')
	a = ''.join(''.join(a).split('>'))
	return a

# Sends an embed with a much more tight function
async def sendEmbed(channel, title, description, color=0xFFFFAA):
	return await channel.send(embed=discord.Embed(title=title, description=description, color=color))

# Modified thread with a kill method
class ThreadWithTrace(threading.Thread):
	def __init__(self, *args, **keywords):
		threading.Thread.__init__(self, *args, **keywords)
		self.killed = False

	def start(self):
		self.__run_backup = self.run
		self.run = self.__run
		threading.Thread.start(self)

	def __run(self):
		sys.settrace(self.globaltrace)
		self.__run_backup()
		self.run = self.__run_backup

	def globaltrace(self, frame, event, arg):
		if event == 'call':
			return self.localtrace
		else:
			return None

	def localtrace(self, frame, event, arg):
		if self.killed:
			if event == 'line':
				raise SystemExit()
		return self.localtrace

	def kill(self):
		self.killed = True
