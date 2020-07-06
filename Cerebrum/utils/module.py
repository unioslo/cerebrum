# coding: utf-8
#
# Copyright 2017 University of Oslo, Norway
#
# This file is part of Cerebrum.
#
# Cerebrum is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Cerebrum is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Cerebrum; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.
# Copyright 2002-2015 University of Oslo, Norway
""" Python module and import utilities.

This module contains utilities for dynamically importing other modules, and
some module introspection utilities.

All dynamic loading of modules and classes should eventually be replaced with
pkg_resources and entry points.

TODO: Replace
  - `Cerebrum.Utils:dyn_import` -> `load_source`
  - the class lookup in `Cerebrum.Utils:Factory.make_class` with `load_source`
  - `Cerebrum.Utils:this_module` -> `this_module`

"""
import functools
import inspect
import re

try:
    # PY > 3.3
    from importlib.machinery import SourceFileLoader

    def _load_source(name, path):
        return SourceFileLoader(name, path).load_module()

except ImportError:
    from imp import load_source as _load_source


def import_item(module_name, item_name=None):
    """Dynamically import a module or a module item.

    :param str module_name:
        A module to dynamically import.

    :param str item_name:
        Some attribute to fetch from the module.

    :return:
        The module, if no item_name is given. Return the item fetched from the
        module otherwise.
    """
    # This method is adopted from `pkg_resources.EntryPoint.resolve`.
    module = __import__(module_name, fromlist=['__name__'], level=0)

    if item_name:
        attrs = item_name.split('.')
        return functools.reduce(getattr, attrs, module)
    else:
        return module


# NOTE: We include the pattern flags in the expression here, so that we're
#       able to do `re.compile(SOURCE_RE.pattern)` later, if needed.
SOURCE_RE = re.compile(
    r"""(?ix)  # re.IGNORECASE, re.VERBOSE
    ^\s*
    (?P<module>
          (?:[_a-z][_a-z0-9]*)       # valid module name
        (?:\.[_a-z][_a-z0-9]*)*      # any number of dotted sub-module names
    )
    \s*
    (?:
        (?P<separator>
            [:/]                     # valid separator characters
        )
        \s*
        (?P<item>
              (?:[_a-z][_a-z0-9]*)   # valid attribute name
            (?:\.[_a-z][_a-z0-9]*)*  # any number of dotted sub-attr names
        )
    )?
    \s*$
    """)


def parse(source):
    """ Parse an input string into components that can be imported and fetched.

    :param str source:
        An entrypoint-like string with format: '<module>[<separator><name>]'
        where:

        - <module> is an importable module name, e.g. 'foo', 'foo.bar'
        - <separator> is one of '/', ':'
        - <name> is an attribute to recursively fetch from that module, e.g.
          'baz' or 'baz.bat'

    :return tuple:
        Returns a tuple with three items; module, separator, name.
    """
    match = SOURCE_RE.match(source)
    if not match:
        raise ValueError("invalid source ({0})".format(source))
    return tuple(match.group(x) for x in ('module', 'separator', 'item'))


def resolve(source):
    """ Load some source string.

    :param str source:
        What to import/fetch (see ``parse_source``)

    Examples
    --------
    Import a module, 'foo.bar':

        my_module = load_source('foo.bar')

    Fetch a class attribute 'attr' from the class 'Cls' in sub-module
    'mod.sub':

        my_attr = load_source('mod.sub:Cls.attr')
        my_attr = load_source('mod.sub/Cls.attr')

    """
    module_name, _, item_name = parse(source)
    return import_item(module_name, item_name)


def this_module():
    """ Return module object of the caller.

    :return module:
        Returns the module object of the caller.
    """
    caller_frame = inspect.currentframe().f_back
    return inspect.getmodule(caller_frame)


def load_source(name, path):
    """ Load a python source file as a module.

    This allows us to import a given source file and inject it as a module.
    This can be useful in tests, where we might want to inject our own config
    modules:

        load_source('cereconf', '/path/to/cereconf.py')
        import cereconf
        print(cereconf.__file__)

    :param str name: The name of the imported module.
    :param str path: The path to the source file.

    :return Module: Returns a python module.

    :raise ImportError: If unable to import.
    """
    try:
        return _load_source(name, path)
    except IOError as e:
        raise ImportError(e)


def make_class(import_spec, name=None, hint=None):
    """
    Assemble a class from a sequence of base class import strings.

    :type import_spec: list, tuple
    :param import_spec:
        A sequence of classes to import/fetch (see :py:func:`resolve`).

    :type name: str
    :param name:
        Class name suffix.  The constructed class will be named
        "_dynamic_<name>".  If no name is given, the name of the first base
        class will be used.

    :type hint: str
    :param hint:
        Variable hint (i.e. where does the import_spec come from?) for error
        messages.

    :rtype: type
    """
    if not isinstance(import_spec, (tuple, list)):
        raise ValueError("Invalid import spec %r - expected list or tuple "
                         "(name=%r, hint=%r)" %
                         (import_spec, name, hint))

    bases = []
    for import_string in import_spec:
        cls = resolve(import_string)

        # The import_spec sequence controls which classes are used to construct
        # a class.  The order inside such a sequence is significant for the
        # MRO in the constructed class.
        #
        # A likely misconfiguration is to list a class A as class_tuple[N], and
        # a subclass of A as class_tuple[N+x], as that would mean the subclass
        # won't override any of A's methods.
        #
        # The following code should ensure that this form of misconfiguration
        # won't be used.
        #
        # Note: a similar check is done by 'type' for new-style classes.
        for override in bases:
            if issubclass(cls, override):
                raise TypeError("Class %r should appear earlier than "
                                "its subclass %r (name=%r, hint=%r)" %
                                (cls, override, name, hint))
        bases.append(cls)

    # Requirement for constructing a class with 'type'
    bases.append(object)

    # Construct class
    cls_name = '_dynamic_' + (name or bases[0].__name__)
    bases = tuple(bases)
    return type(cls_name, bases, {})
