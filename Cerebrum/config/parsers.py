#!/usr/bin/env python
# -*- encoding: utf-8 -*-
u""" Config file parsers. """

import os


_parsers = {}
u""" Config parsers. """


class _AbstractConfigParser(object):
    u""" Abstract config parser. """

    @classmethod
    def loads(cls, data):
        """ Loads data from string. """
        raise NotImplementedError("Abstract class method")

    @classmethod
    def dumps(cls, config):
        """ Dumps data to a string. """
        raise NotImplementedError("Abstract class method")

    @classmethod
    def read(cls, filename):
        """ Dumps the `config` to a string. """
        with open(filename, 'r') as f:
            return cls.loads(f.read())

    @classmethod
    def write(cls, data, filename):
        with open(filename, 'w') as f:
            f.write(cls.dumps(data))


def set_parser(extension, parser):
    u""" Registers a new config file parser. """
    for attr in dir(_AbstractConfigParser):
        if (callable(getattr(_AbstractConfigParser, attr)) and not
                callable(getattr(parser, attr, None))):
            raise ValueError(u"Invalid parser {!r}, does not implement"
                             u" {!r}".format(parser, attr))
    _parsers[extension] = parser


def get_parser(filename):
    u""" Gets config file parser. """
    ext = os.path.splitext(filename)[1].lstrip('.')
    if ext not in _parsers:
        raise NotImplementedError(
            u"No parser for filetype {!r} (file={})".format(ext, filename))
    return _parsers[ext]


try:
    import json

    class JsonParser(_AbstractConfigParser):

        """ A Configuration object that can read and write JSON. """

        @classmethod
        def loads(cls, data):
            return json.loads(data)

        @classmethod
        def dumps(cls, data):
            return json.dumps(data)

    set_parser('json', JsonParser)
except ImportError:
    pass


try:
    import yaml

    class YamlParser(_AbstractConfigParser):

        """ A Configuration object that can read and write JSON. """

        @classmethod
        def loads(cls, data):
            return yaml.load(data)

        @classmethod
        def dumps(cls, data):
            from collections import OrderedDict
            yaml.add_representer(
                OrderedDict,
                yaml.representer.SafeRepresenter.represent_dict)
            return yaml.dump(data)

    set_parser('yml', YamlParser)
except ImportError:
    pass
