import sys, os, socket, re, threading
import asyncio, discord, json, time
import concurrent.futures
from typing import Union

import karma
from util import safeSub as i, filterID, sendEmbed
from sandbox import execSandbox

import pygame, numpy, math, cmath, pickle, pkg_resources

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
	'threading': threading
}

for module in sys.modules.keys():
		known_modules[module] = sys.modules[module]

pkgs = sorted([i.key for i in pkg_resources.working_set])

for module in pkgs:
	try:
		known_modules[module] = __import__(module.replace('-', '_'))
	except:
		pass

async def admin_command(msg, args, prefix):
	if i(args, 0) == 'eval' and len(args) == 2:
		try:
			ev = '```' + repr(eval(msg.content[len(prefix) + 5:])).replace('`', '\u200e‎`') + '```'
			if len(ev) > 2048:
				await sendEmbed(msg.channel, 'Return output', ev[:2044] + ' ...')
			else:
				await sendEmbed(msg.channel, 'Return output', ev)
		except Exception as e:
			exp = f'```' + type(e).__name__.replace("`", "\u200e‎`") + ': ' + ", ".join([str(t) for t in e.args]).replace("`", "\u200e`") + '```'
			if len(exp) > 2048:
				await sendEmbed(msg.channel, 'An exception occured!', exp[:2044] + ' ...')
			else:
				await sendEmbed(msg.channel, 'An exception occured!', exp)
	elif i(args, 0) == 'sudo' and len(args) > 1:
		await msg.channel.send(msg.content[len(prefix) + 5:])
		await msg.delete()
	else:
		await user_command(msg, args, prefix)

async def user_command(msg, args, prefix):
	#if i(args, 0) == 'rep' and len(args) == 2:
	#	iden = filterID(args[1])
	#	if iden not in karma.data.keys():
	#		await sendEmbed(msg.channel, 'Invalid argument value!', 'Correct arguments: `rep <ID or mention>`')
	#		return
	#	await sendEmbed(msg.channel, f'Their reputation value', karma.data[iden]["reputation"])
	#elif i(args, 0) == 'rep':
	#	iden = str(msg.author.id)
	#	if iden not in karma.data.keys():
	#		karma.data[iden] = {
	#			"reputation": 0
	#		}
	#		await sendEmbed(msg.channel, f'Your reputation value', 0)
	#	else:
	#		await sendEmbed(msg.channel, f'Your reputation value', karma.data[iden]['reputation'])

	#el
	if i(args, 0) == 'doc' and len(args) == 2:
		splits = args[1].split('.')
		if i(splits, 0) not in known_modules:
			await sendEmbed(msg.channel, f'No known module of that!', f'No such module is available for its documentation')
			return
		objs = known_modules
		obj =  None
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
		messg += '```' + str(obj.__doc__).replace('`', '') + '```\n\n'

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

		timeout = 5
		try:
			start = time.time()
			thread = concurrent.futures.ThreadPoolExecutor().submit(execSandbox, ret)
			while thread.running():
				if time.time() > start + timeout:
					await sendEmbed(msg.channel, 'Sandbox ran for too long!', f"Your script has ran for more than {timeout} second(s)!")
					del thread
					return
				await asyncio.sleep(0.1)

			returned = thread.result()
			if type(returned.img) is pygame.Surface:
				pygame.image.save(returned.img, f'temp{start}.png')
				await msg.channel.send(file=discord.File(f'temp{start}.png'))
				os.remove(f'temp{start}.png')
			str_repr = '```' + str(returned.text).replace("`", "\u200e‎`") + '```'
			if len(str_repr) > 2048:
				await sendEmbed(msg.channel, 'Returned text', str_repr[:2044] + ' ...')
			else:
				await sendEmbed(msg.channel, 'Returned text', str_repr)
		except Exception as e:
			exp = '```' + type(e).__name__.replace("`", "\u200e‎`") + ': ' + ", ".join([str(t) for t in e.args]).replace("`", "\u200e`") + '```'
			if len(exp) > 2048:
				await sendEmbed(msg.channel, 'An exception occured!', exp[:2044] + ' ...')
			else:
				await sendEmbed(msg.channel, 'An exception occured!', exp)
