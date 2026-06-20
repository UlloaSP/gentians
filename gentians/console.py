import sys


### Print utilities
YELLOW = "\33[93m"
RED = "\033[91m"
END = "\033[0m"


def print_error_and_exit(message: str):
    """
    Prints the error message 'message' and exits.
    """
    print(RED + "Error: " + message + END)
    sys.exit(-1)


def print_warning(message: str):
    """
    Prints the warning message 'message'.
    """
    print(YELLOW + "Warning: " + message + END)
