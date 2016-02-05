#!/usr/bin/env python
# -*- coding: utf-8 -*-
u""" Cerebrum setting module.

Settings are validators and containers for individual configuration values.

They can have default values, validation rules and transforms for serializing
and unserializing.

In addition, all settings contains a `doc` attribute that should contain a
string that describes the behavior of the setting and its uses.

"""
import re
from collections import OrderedDict


class NotSetType(object):

    u""" A NotSet type that indicates that nothing has been set. """

    def __nonzero__(self):
        return False

    def __str__(self):
        return 'NotSet'

    def __unicode__(self):
        return u'NotSet'

    def __repr__(self):
        return str(self)

NotSet = NotSetType()
u""" Singleton that indicates that a setting has not been set. """


class ConfigDocumentation(OrderedDict):
    u""" A container and formatter for structured documentation.

    This class is used when building documentation for a Setting. It contains
    rules, default values and other interesting facts about a Setting in an
    OrderedDict.

    In addition, it implements a `format` method that formats that information
    as a string.
    """

    doc_indent = u'  | '
    u""" Indent for the formatted documentation string. """

    def __init__(self, setting_type):
        u""" Initialize a documentation container.

        :param type setting_type:
            The type of the Setting that this dict-like object documents.
        """
        self._setting_type = setting_type
        super(ConfigDocumentation, self).__init__()

    def __str__(self):
        return self.format()

    def format(self, indent=u'    ', _count=1):
        u""" Formats the data contained in this dict-like object.

        :param unicode indent:
            The indent to use for facts contained in this structure.

        :param int _count:
            Recursion count (number of indents to use).

        :return unicode:
            Returns a formatted documentation string.
        """
        doc = [unicode(self._setting_type)]
        for k, v in self.iteritems():
            if isinstance(v, type(self)):
                v = v.format(indent=indent, _count=_count + 1)
            doc += [u'{}: {}'.format(k, v)]
        return u"\n{}".format(indent * _count).join(doc)


class Setting(object):
    u""" Generic setting."""

    _valid_types = None
    u""" The valid value class or classes that this setting accepts.

    Either None (accept all classes), a type or a tuple of types. """

    def __init__(self, default=NotSet, doc=""):
        u""" Configure a new Setting.

        :param default:
            Default value to return if no value has been set.
            If set to None, this setting will be considered an 'optional'
            setting.

        :param basestring doc:
            A short text that explains the usage for this setting.
        """
        self.default = default
        self._doc = doc
        self._value = NotSet
        if default is not NotSet and default is not None:
            self.validate(default)

    @property
    def is_set(self):
        u""" If the setting has been set. """
        if self._value is NotSet:
            return False
        return True

    @property
    def doc_struct(self):
        u""" Structured documentation for this setting.

        :return ConfigDocumentation:
            An OrderedDict that implements a __str__ method.
        """
        doc = ConfigDocumentation(type(self))
        doc['description'] = self._doc
        if self.default is not NotSet:
            doc['default'] = repr(self.default)
        if self._valid_types:
            doc['types'] = repr(self._valid_types)
        return doc

    @property
    def doc(self):
        u""" Documentation string for this setting. """
        return self.doc_struct.format()

    def get_value(self, default=NotSet):
        u""" Gets the value of this setting.

        :param default:
            A value to return if the setting has no value or default set.
        """
        if self.is_set:
            return self._value
        if default is NotSet:
            return self.default
        return default

    def set_value(self, value):
        u""" Validates and sets the value of this setting.

        :param value:
            The value to set.
        """
        self.validate(value)
        self._value = value

    def reset_value(self):
        u""" Removes any value set for this setting. """
        self._value = NotSet

    def validate(self, value):
        u""" Validates a value.

        This check ensures that the value is of a valid type.

        :param value:
            The value to validate.

        :return bool:
            Returns True if the value does not need further validation.

        :raises TypeException:
            If value is not an instance of the valid types for this setting.
        """
        if self.default is None and value is None:
            return True
        if self._valid_types is None:
            return False
        if isinstance(value, self._valid_types):
            return False

        raise TypeError(
            u'Invalid type {} for setting {}, must be (one of): {}'.format(
                type(value), self.__class__, repr(self._valid_types)))

    def serialize(self, value):
        u""" Serialize the given value. """
        return value

    def unserialize(self, value):
        u""" Unserialize the given value. """
        return value


class Numeric(Setting):
    u""" Numerical setting. """

    _valid_types = (int, long, float)

    def __init__(self, minval=None, maxval=None, **kw):
        u""" Configure a numeric setting.

        :param numeric minval:
            Specify a lower limit for values.
        :param numeric maxval:
            Specify an upper limit for values.
        :param **dict kw:
            See `Setting` for additional keyword arguments.
        """
        self._minval = minval
        self._maxval = maxval
        super(Numeric, self).__init__(**kw)

    @property
    def doc_struct(self):
        doc = super(Numeric, self).doc_struct
        if self._minval is not None:
            doc['min'] = self._minval
        if self._maxval is not None:
            doc['max'] = self._maxval
        return doc

    def validate(self, value):
        u""" Validates a value.

        :see: Setting.validate

        :raises ValueError:
            If value is not within the bounds of minval and maxval
        """
        if super(Numeric, self).validate(value):
            return True
        if self._minval is not None and self._minval > value:
            raise ValueError(
                u'Invalid value {}, must not be less than {}'.format(
                    value, self._minval))
        if self._maxval is not None and self._maxval < value:
            raise ValueError(
                u'Invalid value {}, must not be greater than {}'.format(
                    value, self._maxval))
        return False


