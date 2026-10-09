from setuptools import Extension, setup

# Wheels can include the small decoder accelerator. Source installations without
# a C compiler retain the exact Python decoder and the same clause language.
setup(ext_modules=[Extension(
    "gentians.clauses._records", ["gentians/clauses/_records.c"], optional=True,
)])
