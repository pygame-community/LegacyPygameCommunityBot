"""
A simple script to automate code cleanups.
"""
import os, glob


def cleanup_code():
    """
    Clean up all files of a given extension under a directory
    """
    for filepath in glob.iglob(f"**/*.py", recursive=True):
        print("Formatting file: ", filepath)
        os.system(f"python -m black {filepath}")


if __name__ == "__main__":
    cleanup_code()