class Integer(Numeric):
    u""" A whole number setting. """

    _valid_types = (int, long)


class String(Setting):
    u""" A String setting. """

    _valid_types = (str, unicode)

    def __init__(self, regex=None, minlen=None, maxlen=None, **kw):
        u""" Configure a string setting.

        :param string regex:
            A regex rule for this setting.
        :param int minlen:
            Specify a minimum string length for values.
        :param int maxlen:
            Specify a maximum string length for values.
        :param **dict kw:
            See `Setting` for additional keyword arguments.
        """
        if regex:
            self._regex = re.compile(regex)
        else:
            self._regex = None
        self._minlen = minlen
        self._maxlen = maxlen
        super(String, self).__init__(**kw)

    def validate(self, value):
        u""" Validates a value.

        :see: Setting.validate

        :raises ValueError:
            If the string value does not pass the configured regex, or is
            shorter or longer than the specified limits.
        """
        if super(String, self).validate(value):
            return True
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
        return False

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
    u""" Choice setting with limited options. """

    def __init__(self, choices=set(), **kw):
        u""" Configure a choice setting.

        :param set choice:
            A set of valid values.
        :param **dict kw:
            See `Setting` for additional keyword arguments.
        """
        if not isinstance(choices, set):
            raise TypeError(
                u"Invalid argument 'choices' ({}) must be {}".format(
                    type(choices), set))
        self._choices = choices
        super(Choice, self).__init__(**kw)

    def validate(self, value):
        u""" Validates a value.

        :see: Setting.validate

        :raises ValueError:
            If the value is not one of the pre-configured choices.
        """
        if super(Choice, self).validate(value):
            return True
        if value not in self._choices:
            raise ValueError(
                u'Invalid value {!r}, must be one of {!r}'.format(
                    value, self._choices))
        return False

    @property
    def doc_struct(self):
        doc = super(Choice, self).doc_struct
        doc['choices'] = repr(self._choices)
        return doc


class Boolean(Setting):
    u""" Boolean setting. """

    _valid_types = (bool, )


class Iterable(Setting):
    u""" List value. """

    _valid_types = (list, set, tuple)

    def __init__(self, template=Setting(), min_items=None, max_items=None, **kw):
        u""" Configure a list setting.

        :param Setting template:
            Template setting for items in this setting. The setting will be
            used to validate and serialize/unserialize items in the value of
            this setting (default 'None' - not enforced).
        :param min_items:
            Minimum number of items in the value of this setting
            (default 'None' - not enforced).
        :param max_items:
            Maximum number of items in the value of this setting
            (default 'None' - not enforced).
        :param **dict kw:
            See `Setting` for additional keyword arguments.
        """
        if not isinstance(template, Setting):
            raise TypeError(
                u"Invalid argument 'template' ({}) must be {}".format(
                    type(template), Setting))
        self._template = template
        self._min_items = min_items
        self._max_items = max_items
        super(Iterable, self).__init__(**kw)

    def get_value(self, default=NotSet):
        value = super(Iterable, self).get_value(default=default)
        if isinstance(value, self._valid_types):
            value = list(value)
        return value

    def set_value(self, value):
        if isinstance(value, self._valid_types):
            value = list(value)
            for idx, item in enumerate(value):
                self._template.set_value(item)
                value[idx] = self._template.get_value()

        super(Iterable, self).set_value(value)

    def validate(self, value):
        u""" Validate a value.

        :see: Setting.validate

        :raises ValueError:
            If the value contains too few or too many items.
        :raises:
            Will raise any exception that the template setting will raise.
        """
        if super(Iterable, self).validate(value):
            return True
        if self._min_items is not None and self._min_items > len(value):
            raise ValueError(
                u'Invalid value {}, must have at least {} items'.format(
                    value, self._min_items))
        if self._max_items is not None and self._max_items < len(value):
            raise ValueError(
                u'Invalid value {}, must have at most {} items'.format(
                    value, self._max_items))
        for item in value:
            self._template.validate(item)
        return False

    @property
    def doc_struct(self):
        doc = super(Iterable, self).doc_struct
        doc['template'] = self._template.doc_struct
        if self._min_items is not None:
            doc['min items'] = self._min_items
        if self._max_items is not None:
            doc['max items'] = self._max_items
        return doc

    def serialize(self, value):
        u""" Serialize each item according to any template setting. """
        return [self._template.serialize(item) for item in value]

    def unserialize(self, value):
        u""" Unserialize each item according to any template setting. """
        return [self._template.unserialize(item) for item in value]