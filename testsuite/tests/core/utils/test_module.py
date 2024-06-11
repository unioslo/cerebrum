# -*- coding: utf-8 -*-
"""
Unit tests for mod:`Cerebrum.utils.module`
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import io
import sys

import pytest
import six

from Cerebrum.utils import module as modutils


def noop():
    pass


class Example(object):
    example_attr = 3


@pytest.fixture
def test_module():
    """ a fixture that returns this test module. """
    return sys.modules[test_module.__module__]


#
# import_item tests
#


def test_import_item_module(test_module):
    assert modutils.import_item(__name__) is test_module


def test_import_item_module_attr():
    assert modutils.import_item(__name__, item_name="noop") is noop


def test_import_item_module_nested_attrs():
    item = modutils.import_item(__name__, item_name="Example.example_attr")
    assert item == Example.example_attr


#
# parse tests
#


VALID_PARSE_TESTS = [
    ("foo", ("foo", None, None)),
    ("foo.bar", ("foo.bar", None, None)),
    ("foo:bar", ("foo", ":", "bar")),
    ("foo.bar/baz.bat", ("foo.bar", "/", "baz.bat")),
]


@pytest.mark.parametrize("item, parts", VALID_PARSE_TESTS,
                         ids=[t[0] for t in VALID_PARSE_TESTS])
def test_parse(item, parts):
    """ parsing a valid resolve-string should return the relevant parts """
    assert modutils.parse(item) == parts


@pytest.mark.parametrize(
    "value",
    [
        "",
        # separator present, but missing module or attr:
        "/",
        ":foo",
        "foo:",
        # illegal chars in module or attr
        "foo-bar",
        "foo:bar-baz",
    ],
)
def test_parse_invalid(value):
    """ parsing an invalid resolve-string should raise a value error """
    with pytest.raises(ValueError):
        modutils.parse(value)


#
# resolve tests
#


def test_resolve_module(test_module):
    assert modutils.resolve(__name__) is test_module


def test_resolve_module_error():
    non_existing = "{}.missing".format(__name__)
    with pytest.raises(ImportError) as exc_info:
        modutils.resolve(non_existing)

    msg = six.text_type(exc_info.value)
    assert msg.startswith("No module named")


def test_resolve_module_attr(test_module):
    item = "{}:noop".format(__name__)
    assert modutils.resolve(item) is noop


def test_resolve_module_attr_missing(test_module):
    item = "{}:missing".format(__name__)
    with pytest.raises(AttributeError) as exc_info:
        modutils.resolve(item)
    msg = six.text_type(exc_info.value)
    assert "has no attribute 'missing'" in msg


def test_resolve_module_nested_attr(test_module):
    item = "{}:Example.example_attr".format(__name__)
    assert modutils.resolve(item) == Example.example_attr


def test_resolve_module_nested_attr_missing(test_module):
    item = "{}:Example.missing_attr".format(__name__)
    with pytest.raises(AttributeError) as exc_info:
        modutils.resolve(item)
    msg = six.text_type(exc_info.value)
    assert "has no attribute 'missing_attr'" in msg


#
# this_module tests
#


def test_this_module_name():
    assert modutils.this_module().__name__ == __name__


def test_this_module(test_module):
    assert modutils.this_module() is test_module


#
# load_source tests
#
# These tests depend on the `write_dir` and `new_file` fixtures to create new,
# temporary python files to load.


def test_load_source():
    mod = modutils.load_source('foo', __file__)
    assert mod.__name__ == 'foo'
    assert mod.__file__.replace('.pyc', '.py') == __file__


def test_load_missing(new_file):
    with pytest.raises(ImportError):
        modutils.load_source('bar', new_file)


EXAMPLE_SCRIPT = """
import textwrap

# We use textwrap.dedent to create this simple literal,
# just to run some code in the module
foo = textwrap.dedent(
    '''
    This is some text
    '''
).strip()

def get_foo():
    ''' return the 'foo' string '''
    return foo
""".lstrip()


@pytest.fixture
def simple_pyfile(new_file):
    with io.open(new_file, encoding="utf-8", mode="w") as f:
        f.write(EXAMPLE_SCRIPT)
    return new_file


def test_load_source_from_file(simple_pyfile):
    example_module = modutils.load_source("example_module", simple_pyfile)
    assert example_module.__name__ == "example_module"
    assert example_module.__file__ == simple_pyfile
    assert example_module.get_foo() == "This is some text"


def test_load_source_in_sys_modules(simple_pyfile):
    module_name = "example_module_in_sys_modules"
    example_module = modutils.load_source(module_name, simple_pyfile)
    assert module_name in sys.modules
    assert sys.modules[module_name] is example_module


#
# make_class tests
#


class Foo(object):
    """ a class to use with make_class. """
    pass


class Bar(object):
    """ a class to use with make_class. """
    pass


class Baz(Bar):
    """ a subclass to use with make_class. """
    pass


def _format_entrypoint(mod, cls):
    return "{}:{}".format(mod.__name__, cls.__name__)


def test_make_class(test_module):
    bases = (Baz, Bar, Foo)
    import_spec = [_format_entrypoint(test_module, cls) for cls in bases]

    cls = modutils.make_class(import_spec)
    assert cls.__bases__ == bases + (object,)


def test_make_class_generate_name(test_module):
    bases = (Baz,)
    import_spec = [_format_entrypoint(test_module, cls) for cls in bases]

    cls = modutils.make_class(import_spec)
    assert cls.__name__ == "_dynamic_Baz"


def test_make_class_custom_name(test_module):
    bases = (Baz,)
    import_spec = [_format_entrypoint(test_module, cls) for cls in bases]

    cls = modutils.make_class(import_spec, name="test")
    assert cls.__name__ == "_dynamic_test"


def test_make_class_invalid_spec_type(test_module):
    """ import spec must be an ordered sequence (list or tuple) """
    bases = (Baz, Bar, Foo)
    import_spec = set(_format_entrypoint(test_module, cls) for cls in bases)

    with pytest.raises(ValueError) as exc_info:
        modutils.make_class(import_spec)

    msg = six.text_type(exc_info.value)
    assert msg.startswith("Invalid import spec")


def test_make_class_invalid_spec_order(test_module):
    """ import spec must order subclasses *before* superclasses. """
    bases = (Foo, Bar, Baz)
    import_spec = [_format_entrypoint(test_module, cls) for cls in bases]

    with pytest.raises(TypeError) as exc_info:
        modutils.make_class(import_spec)

    msg = six.text_type(exc_info.value)
    assert "should appear earlier" in msg
