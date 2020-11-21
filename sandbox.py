import pygame.gfxdraw
import pygame, math, cmath, time, os
import builtins, random, asyncio, numpy
import types, threading, psutil, gc
from util import ThreadWithTrace

process = psutil.Process(os.getpid())

filtered_builtins = {}
disallowed_builtins = (
	'__build_class__', '__debug__', '__doc__', '__import__', '__loader__', '__name__',
	'__package__', '__spec__', 'copyright', 'credits', 'exit', 'type',
	'help', 'input', 'license', 'print', 'open', 'quit', 'compile',
	'exec', 'eval', 'getattr', 'setattr', 'delattr', 'globals', 'locals', 'vars'
)

for key in dir(builtins):
	if key not in disallowed_builtins:
		filtered_builtins[key] = getattr(builtins, key)


class FilteredPygame:
	Surface = pygame.Surface
	Rect = pygame.Rect
	Color = pygame.Color
	draw = pygame.draw
	gfxdraw = pygame.gfxdraw
	transform = pygame.transform
	mask = pygame.mask
	math = pygame.math

	class image:
		fromstring = pygame.image.fromstring
		tostring = pygame.image.tostring
		frombuffer = pygame.image.frombuffer

	class constants:
		pass


del FilteredPygame.mask.__loader__
del FilteredPygame.math.__loader__
del FilteredPygame.transform.__loader__
del FilteredPygame.draw.__loader__
del FilteredPygame.gfxdraw.__loader__

del FilteredPygame.mask.__spec__
del FilteredPygame.math.__spec__
del FilteredPygame.transform.__spec__
del FilteredPygame.draw.__spec__
del FilteredPygame.gfxdraw.__spec__

for const in pygame.constants.__all__:
	setattr(FilteredPygame.constants, f'{const}', pygame.constants.__dict__[const])
	setattr(FilteredPygame, f'{const}', pygame.constants.__dict__[const])

allowed_globals = {
	'__builtins__': {},
	'pygame': FilteredPygame,
	'math': math,
	'cmath': cmath,
	'random': random
}

del math.__loader__
del cmath.__loader__
del random.__loader__

del math.__spec__
del cmath.__spec__
del random.__spec__

for k in filtered_builtins.keys():
	allowed_globals[k] = filtered_builtins[k]


async def execSandbox(code, timeout = 5, max_memory = 2**28):
	class output:
		text = ''
		img = None
		exc = None
		duration = None # The script execution time

	allowed_globals['output'] = output

	for il in ['__subclasses__', '__loader__', '__bases__', 'mro']:
		if il in code:
			class YouAreSusException(Exception):
				pass
			raise YouAreSusException('Uh oh... stinky.. poo, ahahahahh, whose tryna breakout of the sandbox??!!')

	def execThread():
		glob = allowed_globals.copy()
		try:
			compiled_code = compile('def print(*values, sep=" ", end="\\n"):\n\tvalues = list(values)\n\toutput.text = str(output.text)\n\tfor i in range(len(values)):\n\t\tvalues[i] = str(values[i])\n\toutput.text += sep.join(values) + end\npass\n\n' + code, "<string>", mode='exec')

			script_start = time.perf_counter()
			exec(compiled_code, glob)
			output.duration = time.perf_counter() - script_start
		
		except Exception as e:
			output.exc = e
		glob.clear()
		gc.collect()
	thread = ThreadWithTrace(target=execThread)
	thread.start()

	start = time.time()
	while thread.is_alive():
		if start + timeout < time.time():
			output.exc = RuntimeError(f'Sandbox was running for more than the timeout of {timeout} seconds!')
			break
		if process.memory_info().rss > max_memory:
			output.exc = RuntimeError(f'The bot\'s memory has taken up to {max_memory} bytes!')
			break
		await asyncio.sleep(0.05) # Let the bot do other async things
	thread.kill()
	thread.join()
	return output
