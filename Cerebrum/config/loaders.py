#!/usr/bin/env python
# -*- encoding: utf-8 -*-
u""" Config file utils. """

import sys
import os
from . import parsers as _parsers


default_dir = os.path.join(sys.prefix, 'etc', 'cerebrum', 'config')
u""" Default config dir. """

user_dir = os.path.join('~', '.cerebrum', 'config')
u""" Default user config dir. """

root_filename = None
u""" The name of the root config file. """


_f2key = lambda f: os.path.splitext(os.path.basename(f))[0]
u""" Translate filename to config key name. """

_f2ext = lambda f: os.path.splitext(f)[1].lstrip('.')
u""" Translate filename to extension key name. """


def is_readable_dir(path):
    u""" Return True if directory is readable. """
    return (bool(path) and os.path.isdir(path)
            and os.access(path, os.R_OK | os.X_OK))


def lookup_dirs(additional_dirs=[]):
    u""" Ordered list of directories to look for configs in. """
    return filter(
        is_readable_dir,
        map(lambda d: os.path.abspath(os.path.expanduser(d)),
            [default_dir, user_dir] + additional_dirs))


def read(config, additional_dirs=[], names=[]):
    for d in lookup_dirs(additional_dirs=additional_dirs):
        for f in _get_config_files(d, names=names):
            key = _f2key(f)
            if key in names:
                config = read_config(f)
            elif key in config:
                config[key] = read_config(f)


def _file_sorter(names):
    def _cmp(a, b):
        a = _f2key(a)
        b = _f2key(b)

        # root_filename should always be first
        if a in names and b in names:
            return cmp(a, b)
        elif a in names:
            return cmp(0, 1)
        elif b in names:
            return cmp(1, 0)

        # Otherwise, we use the string length to select read order. This is
        # the same way that config assignment works.
        return cmp(len(a), len(b))
    return _cmp


def _get_config_files(confdir, names=[]):
    u""" Return an ordered list of files to read. """
    # Do we have config files that match a specific thing?
    files = map(lambda f: os.path.join(confdir, f),
                filter(lambda f: not f.startswith(os.path.extsep),
                       os.listdir(confdir)))
    files.sort(_file_sorter(names))
    for f in files:
        yield f


def read_config(filename):
    parser = _parsers.get_parser(filename)
    return parser.read(filename)
