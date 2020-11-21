import sys, os, time, asyncio
import discord, pygame, numpy, threading
from typing import Union

# Safe subscripting
def safeSub(li, ind):
	try:
		return li[ind]
	except:
		return ''

# Split
def split(com):
	spl = []
	tm = ''
	for c in com:
		if c in [' ', '\n']:
			if tm != '':
				spl.append(tm)
				tm = ''
		else:
			tm += c
	if tm != '':
		spl.append(tm)
	return spl


def formatTime(t: float, decimal_places=3):
	dec = 10**decimal_places

	if t < 1e-09:
		return f"{int(t*1e+09*dec)/dec} ps"

	elif t < 1e-06:
		return f"{int(t*1e+09*dec)/dec} ns"

	elif t < 1e-03:
		return f"{int(t*1e+06*dec)/dec} \u03bcs"

	elif t < 1.0:
		return f"{int(t*1e+03*dec)/dec} ms"

	return f"{int(t*1e+03*dec)/dec} s"


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
