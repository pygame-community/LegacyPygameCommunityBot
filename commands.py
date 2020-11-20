import sys, os, socket, re, threading
import asyncio, discord, json, time, psutil
from typing import Union

from util import safeSub as i, filterID, sendEmbed, formatTime
from sandbox import execSandbox

import pygame, numpy, math, cmath, pickle, pkg_resources, timeit, string, itertools, re, builtins

last_pet = time.time() - 3600
pet_anger = 0.1
pet_cost = 0.1
jumpscare_threshold = 20.0
pet_interval = 60.0

known_modules = {
	'pygame': pygame,
	'numpy': numpy,
	'discord': discord,
	'asyncio': asyncio,
	'json': json,
	'sys': sys,
	'os': os,
	'socket': socket,
	're': re,
	'math': math,
	'pickle': pickle,
	'threading': threading,
	'time': time,
	'timeit': timeit,
	'string': string,
	'itertools': itertools,
	'builtins': builtins
}

for module in sys.modules.keys():
	known_modules[module] = sys.modules[module]

pkgs = sorted([i.key for i in pkg_resources.working_set])
process = psutil.Process(os.getpid())

for module in pkgs:
	try:
		known_modules[module] = __import__(module.replace('-', '_'))
	except:
		pass

async def admin_command(msg, args, prefix):
	if i(args, 0) == 'eval' and len(args) == 2:
		
		try:
			script_start = time.perf_counter()
			ev = repr(eval(msg.content[len(prefix) + 5:])).replace('```', '\u200e‎`\u200e‎`\u200e‎`\u200e‎')
			script_duration = time.perf_counter()-script_start
			
			if len(ev) + 6 > 2048:
				await sendEmbed(msg.channel, f'Return output (executed in {formatTime(script_duration)}):', '```' + ev[:2038] + ' ...```')
			else:
				await sendEmbed(msg.channel, f'Return output (executed in {formatTime(script_duration)}):', '```' + ev + '```')
		
		except Exception as e:
			exp = f'```' + type(e).__name__.replace("`", "\u200e‎`") + ': ' + ", ".join([str(t) for t in e.args]).replace("`", "\u200e`") + '```'
			
			if len(exp) > 2048:
				await sendEmbed(msg.channel, 'An exception occured!', exp[:2044] + ' ...')
			else:
				await sendEmbed(msg.channel, 'An exception occured!', exp)
	
	elif i(args, 0) == 'sudo' and len(args) > 1:
		await msg.channel.send(msg.content[len(prefix) + 5:])
		await msg.delete()
	
	elif i(args, 0) == 'heap' and len(args) == 1:
		await sendEmbed(msg.channel, 'Total memory used', f'{process.memory_info().rss} B')
	
	elif i(args, 0) == 'stop' and len(args) == 1:
		sys.exit(0)
	
	else:
		await user_command(msg, args, prefix, True, True)

async def user_command(msg, args, prefix, is_priv = False, is_admin = False):
	global last_pet, pet_anger
	
	if i(args, 0) == 'doc' and len(args) == 2:
		splits = args[1].split('.')
		
		if i(splits, 0) not in known_modules:
			await sendEmbed(msg.channel, f'No known module of that!', f'No such module is available for its documentation')
			return
		objs = known_modules
		obj = None
		
		for part in splits:
			try:
				obj = objs[part]
				try:
					objs = vars(obj)
				except:
					objs = {}
			except:
				await sendEmbed(msg.channel, f'Class/function/sub-module not found!', f'There\'s no such thing here named `{args[1]}`')
				return
		messg = ''
		
		if i(splits, 0) == 'pygame':
			doclink = "https://www.pygame.org/docs"
			if len(splits) > 1:
				doclink += '/ref/' + i(splits, 1).lower() + ".html"
				doclink += "#"
				doclink += "".join([s+"." for s in splits])[:-1]
			messg += 'Online documentation: ' + doclink + '\n'
		messg += str(obj.__doc__).replace('```', '\u200e‎`\u200e‎`\u200e‎`\u200e‎')

		if len(messg) + 6 > 2048:
			await sendEmbed(msg.channel, f'Documentation for {args[1]}', '```' + messg[:2038] + ' ...```')
			return
		else:
			messg = '```' + messg + '```\n\n'

		for ob in objs.keys():
			if ob.startswith('__'):
				continue
			if type(objs[ob]).__name__ not in ('module', 'type', 'function', 'method_descriptor', 'builtin_function_or_method'):
				continue
			messg += '**' + type(objs[ob]).__name__.upper() + '** `' + ob + '`\n'

		if len(messg) > 2048:
			await sendEmbed(msg.channel, f'Documentation for {args[1]}', messg[:2044] + ' ...')
		else:
			await sendEmbed(msg.channel, f'Documentation for {args[1]}', messg)

	elif i(args, 0) == 'exec' and len(args) > 1:
		code = msg.content[len(prefix) + 5:]
		ret = ''

		for x in range(len(code)):
			if code[x] in [' ', '`', '\n']:
				ret = code[x + 1:]
			else:
				break
		code = ret
		
		for x in reversed(range(len(code))):
			if code[x] in [' ', '`', '\n']:
				ret = code[:x]
			else:
				break

		if ret.startswith('py\n'):
			ret = ret[3:]

		start = time.time()
		returned = await execSandbox(ret, 5 if is_priv else 2)
		duration = returned.duration                          # the execution time of the script alone
		
		if not returned.exc:
			if type(returned.img) is pygame.Surface:
				pygame.image.save(returned.img, f'temp{start}.png')
				await msg.channel.send(file=discord.File(f'temp{start}.png'))
				os.remove(f'temp{start}.png')
			str_repr = str(returned.text).replace("```", "\u200e‎`\u200e`\u200e‎`\u200e‎‎")
			
			if len(str_repr) + 6 > 2048:
				await sendEmbed(msg.channel, f'Returned text (executed in {formatTime(duration)}):', '```' + str_repr[:2038] + ' ...```')
			else:
				await sendEmbed(msg.channel, f'Returned text (executed in {formatTime(duration)}):', '```' + str_repr + '```')
		
		else:
			exp = '```' + type(returned.exc).__name__.replace("`", "\u200e‎`\u200e‎") + ': ' + i(returned.exc.args, 0).replace("`", "\u200e`") + '```'
			
			if len(exp) > 2048:
				await sendEmbed(msg.channel, 'An exception occured!', exp[:2044] + ' ...')
			else:
				await sendEmbed(msg.channel, 'An exception occured!', exp)
	
	elif i(args, 0) == 'pet' and len(args) == 1:
		pet_anger -= (time.time() - last_pet - pet_interval) * (pet_anger / jumpscare_threshold) - pet_cost
		
		if pet_anger < pet_cost:
			pet_anger = pet_cost
		last_pet = time.time()
		
		if pet_anger > jumpscare_threshold:
			await msg.channel.send(file=discord.File('save/die.gif'))
		else:
			await msg.channel.send(file=discord.File('save/pet.gif'))
	
	elif i(args, 0) == 'vibecheck' and len(args) == 1:
		await sendEmbed(msg.channel, 'Vibe Check, snek?', f'Previous petting anger: {pet_anger:.2f}/{jumpscare_threshold:.2f}\nIt was last pet {time.time() - last_pet:.2f} second(s) ago')
