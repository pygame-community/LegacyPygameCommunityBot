class Output:
    """
    Output class for posting relevent data through discord
    """
    def __init__(self):
        self.text = ""
        self.img = None
        self.exc = None
        self.duration = -1  # The script execution time


class SandboxFunctionsObject:

    public_functions = (
        "print",
    )
    def __init__(self):
        self.output = Output()

    def print(self, *values, sep=" ", end="\n"):
        self.output.text = str(self.output.text)
        self.output.text += sep.join(map(str, values)) + end
