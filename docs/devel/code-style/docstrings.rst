=====================
Documenting Cerebrum
=====================

All "public" modules, classes, functions, constants, and scripts should be
typically be documented by docstrings.  Docstrings should:

- follow `PEP-257`_
- work with `sphinx`_


What to include
================
Some hints on what a docstring should include:

Modules
    For modules, describe how the module works, and if relevant:

    - how it connects to other modules and scripts
    - how it is affected by configuration

    For larger, and more complicated modules with sub-modules, the main module
    ``__init__.py`` will typically provide documentation with a birds-eye view
    of the entire module.

Scripts
    For stand-alone scripts, add a short description of what the script does,
    and include some examples on how to run it, if relevant.

Classes
    For classes, describe how the class works, and if relevant:

    - how it connects to other classes, modules and scripts
    - how it is affected by configuration
    - how it can be used (examples)

Functions
    For functions, document what the function does, as well as its arguments and
    return value.


What not to include
====================
Documentation should be omitted if it is redundant or makes the code less
readable.

Self-documenting function signatures
    You should omit args and/or return value for short functions if it is
    obvious from e.g. the function name or argument names.

    If adding documentation in a docstring *feels* redundant, it probably is:
    ::

        def parse_int(value):
            """
            :param value: the value to parse

            :returns int:
                Returns the value as an integer
            """

Private objects
    You don't have to document functions or classes that are "private" (only for
    *internal* use in its own module), unless it *needs* a docstring to easily
    understand its behaviour.

.. _pep-257: https://www.python.org/dev/peps/pep-0257/
.. _sphinx: http://www.sphinx-doc.org/
