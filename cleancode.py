"""
A simple script to automate simple code cleanups. Currently it just strips all
trailing whitespaces on lines, replaces all tabs to spaces, normalises newlines
and terminates files with newlines.
"""
import glob


def cleanup_code():
    """
    Clean up all files of a given extension under a directory
    """
    for filepath in glob.iglob(f"**/*.py", recursive=True):
        newfile = ""
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f.read().splitlines():
                newfile += line.rstrip().replace("\t", " " * 4) + "\n"

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(newfile)


if __name__ == "__main__":
    cleanup_code()
