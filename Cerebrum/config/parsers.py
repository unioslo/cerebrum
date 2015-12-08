#!/usr/bin/env python
# -*- encoding: utf-8 -*-
u""" Cerebrum config serializing module.

This module contains classes that wraps libraries for reading and writing
serializing formats with a common API.

The API (_AbstractConfigParser) consists of four methods:

dumps
    Convert a basic data structure to a serialized string.
loads
    Convert a serialized string into a basic data structure.
read
    Read a serialized file and unserialize.
write
    Serialize a data structure and write to file.

"""

import os


_parsers = {}
u""" Known file format parsers. """


class _AbstractConfigParser(object):
    u""" Abstract config parser. """

    @classmethod
    def loads(cls, data):
        u""" Loads a string

        :param str data:
            A serialized string to parse.

        :returns:
            Unserialized data.
        """
        raise NotImplementedError("Abstract class method")

    @classmethod
    def dumps(cls, data):
        u""" Dumps data.

        :param str data:
            An unserialized structure to serialize.

        :returns str:
            A serialized string.
        """
        raise NotImplementedError("Abstract class method")

    @classmethod
    def read(cls, filename):
        u""" Reads data from a file.

        :param str filename:
            The file to read.

        :returns:
            Unserialized data.
        """
        with open(filename, 'r') as f:
            return cls.loads(f.read())

    @classmethod
    def write(cls, data, filename):
        u""" Writes data.

        :param data:
            The data structure to write.
        :param str filename:
            The file to write to.
        """
        with open(filename, 'w') as f:
            f.write(cls.dumps(data))


def set_parser(extension, parser):
    u""" Registers a new parser for a file format.

    :param str extension:
        The file extension to use this parser for.
    :param type parser:
        An _AbstractConfigParser-like type.

    :raises ValueError:
        If `parser` does not implement the methods of _AbstractConfigParser.
    """
    for attr in dir(_AbstractConfigParser):
        if (callable(getattr(_AbstractConfigParser, attr)) and not
                callable(getattr(parser, attr, None))):
            raise ValueError(u"Invalid parser {!r}, does not implement"
                             u" {!r}".format(parser, attr))
    _parsers[extension] = parser


def get_parser(filename):
    u""" Gets file parser for a given filename

    :param str filename:
        Path to, or filename of the file to parse.

    :return type:
        A _AbstractConfigParser-like parser type.

    :raises NotImplementedError:
        If no parser exists for the given filename.
    """
    ext = os.path.splitext(filename)[1].lstrip('.')
    if ext not in _parsers:
        raise NotImplementedError(
            u"No parser for filetype {!r} (file={})".format(ext, filename))
    return _parsers[ext]


try:
    import json

    class JsonParser(_AbstractConfigParser):
        u""" JSON Parser API.

        Wraps the json module with a common API.
        """

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
        u""" YAML Parser API.

        Wraps the PyYaml module with a common API.
        """

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
