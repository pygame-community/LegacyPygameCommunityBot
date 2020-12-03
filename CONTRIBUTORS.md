# Guide on contributing

> To make the code consistent, contributors must follow these code style guidelines:
- Imports are categorized in a line (eg. multiple imports of builtin libraries `import cmath, math, os, socket, sys`)
- Use `camelCase` for function and method namings (Except for other libraries that don't)
- Space out 2 lines at the top of a class or function (Methods are spaced downwards with each other by one line) and one at the bottom if there's no more class/function below them
- Dictionary, lists, sets, tuples that takes multiple lines should be able to be compacted and have its opening brackets at the top and the closing brackets at a new line. Eg. 
```py
a_list = [
	'Apple', 'Banana', 'Orange',
	'Knife', 'Gun', 'Sword',
	'Noun', 'Adjective', 'Verb'
]
```

> Additions:
- For people that prefer tabs over spaces (like me), there is `tabspace.py` which allows you to change between spaces and tabs. Don't forget to change it to spaces before submitting a PR.
