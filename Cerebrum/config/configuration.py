#!/usr/bin/env python
# encoding: utf-8
""" Configuration container.

Configuration-subclasses are configuration-specifications. They contain rules
and default values for settings.

Configuration-objects are containers for actual configuration. A
configuration-object can be serialized and un-serialized.

Mixin-classes for the `Configuration` class enables config file reading and
writing.

"""
from collections import OrderedDict

from . import settings
from .errors import ConfigurationError


class _odict(OrderedDict):

    u""" OrderedDict with `dict` repr. """

    def __repr__(self):
        return super(OrderedDict, self).__repr__()


class Configuration(object):

    """ An abstract configuration. """

    def __init__(self, init=dict()):
        """ Initialize a new, empty config. """
        self.load_dict(init)

    @staticmethod
    def __split_path(item):
        """ Splits `item` by the path separator ('.').

        This is a helper function to help recusing when fetching a
        dot-separated setting.

        :param str item:
            The setting to get. E.g. 'bar' or 'foo.bar.baz'.

        :return tuple:
            Returns a tuple with (str, str) or (str, NoneType).

            If the `item` is the name of a setting, e.g. 'foo', the return
            value will be ('foo', None).

            If the `item` is the name of a namespaced setting, e.g.
            'foo.bar.baz', the return value will be ('foo', 'bar.baz').

        :raise TypeError:
            If `item` is not a string.

        """
        if not isinstance(item, (str, unicode)):
            raise TypeError(
                u'Config settings must be strings, not {}'.format(type(item)))
        rest = None
        if '.' in item:
            item, rest = item.split('.', 1)
        return item, rest

    @classmethod
    def list_settings(cls):
        """ Lists all settings in this class. """
        return filter(
            lambda attr: isinstance(getattr(cls, attr), settings.Setting),
            dir(cls))

    @classmethod
    def get_setting(cls, item):
        """ Gets a setting instance. """
        attr, rest = cls.__split_path(item)
        setting = getattr(cls, attr)
        if rest:
            value = setting.get_value()
            if not isinstance(value, Configuration):
                # TODO: What is the correct exception type here?
                #       get_setting should never be called if the item does not
                #       exist...
                raise Exception(
                    "get_setting: {!r} has no {!r}".format(attr, rest))
            return value.get_setting(rest)
        return setting

    def __item(self, item):
        """ Helper method, raises KeyError if item does not exist. """
        attr, rest = self.__split_path(item)
        try:
            value = getattr(self, attr)
            if rest and not isinstance(value, Configuration):
                raise AttributeError()
            return value, rest
        except AttributeError:
            raise KeyError("No setting {!r} in config".format(item))

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
        doc = settings.ConfigDocumentation(cls)
        for name in cls.list_settings():
            setting = cls.get_setting(name)
            doc[name] = setting.doc_struct
        return doc.format()

    def validate(self):
        errors = ConfigurationError()
        for name in self.list_settings():
            try:
                setting = self.get_setting(name)
                setting.validate(self[name])
            except Exception as e:
                errors.set_error(name, e)
        if errors:
            raise errors

    def dump_dict(self, flatten=False, order=True):
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
        d = _odict()
        for name in sorted(self.list_settings()):
            if isinstance(self[name], Configuration) and flatten:
                dd = self[name].dump_dict(flatten=flatten, order=order)
                for kk, vv in dd.iteritems():
                    d['%s.%s' % (name, kk)] = vv
            else:
                setting = self.get_setting(name)
                # TODO: What about NotSet values?
                #       They should probably be serialized in some way?
                #       Could we give them some special string value that
                #       Setting recognizes?
                d[name] = setting.serialize(self[name])
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

        """
        errors = ConfigurationError()
        for name in sorted(d):
            try:
                setting = self.get_setting(name)
                self[name] = setting.unserialize(d[name])
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
        if type(self) != type(other):
            return False
        if any(n not in other for n in self):
            return False
        return all(self[n] == other[n] for n in self)

    def __len__(self):
        return len([n for n in self])

    def __nonzero__(self):
        # TODO: Does this have any real use?
        return bool(len(self))

    def __repr__(self):
        return "{}(init={!r})".format(
            self.__class__.__name__,
            self.dump_dict())

    def __str__(self):
        return "{}({})".format(
            self.__class__.__name__,
            ', '.join((key for key in self)))

    def __unicode__(self):
        return u"{}({})".format(
            self.__class__.__name__,
            u', '.join((key for key in self)))


# TODO: Should the file read/write rather be a separate class? E.g.:
#         foo = Configuraiton()
#         foo.load_dict(JsonConfig.read('filename'))
#         JsonConfig.write('filename', foo)


class Namespace(settings.Setting):

    """ A setting that contains another Configuration. """

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
        """ Validate the value.  """
        if isinstance(value, dict):
            value = self._cls(init=value)
        super(Namespace, self).validate(value)

        if not isinstance(value, self._cls):
            raise TypeError("Setting must be subtype of %r, got %r" %
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
        if not issubclass(cls, settings.Setting):
            raise TypeError(u'Expected {}, got {}'.format(
                settings.Setting, cls))
        self.cls = cls
        self.factory = lambda: cls(**kwargs)
        self.ident = id(self.factory)
        # The following does two things:
        #   1. Test that 'kwargs' are valid arguments for the class 'cls'
        #   2. Set __doc__ to the generated documentation for the attibute
        self.__doc__ = self.factory().doc

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

        # A reasonably unique attribute name
        attr = '__ConfigDescriptor_setting_{:x}'.format(self.ident)

        if not hasattr(parent, attr):
            setattr(parent, attr, self.factory())

        return getattr(parent, attr)

    def __get__(self, parent, parent_type=None):
        # Static call, get a _new_ instance of this Setting.
        if parent is None:
            return self.factory()

        setting = self.get_instance(parent)
        return setting.get_value()

    def __set__(self, parent, value):
        if parent is None:
            # TODO: is there a valid use-case for this?
            raise Exception("Shouldn't happen!")
        setting = self.get_instance(parent)
        setting.set_value(value)

    def __delete__(self, parent):
        if parent is None:
            # TODO: is there a valid use-case for this?
            raise Exception("Shouldn't happen!")
        setting = self.get_instance(parent)
        setting.reset_value()


def _example():

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
            setting=settings.String(maxlen=10, doc='10 chars'),
            max_items=10,
            doc='A list of strings')

    return Coordinate, Group, Example


if __name__ == '__main__':

    co, gr, ex = _example()
    print u"Documentation for Configuration 'Example'\n"
    print ex.documentation()
