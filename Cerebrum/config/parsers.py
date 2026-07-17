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
"""
Common API for serializing and deserializing config files.

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
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import json
import os
import types

from Cerebrum.utils.module import load_source

# TODO: Implement registry using Cerebrum.utils.mappings

_parsers = {}


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


def list_extensions():
    return list(_parsers.keys())


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


try:
    import yaml

    @register_extension('yml', 'yaml')
    class YamlParser(_AbstractConfigParser):
        """ YAML Parser API.

        Wraps the PyYaml module with a common API.
        """

        @classmethod
        def loads(cls, data):
            # TODO: Decide if we actually want to use the FullLoader with all
            #  the functionality
            return yaml.load(data, Loader=yaml.FullLoader)

        @classmethod
        def dumps(cls, data):
            from collections import OrderedDict
            yaml.add_representer(
                OrderedDict,
                yaml.representer.SafeRepresenter.represent_dict)
            return yaml.dump(data)
except ImportError:
    pass


# TODO: We probably don't want to *register* this module,
# as it could lead to code execution from configs.
#
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
        module = load_source('_input_file', filename)
        data = {}
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
    def loads(cls, data):
        raise NotImplementedError("Not implemented")

    @classmethod
    def dumps(cls, data):
        raise NotImplementedError("Cannot write python code")


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
