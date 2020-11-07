import pygame.gfxdraw
import pygame, math, cmath
import builtins, random
import types

filtered_builtins = {}
disallowed_builtins = (
	'__build_class__', '__debug__', '__doc__', '__import__', '__loader__', '__name__',
	'__package__', '__spec__', 'copyright', 'credits', 'exit', 'type',
	'help', 'input', 'license', 'print', 'open', 'quit', 'compile',
	'exec', 'eval', 'getattr', 'setattr', 'delattr'
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

del FilteredPygame.mask.__loader__
del FilteredPygame.math.__loader__
del FilteredPygame.transform.__loader__
del FilteredPygame.draw.__loader__
del FilteredPygame.gfxdraw.__loader__

for const in dir(pygame.constants):
	setattr(FilteredPygame, const, f'pygame.constants.{const}')

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

for k in filtered_builtins.keys():
	allowed_globals[k] = filtered_builtins[k]



def execSandbox(code):
	class output:
		text = None
		img = None
	allowed_globals['output'] = output

	for il in ['__subclasses__', '__loader__', '__bases__', 'mro']:
		if il in code:
			raise Exception('Uh oh... stinky.. poo, whose tryna breakout of the sandbox??!!')

	exec(code, allowed_globals, {})

	return output
