# -*- coding: utf-8 -*-

import unittest


class BaseUnitTestCase(unittest.TestCase):
    """ This is a subclass of the unittest TestCase.
    """
    pass


def class_match(cls, module, name):
    """ Test a given class and its parent classes for a class match.

    Recursive method, will test the class C{cls} and each of its
    superclasses for a match in its C{__module__} and its C{__name__}
    attribute.

    @type cls: type
    @param cls: The class to test

    @type module: str or NoneType
    @param module: The module or module prefix to test C{cls} for. If None,
        and a C{name} is given, we will only test for a name match.

    @type name: str or NoneType
    @param name: The class name to test C{cls} for. If None, and a C{module} is
        given, we will only test for a module match.

    @rtype: bool
    @return: True if the class, or one of the superclasses is of a given
        name and/or module.
    """
    _match_module = lambda cls, mod: (
        bool(mod) and bool(getattr(cls, '__module__')) and
        getattr(cls, '__module__', '').startswith(mod))

    _match_name = lambda cls, name: (
        bool(name) and bool(getattr(cls, '__name__')) and
        getattr(cls, '__name__') == name)

    if (not module) and (not name):
        # No module or name template given, cannot match
        return False
    elif not module and _match_name(cls, name):
        # Only match name
        return True
    elif not name and _match_module(cls, module):
        # Only match module
        return True
    elif _match_module(cls, module) and _match_name(cls, name):
        # Match name and module
        return True

    # No match yet, test every class in the mro except self
    for parent in cls.mro():
        if parent == cls or parent == object:
            continue
        if class_match(parent, module, name):
            return True

    # No match
    return False

