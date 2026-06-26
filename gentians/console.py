import sys


### Print utilities
RED = "\033[91m"
END = "\033[0m"


def print_error_and_exit(message: str):
    """
    Prints the error message 'message' and exits.
    """
    print(RED + "Error: " + message + END)
    sys.exit(-1)
