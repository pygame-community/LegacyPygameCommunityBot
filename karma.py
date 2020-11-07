import asyncio, discord, json
from typing import Union

data = {}

def init():
	global data
	with open('save/karma.json') as f:
		data = json.loads(f.read())

def save():
	with open('save/karma.json', 'w') as f:
		f.write(json.dumps(data))

def getReputation(user):
	return data[user.id]['reputation']

async def setRep(user: Union[discord.Member, discord.User], amount = 1):
	if str(user.id) not in data.keys():
		data[str(user.id)] = {
			'reputation': amount
		}
	else:
		data[str(user.id)]['reputation'] = amount
	save()

async def vote(user: Union[discord.Member, discord.User], amount = 1):
	if str(user.id) not in data.keys():
		data[str(user.id)] = {
			'reputation': 0
		}
	data[str(user.id)]['reputation'] += amount
	save()
