#!/usr/bin/env python
# -*- encoding: utf-8 -*-
""" Cerebrum config serializing module.

This module contains classes that wraps libraries for reading and writing
serializing formats with a common API.

The API (_AbstractConfigParser) consists of four methods:

dumps(data)
    Convert a basic data structure to a serialized string.
loads(string)
    Convert a serialized string into a basic data structure.
read(filename)
    Read a serialized file and unserialize.
write(data, filename)
    Serialize a data structure and write to file.
"""
from __future__ import print_function
import os
from io import BytesIO

# TODO: Split this into multiple modules
#
#   suggested structure
#
#     ./parsers/__init__.py -- {set,get,register}_parsers(), entry point lookup
#     ./parsers/base.py -- AbstractConfigParser
#     ./parsers/<module>.py -- yaml-parser

# TODO: Implement discovery by entry_points
#
#   We should implement parsers as 'plugins', and use setuptools/pkg_resources
#   to install and fetch implementations.
#
#     pkg_resources.iter_entry_points('Cerebrum.config.parsers') -> list of
#     entry points.
#
#   example implementation of a plugin lookup
#
#     def find_parser(ext):
#         " example implementation "
#         for ep in pkg_resources.iter_entry_points('Cerebrum.config.parsers',
#                                                   name=ext):
#             # iterate through entry points named 'ext'
#             try:
#                 return ep.load()
#             except:
#                 # maybe missing dependency? Let's try another if it exists
#                 continue
#         raise NotImplementedError("No parser found")
#
#   installing new plugins:
#
#       setup(
#         ...
#         entry_points={
#           'Cerebrum.config.parsers': [
#             'json = Cerebrum.modules.parsers.json:JsonParser',
#             'yml = Cerebrum.modules.parsers.yaml:YamlParser',
#             'yaml = Cerebrum.modules.parsers.yaml:YamlParser',
#           ],
#         },
#       )

# TODO: YAML 1.2 support
#
#   Look into replacing, or supplementing the YAML-parser with ruamel.yaml, for
#   YAML 1.2 support (http://yaml.readthedocs.io/en/)

_parsers = {}
""" Known file format parsers. """


class _AbstractConfigParser(object):
    """ Abstract config parser. """

    @classmethod
    def loads(cls, data):
        """ Loads a string

        :param str data:
            A serialized string to parse.

        :returns:
            Unserialized data.
        """
        raise NotImplementedError("Abstract class method")

    @classmethod
    def dumps(cls, data):
        """ Dumps data.

        :param str data:
            An unserialized structure to serialize.

        :returns str:
            A serialized string.
        """
        raise NotImplementedError("Abstract class method")

    @classmethod
    def read(cls, filename):
        """ Reads data from a file.

        :param str filename:
            The file to read.

        :returns:
            Unserialized data.
        """
        with open(filename, 'r') as f:
            return cls.loads(f.read())

    @classmethod
    def write(cls, data, filename):
        """ Writes data.

        :param data:
            The data structure to write.
        :param str filename:
            The file to write to.
        """
        with open(filename, 'w') as f:
            f.write(cls.dumps(data))


def set_parser(extension, parser):
    """ Registers a new parser for a file format.

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
            raise ValueError("Invalid parser {!r}, does not implement"
                             " {!r}".format(parser, attr))
    _parsers[extension] = parser


def get_parser(filename):
    """ Gets file parser for a given filename

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
            "No parser for filetype {!r} (file={})".format(ext, filename))
    return _parsers[ext]


def register_extension(*extensions):
    """ Register class as parser for file extensions.

    Usage:

      @register_extension('txt', 'dat')
      class TxtAndDatParser(_AbstractConfigParser):
          ...
    """
    def _set_parser_and_return_class(cls):
        for ext in extensions:
            set_parser(ext, cls)
        return cls
    return _set_parser_and_return_class


try:
    import json

    @register_extension('json')
    class JsonParser(_AbstractConfigParser):
        """ JSON Parser API.

        Wraps the json module with a common API.
        """

        @classmethod
        def loads(cls, data):
            return json.loads(data)

        @classmethod
        def dumps(cls, data):
            return json.dumps(data)
except ImportError:
    pass


