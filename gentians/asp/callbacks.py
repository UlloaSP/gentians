import sys

import clingo

from ..timing import instrumentation


def wrapper_exit_callback(code, message):
    if "error" in message:
        raise RuntimeError(f"{code}\n{message}")


def coverage_logger(code, message):
    with instrumentation():
        if code != clingo.MessageCode.AtomUndefined:
            print(message, file=sys.stderr, end="" if message.endswith("\n") else "\n")
