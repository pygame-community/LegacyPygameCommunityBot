"""
A simple script to automate code cleanups.
"""
import glob
import os
import pathlib

try:
    import black
except ImportError:
    print("We use black to format code. Please install it with 'pip install black'")
    raise SystemExit


def cleanup_code():
    """
    Clean up all files of a given extension under a directory
    """
    for filepath in glob.iglob("**/*.py", recursive=True):
        path = pathlib.Path(os.getcwd(), filepath)
        if black.format_file_in_place(
            path, False, black.FileMode(), black.WriteBack.YES
        ):
            print("Formatted file: ", filepath)
        else:
            print(f"Skipping file {filepath} as it is already formatted")


if __name__ == "__main__":
    cleanup_code()