try:
    import yaml

    @register_extension('yml', 'yaml')
    class YamlParser(_AbstractConfigParser):
        """ YAML Parser API.

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
except ImportError:
    pass


try:
    import bson

    @register_extension('bson')
    class BsonParser(_AbstractConfigParser):
        """ BSON Parser API.

        Wraps the bson module with a common API.
        """

        @classmethod
        def loads(cls, data):
            return bson.loads(data)

        @classmethod
        def dumps(cls, data):
            return bson.dumps(data)
except ImportError:
    pass


try:
    # PY2
    from ConfigParser import RawConfigParser
    from collections import OrderedDict
except ImportError:
    from configparser import RawConfigParser


# TODO: Do we want this?
# @register_extension('ini', 'conf', 'cfg')
class IniParser(_AbstractConfigParser):
    """ .ini/.conf ConfigParser-like files. """

    @classmethod
    def _readfp(cls, fp, filename=None):
        config = RawConfigParser()
        config.readfp(fp, filename)
        data = OrderedDict()
        for section in config.sections():
            data[section] = OrderedDict()
            for k, v in config.items(section):
                data[section][k] = v
        return data

    @classmethod
    def _writefp(cls, fp, data):
        config = RawConfigParser()
        for section_name, section in data.items():
            config.add_section(section_name)
            for k, v in section.items():
                config.set(section_name, k, v)
        config.write(fp)

    @classmethod
    def read(cls, filename):
        with open(filename, 'r') as fp:
            return cls._readfp(fp, filename)

    @classmethod
    def write(cls, data, filename):
        with open(filename, 'w') as fp:
            return cls._writefp(fp, data)

    @classmethod
    def loads(cls, data):
        strfp = BytesIO(data)
        return cls._readfp(strfp)

    @classmethod
    def dumps(cls, data):
        strfp = BytesIO()
        cls._writefp(strfp, data)
        strfp.seek(0)
        return strfp.read()


try:
    # PY2-only
    import imp
    import types

    # TODO: Do we want this?
    # @register_extension('py')
    class PyParser(_AbstractConfigParser):
        """ This is a special parser implementation that reads (imports) a
        python module, and turns it into a dict with the module globals.

        NOTE: It can only read python files, not strings, and it cannot write
        or dump. Also, it should be used with care, as the python files can
        execute anything.

        Names in the module globals that starts with underscore (_) will be
        excluded. Also, certain value types are excluded (`EXCLUDE_TYPES`).
        """

        # Exclude ModuleType, as this will mostly be imports. In configs, these
        # should probably be imported with a '_' prefix in the scope anyway,
        # but let's exclude them if we forget.
        EXCLUDE_TYPES = (types.ModuleType, )

        @classmethod
        def read(cls, filename):
            module = imp.load_source('_input_file', filename)
            data = dict()
            for attr in dir(module):
                if attr.startswith('_'):
                    continue
                value = getattr(module, attr)
                if isinstance(value, cls.EXCLUDE_TYPES):
                    continue
                data[attr] = value
            return data

        @classmethod
        def write(cls, data, filename):
            raise NotImplementedError("Cannot write python modules")

        @classmethod
        def loads(cls, data, filename):
            raise NotImplementedError("Not implemented")

        @classmethod
        def dumps(cls, data):
            raise NotImplementedError("Cannot write python code")
except:
    pass


# python -m Cerebrum.config.parsers


def make_parser():
    import argparse
    parser = argparse.ArgumentParser(
        description="Show available parsers or parse a file")
    parser.add_argument(
        'filename',
        nargs='?',
        help="Parse file and pretty-print result")
    return parser


def main(inargs=None):
    """ Print supported file formats. """
    args = make_parser().parse_args(inargs)
    try:
        from pprintpp import pprint
    except ImportError:
        from pprint import pprint

    def _fmt_cls(cls):
        mod = cls.__module__
        if mod == '__main__':
            mod = 'Cerebrum.config.parsers'
        return '{0}.{1}'.format(mod, cls.__name__)

    def _list():
        print("Supported file extensions:")
        for ext in sorted(_parsers):
            print('  *.{:8s} {!r}'.format(ext, _fmt_cls(_parsers[ext])))

    def _parse(filename):
        parser = get_parser(filename)
        data = parser.read(filename)
        pprint(data)

    if args.filename:
        _parse(args.filename)
    else:
        _list()


if __name__ == '__main__':
    main()
