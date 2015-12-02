#!/usr/bin/env python
# encoding: utf-8
""" Configuration settings.

Settings are containers for individual configuration values.

They can have default values, rules and transforms for serializing and
unserializing.

In addition, all settings should contain a `doc` attribute that contains a
string that describes the behavoir of the setting.

"""
import re
from collections import OrderedDict


class NotSetType(object):

    """ A NotSet type that indicates that nothing has been set. """

    def __nonzero__(self):
        return False

    def __str__(self):
        return 'NotSet'

    def __unicode__(self):
        return u'NotSet'

    def __repr__(self):
        return str(self)

NotSet = NotSetType()
""" Singleton that indicates that a setting has not been set. """


class ConfigDocumentation(OrderedDict):

    """ A structured documentation class. """

    doc_indent = u'  | '
    """ Indent for the documentation string. """

    def __init__(self, setting_type):
        """ TODO

        :param type setting_type:
            A type for the documentation.
        """
        self._setting_type = setting_type
        super(ConfigDocumentation, self).__init__()

    def __str__(self):
        return self.format()

    def format(self, indent=u'    ', _count=1):
        doc = [unicode(self._setting_type)]
        for k, v in self.iteritems():
            if isinstance(v, type(self)):
                v = v.format(indent=indent, _count=_count + 1)
            doc += [u'{}: {}'.format(k, v)]
        return u"\n{}".format(indent * _count).join(doc)


class Setting(object):

    """ Generic setting. """

    _valid_types = None
    """ The valid value class or classes that this setting accepts. Either
    None (accept all classes), a Type or an iterable of Types. """

    def __init__(self, default=NotSet, doc=""):
        """ Initialize the Setting. """
        if default is not NotSet:
            self.validate(default)
        self.default = default
        self._doc = doc
        self._value = NotSet
        self.__doc__ = self.doc

    @property
    def is_set(self):
        """ If the setting has been set. """
        if self._value is NotSet:
            return False
        return True

    @property
    def doc_struct(self):
        doc = ConfigDocumentation(type(self))
        doc['description'] = self._doc
        if self.default is not NotSet:
            doc['default'] = repr(self.default)
        if self._valid_types:
            doc['types'] = repr(self._valid_types)
        return doc

    @property
    def doc(self):
        return self.doc_struct.format()

    def get_value(self, default=NotSet):
        """ Gets the value of this setting. """
        if self.is_set:
            return self._value
        if default is NotSet:
            return self.default
        return default

    def _load_value(self, value):
        return value

    def set_value(self, value):
        """ Validates and sets the value of this setting. """
        value = self._load_value(value)
        self.validate(value)
        self._value = value

    def reset_value(self):
        self._value = NotSet

    def validate(self, value):
        """ Validate the value.

        This function checks that the value matches the class requirements:
         - If _valid_types is None, all classes are accepted.
         - If _valid_types is a type or tuple of types, the value must be an
         instance of those classes.

        :value: Any value
        :raises TypeError: If _valid_types is not None (accept all types), and
        value is not an instance of any class in a set of Types

        If a subclass needs to limit the value, it should call super (this
        methdo), and implement a check that raises ValueError.

        """
        value = self._load_value(value)
        if self._valid_types is None:
            return
        if isinstance(value, self._valid_types):
            return

        raise TypeError(
            u'Invalid type {} for setting {}, must be (one of): {}'.format(
                type(value), self.__class__, repr(self._valid_types)))

    def serialize(self, value):
        return value

    def unserialize(self, value):
        return value


class Numeric(Setting):

    """ Numerical setting. """
    # TODO: Should we try to cast the setting?

    _valid_types = (int, long, float)

    def __init__(self, minval=None, maxval=None, **kwargs):
        if minval and not isinstance(minval, self._valid_types):
            raise TypeError(
                u'Invalid type {} for minval, must be one of [{}]'.format(
                    type(minval), repr(self._valid_types)))
        if maxval and not isinstance(maxval, self._valid_types):
            raise TypeError(
                u'Invalid type {} for maxval, must be one of [{}]'.format(
                    type(maxval), repr(self._valid_types)))
        self._minval = minval
        self._maxval = maxval
        super(Numeric, self).__init__(**kwargs)

    @property
    def doc_struct(self):
        doc = super(Numeric, self).doc_struct
        if self._minval is not None:
            doc['min'] = self._minval
        if self._maxval is not None:
            doc['max'] = self._maxval
        return doc

    def validate(self, value):
        super(Numeric, self).validate(value)
        if self._minval is not None and self._minval > value:
            raise ValueError(
                u'Invalid value {}, must not be less than {}'.format(
                    value, self._minval))
        if self._maxval is not None and self._maxval < value:
            raise ValueError(
                u'Invalid value {}, must not be greater than {}'.format(
                    value, self._maxval))


