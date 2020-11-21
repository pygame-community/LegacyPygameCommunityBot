import pygame.gfxdraw
import pygame, math, cmath, time, os
import builtins, asyncio, numpy
import types, threading, psutil, gc

from util import ThreadWithTrace, INCLUDE_FUNCTIONS

# extras
import timeit, random, string, itertools, re, builtins

process = psutil.Process(os.getpid())

filtered_builtins = {}
disallowed_builtins = (
	'__debug__', '__doc__', '__import__', '__loader__', '__name__',
	'__package__', '__spec__', 'copyright', 'credits', 'exit', 'type',
	'help', 'input', 'license', 'print', 'open', 'quit', 'compile',
	'exec', 'eval', 'getattr', 'setattr', 'delattr', 'globals', 'locals', 'vars'
)

for key in dir(builtins):
	if key not in disallowed_builtins:
		filtered_builtins[key] = getattr(builtins, key)
filtered_builtins['__build_class__'] = builtins.__build_class__

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
	'math': math,
	'cmath': cmath,
	'random': random,
	're': re,
	'time': time,
	'timeit': timeit,
	'string': string,
	'itertools': itertools,
}

for module in allowed_globals.keys():
	del allowed_globals[module].__loader__, allowed_globals[module].__spec__

allowed_globals["__builtins__"] = {}
allowed_globals["pygame"] = FilteredPygame

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
			included_funcs = "\n".join( INCLUDE_FUNCTIONS[func_name] for func_name in INCLUDE_FUNCTIONS.keys() )
			
			compiled_code = compile( f"{included_funcs}\n{code}", "<string>", mode='exec' )

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
