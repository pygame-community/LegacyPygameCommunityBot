import glob

mode = input("Choose your prefered indentation method(tab/space)")

for filepath in glob.iglob("**/*.py", recursive=True):
	with open(filepath, "r") as f:
		file = f.read()

	if mode == "tab":
		newfile = file.replace(" " * 4, "\t")
	elif mode == "space":
		newfile = file.replace("\t", " " * 4)
	else:
		raise ValueError("Invalid indentation method")

	with open(filepath, "w") as f:
		f.write(newfile)