class Integer(Numeric):

    _valid_types = int


class String(Setting):

    """ String setting. """

    _valid_types = (str, unicode)

    def __init__(self, regex=None, minlen=None, maxlen=None, **kwargs):
        if regex:
            self._regex = re.compile(regex)
        else:
            self._regex = None
        self._minlen = minlen
        self._maxlen = maxlen
        super(String, self).__init__(**kwargs)

    def validate(self, value):
        super(String, self).validate(value)
        if self._minlen and self._minlen > len(value):
            raise ValueError(
                u'Invalid value {!r} of length {}, must be at least {}'.format(
                    value, self._minlen))
        if self._maxlen and self._maxlen < len(value):
            raise ValueError(
                u'Invalid value {!r} of length {}, must be at most {}'.format(
                    value, self._maxlen))
        if self._regex and not self._regex.match(value):
            raise ValueError(
                u'Invalid value {!r}, must pass regex {!r}'.format(
                    value, self._regex.pattern))

    @property
    def doc_struct(self):
        doc = super(String, self).doc_struct
        if self._minlen is not None:
            doc['min length'] = self._minlen
        if self._maxlen is not None:
            doc['max length'] = self._maxlen
        if self._regex is not None:
            doc['regex'] = '/{!s}/'.format(self._regex.pattern)
        return doc


class Choice(Setting):

    def __init__(self, choices=set(), **kwargs):
        if not isinstance(choices, set):
            raise TypeError(
                u"Invalid argument 'choices' ({}) must be {}".format(
                    type(choices), set))
        self._choices = choices
        super(Choice, self).__init__(**kwargs)

    def validate(self, value):
        super(Choice, self).validate(value)
        if value not in self._choices:
            raise ValueError(
                u'Invalid value {!r}, must be one of {!r}'.format(
                    value, self._choices))

    @property
    def doc_struct(self):
        doc = super(Choice, self).doc_struct
        doc['choices'] = repr(self._choices)
        return doc


class Iterable(Setting):

    """ Callback value. """

    _valid_types = (list, set, tuple)

    def __init__(self, setting=None, min_items=None, max_items=None, **kwargs):
        self._setting = setting
        self._min_items = min_items
        self._max_items = max_items
        super(Iterable, self).__init__(**kwargs)

    def get_value(self, default=NotSet):
        value = super(Iterable, self).get_value(default=default)
        if isinstance(value, self._valid_types):
            value = list(value)
        return value

    def set_value(self, value):
        """ Validates and sets the value of this setting. """
        if isinstance(value, self._valid_types):
            value = list(value)
            if self._setting is not None:
                for idx, item in enumerate(value):
                    self._setting.set_value(item)
                    value[idx] = self._setting.get_value()

        super(Iterable, self).set_value(value)

    def validate(self, value):
        super(Iterable, self).validate(value)
        if self._min_items is not None and self._min_items > len(value):
            raise ValueError(
                u'Invalid value {}, must have at least {} items'.format(
                    value, self._min_items))
        if self._max_items is not None and self._max_items < len(value):
            raise ValueError(
                u'Invalid value {}, must have at most {} items'.format(
                    value, self._max_items))
        if self._setting is not None:
            for item in value:
                self._setting.validate(item)

    @property
    def doc_struct(self):
        doc = super(Iterable, self).doc_struct
        if self._setting is not None:
            doc['item'] = self._setting.doc_struct
        if self._min_items is not None:
            doc['min items'] = self._min_items
        if self._max_items is not None:
            doc['max items'] = self._max_items
        return doc

    def serialize(self, value):
        if self._setting is not None:
            return [self._setting.serialize(item) for item in value]
        return value

    def unserialize(self, value):
        if self._setting is not None:
            return [self._setting.unserialize(item) for item in value]
        return value
