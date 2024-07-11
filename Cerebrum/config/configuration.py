#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2015-2024 University of Oslo, Norway
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
""" Cerebrum configuration module.

This module contains the core of the Cerebrum configuration framework. It
consists of:

Configuration
    The Configuration class is a config schema framework. Actual configuration
    implementations consists of Configuration-subclasses with ConfigDescriptor
    attributes.

    Instances of Configuration-subclasses functions as a data containers for
    settings.

    Multiple configuration classes can be combined by inheritance:

    >>> class MyConfiguration(CommonConfiguration, SomeOddConfiguration):
    >>>    pass

    Configurations can also be extended easily:

    >>> MyConfiguration.new_setting = ConfigDescriptor(Setting, default='foo')

    TODO: Rename to ConfigSchema or similar?

ConfigDescriptor
    The ConfigDescriptor object wraps Settings as class descriptors. This is
    how a Setting gets assigned to (implemented in) a Configuration-subclass.

    All settings that are implemented in a Configuration should be wrapped in
    this descriptor:

    >>> class MyConfiguration(Configuration):
    >>>     a_setting = ConfigDescriptor(Setting, default='foo')
    >>>     another_setting = ConfigDescriptor(Setting)

Namespace
    Namespace is a special Setting. It allows us to use another Configuration
    as a Setting.

    By using Namespaces in a configuration, we can group settings togeher. This
    makes large Configurations easier to understand. Namespaces can also be
    read in separately from files.

    >>> class MyConfiguration(Configuration):
    >>>     my_namespace = ConfigDescriptor(Namespace, config=MyNamespace)
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
from collections import OrderedDict

import six

from . import settings
from .errors import ConfigurationError


class _Odict(OrderedDict):
    """ OrderedDict with `dict` repr. """

    def __repr__(self):
        # TODO: Repr output should probably be sorted, to avoid confusion.
        #       Consider re-implementing __repr__ from collections.OrderedDict
        return super(_Odict, self).__repr__()


def flatten_dict(d, prefix=''):
    """ Generate a recursive, sorted iterator.

    This function yields key,value pairs for a dict that is 'flattened'.

    Example input
        { 'b': {'a': 1, 'b': 2}, 'a': {'b': 3, 'a': 4}, }

    Will yield:
        'a.a', 4
        'a.b', 3
        'b.a', 1
        'b.b': 2

    :param dict d:
        The dict to flatten.

    :raise ValueError:
        If a key gets duplicated in the flattened dict.

    :return generator:
        A generator that yields sorted, flattened key value pairs.
    """
    for k in sorted(d):
        newkey = '{}.{}'.format(prefix, k) if prefix else k
        if isinstance(d[k], dict):
            for kk, vv in flatten_dict(d[k], newkey):
                yield kk, vv
        else:
            yield newkey, d[k]


def next_attr(path):
    """
    Splits *path* by the path separator `.`

    When accessing settings in nested namespaces, this helper function gets the
    next namespace to fetch:

    >>> next_attr("foo.bar.baz")
    ("foo", "bar.baz")
    >>> next_attr("foo")
    ("foo", None)

    :param str item:
        The setting to get. E.g. 'bar' or 'foo.bar.baz'.

    :return tuple:
        Returns a tuple with (str, str) or (str, NoneType).

    :raise TypeError:
        If `item` is not a string.
    """
    if not isinstance(path, six.string_types):
        raise TypeError("Setting path must be string, not " + repr(type(path)))
    if '.' in path:
        return path.split('.', 1)
    return (path, None)


@six.python_2_unicode_compatible
class Configuration(object):
    """ An abstract configuration. """

    def __init__(self, init=dict()):
        """ Initialize a new configuration container.

        :param dict init:
            Initialize config with settings from dictionary.
        """
        self.load_dict(init)

    @classmethod
    def list_settings(cls):
        """ Lists all settings in this class. """
        return [attr for attr in dir(cls)
                if isinstance(getattr(cls, attr), settings.Setting)]

    @classmethod
    def get_setting(cls, item):
        """ Gets a setting instance. """
        attr, rest = next_attr(item)
        setting = getattr(cls, attr)
        if rest:
            value = setting.get_value()
            if not isinstance(value, Configuration):
                raise AttributeError(
                    "{!r} object in {!r} has no setting"
                    " {!r}".format(type(value).__name__, attr, rest)
                )
            return value.get_setting(rest)
        return setting

    @classmethod
    def list_ns_settings(cls):
        """ Generate a list of all settings in all Namespaces. """
        for attr in cls.list_settings():
            s = cls.get_setting(attr)
            if isinstance(s, Namespace):
                for nsattr in s._cls.list_ns_settings():
                    yield "{}.{}".format(attr, nsattr)
            else:
                yield attr

    def __item(self, item):
        """ Helper method for fetching setting values.

        :param str item:
            The setting to fetch.

        :raise KeyError:
            If item does not exist.
        """
        attr, rest = next_attr(item)
        try:
            value = getattr(self, attr)
            if rest and not isinstance(value, Configuration):
                raise AttributeError()
            return value, rest
        except AttributeError:
            raise KeyError('No setting {!r} in config'.format(item))

    def __getitem__(self, item):
        value, rest = self.__item(item)
        if rest:
            return value[rest]
        return value

    def __setitem__(self, item, newval):
        value, rest = self.__item(item)
        if rest:
            value[rest] = newval
        else:
            setattr(self, item, newval)

    def __delitem__(self, item):
        value, rest = self.__item(item)
        if rest:
            del value[rest]
        else:
            delattr(self, item)

    @classmethod
    def documentation(cls):
        """ Generate a formatted, multiline documentation string. """
        doc = settings.ConfigDocumentation(cls)
        for name in cls.list_settings():
            setting = cls.get_setting(name)
            doc[name] = setting.doc_struct
        return doc.format()

    def validate(self):
        """ Validate the settings in this configuration.

        :raises ConfigurationError:
            If validation of any settings fails.
        """
        errors = ConfigurationError()
        for name in self.list_settings():
            try:
                setting = self.get_setting(name)
                setting.validate(self[name])
            except Exception as e:
                errors.set_error(name, e)
        if errors:
            raise errors

    def dump_dict(self, flatten=False):
        """ Convert the config to a dictionary.

        :param bool flatten:
            If True, namespaces will be flattened out.

            Without flatten (default):
                { 'a': {'foo': 1, 'bar': 2}, 'b': {'foo': 1, 'bar': 2}, }

            With flatten:
                { 'a.foo': 1, 'a.bar': 2, 'b.foo': 1, 'b.bar': 2, }

        :return dict:
            A dict representation of this Configuration, with serialized
            values.
        """
        d = dict()
        for name in self.list_settings():
            setting = self.get_setting(name)
            # TODO: What about NotSet values?
            #       They should probably be serialized in some way?
            #       Could we give them some special string value that
            #       Setting recognizes?
            d[name] = setting.serialize(self[name])
        if flatten:
            d = _Odict(flatten_dict(d))
        return d

    def load_dict(self, d):
        """ Read in config values from a dictionary structure.

        :param dict d:
            A dictionary with serialized values.

            The dictionary keys are read in alphabetical order. This means that
            given the following dict:
                 { 'a.b.c': 1,
                   'a': {'b': {'c': 2}}, }

            we know that the value of 'a.b.c' is 1, because it is
            alphabetically sorted after 'a'.

        :raises ConfigurationError:
            If a dict contains keys that are not settings, or values that
            doesn't pass validation for a given setting.
        """
        errors = ConfigurationError()
        loaded_keys = set()
        for name, value in flatten_dict(d):
            if name in loaded_keys:
                errors.set_error(
                    name,
                    ValueError('Duplicate key {!r}'.format(name)))
                continue
            else:
                loaded_keys.add(name)

            if name not in self:
                errors.set_error(
                    name,
                    Exception('No setting for key {!r}'.format(name)))
                continue

            try:
                setting = self.get_setting(name)
                self[name] = setting.unserialize(value)
            except Exception as e:
                errors.set_error(name, e)
        if errors:
            raise errors

    def __iter__(self):
        for name in self.list_settings():
            yield name

    def __contains__(self, item):
        try:
            self.__item(item)
        except KeyError:
            return False
        return True

    def __eq__(self, other):
        # TODO: Does this have any real use?
        if type(self) != type(other):
            return False
        if any(n not in other for n in self):
            return False
        return all(self[n] == other[n] for n in self)

    def __ne__(self, other):
        # TODO: Does this have any real use?
        return not self.__eq__(other)

    def __len__(self):
        return len([n for n in self])

    def __bool__(self):
        # TODO: Does this have any real use?
        return bool(len(self))

    # PY2 backwards compatibility
    __nonzero__ = __bool__

    def __repr__(self):
        name = self.__class__.__name__
        init = repr(self.dump_dict())
        return "{}(init={})".format(name, init)

    def __str__(self):
        name = self.__class__.__name__
        keys = ', '.join((key for key in self))
        return "{}({})".format(name, keys)


class Namespace(settings.Setting):
    """ A setting that contains another Configuration. """

    # TODO: Could not Namespace and Configuration be the same class?

    _valid_types = Configuration

    def __init__(self, config=Configuration, doc="Namespace"):
        """ Initialize the Setting. """
        self._cls = config
        self._value = self.default

    @property
    def is_set(self):
        """ If the setting has been set. """
        return True

    @property
    def default(self):
        """ The default value of this Namespace (an empty Configuration). """
        return self._cls()

    @property
    def doc_struct(self):
        doc = settings.ConfigDocumentation(type(self))
        config = self.get_value()
        for name in config.list_settings():
            setting = config.get_setting(name)
            doc[name] = setting.doc_struct
        return doc

    def get_value(self):
        """ Gets the Configuration object of this Namespace. """
        return self._value

    def set_value(self, value):
        """ Replaces all values in this Namespace. """
        if isinstance(value, dict):
            value = self._cls(init=value)
        super(Namespace, self).set_value(value)

    def reset_value(self):
        """ Re-sets all values in this Namespace. """
        self._value = self.default

    def validate(self, value):
        """ Validate the value. """
        if isinstance(value, dict):
            value = self._cls(init=value)
        super(Namespace, self).validate(value)

        if not isinstance(value, self._cls):
            raise TypeError('Setting must be subtype of %r, got %r' %
                            (self._cls, type(value)))

        value.validate()

    def serialize(self, value):
        return value.dump_dict()

    def unserialize(self, value):
        newval = self.default
        newval.load_dict(value)
        return newval


class ConfigDescriptor(object):
    """ Wrap a Setting as a data descriptor. """

    def __init__(self, cls, **kwargs):
        """ Wraps a Setting as a data descriptor.

        :param Setting cls:
            The setting class of this descriptor.

        :param **dict kwargs:
            Init-arguments for `cls`.
        """
        if not issubclass(cls, settings.Setting):
            raise TypeError('Expected {}, got {}'.format(
                settings.Setting, cls))
        self.factory = lambda: cls(**kwargs)
        # The following does two things:
        #   1. Test that 'kwargs' are valid arguments for the class 'cls'
        #   2. Set __doc__ to the generated documentation for the attibute
        self.__doc__ = self.factory().doc

    @property
    def attr(self):
        """ Name of the attribute that stores the actual setting. """
        return '__ConfigDescriptor_setting_{:x}'.format(id(self))

    def get_instance(self, parent):
        """ Get an instance of this setting from the `parent' object .

        A Descriptor (self) is a class attribute, and so it gets shared between
        instances of the same type.

        We may want two instances of the same Configuration, but with different
        values. If so, we need to make sure that the actual Settings are stored
        in the Configuration object instance, and not in the class.

        This method makes sure that the actual Setting instance is lazily
        instantiated, and stored in a unique attribute in the `parent' object.

        :param object parent:
            An object whose type is using this object as a Descriptor.

        :return Setting:
            Fetches a `Setting' from `parent'. If no `Setting' exists for this
            Descriptor in `parent', one will get created.
        """
        if parent is None:
            return parent

        if not hasattr(parent, self.attr):
            setattr(parent, self.attr, self.factory())

        return getattr(parent, self.attr)

    def __get__(self, parent, parent_type=None):
        # Static call, get a _new_ instance of this Setting.
        if parent is None:
            return self.factory()

        setting = self.get_instance(parent)
        return setting.get_value()

    def __set__(self, parent, value):
        if parent is None:
            raise RuntimeError(
                '{} is read-only'.format(self.__class__.__name__))
        setting = self.get_instance(parent)
        setting.set_value(value)

    def __delete__(self, parent):
        if parent is None:
            raise RuntimeError(
                '{} is read-only'.format(self.__class__.__name__))
        setting = self.get_instance(parent)
        setting.reset_value()


def _main_demo():
    """
    A short example.
    """

    class Coordinate(Configuration):

        x = ConfigDescriptor(settings.Numeric, doc='x coordinate')
        y = ConfigDescriptor(settings.Numeric, doc='y coordinate')

    class Group(Configuration):

        foo = ConfigDescriptor(
            settings.String,
            regex='^Foo',
            maxlen=20,
            doc="A string that starts with 'Foo'")

        bar = ConfigDescriptor(
            settings.Numeric,
            minval=0,
            maxval=3,
            default=0.5,
            doc="A number.")

        coordinate = ConfigDescriptor(
            Namespace,
            config=Coordinate,
            doc='A coordinate for something')

    class Example(Configuration):

        group = ConfigDescriptor(
            Namespace,
            config=Group,
            doc="A setting group.")

        items = ConfigDescriptor(
            settings.Iterable,
            template=settings.String(maxlen=10, doc='10 chars'),
            max_items=10,
            doc='A list of strings')

    print("Documentation for Configuration 'Example'")
    print()
    print(Example.documentation())


if __name__ == '__main__':
    _main_demo()
