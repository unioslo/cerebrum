# -*- coding: utf-8 -*-
""" Tests for mod:`Cerebrum.utils.descriptors`. """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import re

import pytest
import six

from Cerebrum.utils import descriptors


#
# base Descriptor tests
#


def test_descriptor_init():
    assert descriptors.Descriptor("foo")


def test_descriptor_name():
    obj = descriptors.Descriptor("foo")
    assert obj.name == "foo"


def test_descriptor_repr():
    obj = descriptors.Descriptor("foo")
    obj_repr = repr(obj)
    assert re.match(
        (
            r"^<Cerebrum\.utils\.descriptors\.Descriptor"
            r" name=u?'foo' at 0x[a-f0-9]+>$"
        ),
        obj_repr,
    )


def test_descriptor_get_default():
    obj = descriptors.Descriptor("foo")
    with pytest.raises(AttributeError) as exc_info:
        obj.get_default(object())

    assert six.text_type(exc_info.value) == "foo"


def test_descriptor_attr_name_prefix():
    obj = descriptors.Descriptor("foo")
    attr_name = obj.attr_name
    assert attr_name.startswith("_Descriptor__foo_")


def test_descriptor_attr_name_unique():
    obj_a = descriptors.Descriptor("foo")
    obj_b = descriptors.Descriptor("foo")
    assert obj_a.attr_name != obj_b.attr_name


def test_descriptor_get_class():
    descriptor = descriptors.Descriptor("foo")

    class Example(object):
        foo = descriptor

    assert Example.foo is descriptor


@pytest.fixture
def descriptor_owner():
    class DescriptorOwner(object):
        foo = descriptors.Descriptor("foo")
        bar = descriptors.Descriptor("bar")

    return DescriptorOwner()


def test_descriptor_get_unset(descriptor_owner):
    with pytest.raises(AttributeError) as exc_info:
        descriptor_owner.foo

    assert six.text_type(exc_info.value) == "foo"


def test_descriptor_set(descriptor_owner):
    value_foo = "unique-value-946c1e4b"
    value_bar = "unique-value-824664aa"
    descriptor_owner.foo = value_foo
    descriptor_owner.bar = value_bar
    assert value_foo in descriptor_owner.__dict__.values()
    assert value_bar in descriptor_owner.__dict__.values()


def test_descriptor_get(descriptor_owner):
    value_foo = "unique-value-946c1e4b"
    value_bar = "unique-value-824664aa"
    descriptor_owner.foo = value_foo
    descriptor_owner.bar = value_bar
    assert descriptor_owner.foo == value_foo
    assert descriptor_owner.bar == value_bar


def test_descriptor_delete_unset(descriptor_owner):
    with pytest.raises(AttributeError) as exc_info:
        del descriptor_owner.foo

    assert six.text_type(exc_info.value) == "foo"


def test_descriptor_delete(descriptor_owner):
    descriptor_owner.foo = "foo"
    del descriptor_owner.foo

    with pytest.raises(AttributeError) as exc_info:
        descriptor_owner.foo

    assert six.text_type(exc_info.value) == "foo"


#
# DefaultDescriptor tests
#


def test_default_descriptor_init():
    obj = descriptors.DefaultDescriptor("foo", "bar")
    assert obj.default == "bar"


def test_default_descriptor_get_default():
    obj = descriptors.DefaultDescriptor("foo")
    assert obj.get_default(object()) is None

    obj = descriptors.DefaultDescriptor("foo", default="bar")
    assert obj.get_default(object()) == "bar"


@pytest.fixture
def default_owner():
    class DefaultDescriptorOwner(object):
        foo = descriptors.DefaultDescriptor("foo")
        bar = descriptors.DefaultDescriptor("bar", "baz")

    return DefaultDescriptorOwner()


def test_default_descriptor_get_unset(default_owner):
    assert default_owner.foo is None
    assert default_owner.bar == "baz"


def test_default_descriptor_get(default_owner):
    default_owner.foo = "foo"
    default_owner.bar = "bar"
    assert default_owner.foo == "foo"
    assert default_owner.bar == "bar"


def test_default_descriptor_delete_unset(default_owner):
    del default_owner.foo
    assert default_owner.foo is None


def test_default_descriptor_delete(default_owner):
    default_owner.bar = "bar"
    del default_owner.bar
    assert default_owner.bar == "baz"


#
# lazy_property tests
#


DEFAULT_VALUE = 123


@pytest.fixture
def foo_class():
    class Foo(object):
        @descriptors.lazy_property
        def example(self):
            """Bar"""
            return DEFAULT_VALUE
    return Foo


def test_lazy_property_get_class(foo_class):
    """ getting a property from a class should return the property itself. """
    assert isinstance(foo_class.example, descriptors.lazy_property)


def test_lazy_property_docstring(foo_class):
    """ the property should get its docstring from its wrapped method. """
    assert foo_class.example.__doc__ == "Bar"


def test_lazy_property_default(foo_class):
    """ getting an unset value should work (and cache its value). """
    foo = foo_class()
    assert foo.example == DEFAULT_VALUE


def test_lazy_property_set(foo_class):
    """ setting a custom value should work (override the wrapped default). """
    foo = foo_class()
    foo.example = 321
    assert foo.example == 321


def test_lazy_property_del(foo_class):
    """ deleting a property should reset it to its default. """
    foo = foo_class()
    foo.example = 321
    del foo.example
    assert foo.example == DEFAULT_VALUE


def test_lazy_property_del_default(foo_class):
    """ deleting an unset property should work (do nothing). """
    foo = foo_class()
    del foo.example
    assert foo.example == DEFAULT_VALUE
