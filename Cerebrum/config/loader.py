#!/usr/bin/env python
# -*- encoding: utf-8 -*-
u""" Cerebrum module for loading configuration files.

This module contains functionality for finding and loading config files from
well-defined locations on the file system.

It is a bridge between the `parsers` module and the `configuration` module.


TODO: Improvements:

1. Improve the namespace writing. Don't overwrite the entire namespace when
   loading a namespace.
2. Improve error handling:
  - If multiple errors exist in config files, we should gather them up and
    present all the errors.
  - Reading config should be 'transactional'. If any errors exists, no
    configuration should be changed.
"""
import sys
import os
from . import parsers as _parsers


default_dir = os.path.join(sys.prefix, 'etc', 'cerebrum', 'config')
u""" Default directory for global configuration files. """

user_dir = os.path.join('~', '.cerebrum', 'config')
u""" Default directory for user configuration files. """

default_root_ns = None
u""" Default name of the root configuration file. """


_f2key = lambda f: os.path.splitext(os.path.basename(f))[0]
u""" Get config namespace from filename. """

_f2ext = lambda f: os.path.splitext(f)[1].lstrip('.')
u""" Get file extension from filename. """


def is_readable_dir(path):
    u""" Checks if path is a readable directory.

    :param str path:
        A file system path.

    :return bool:
        True if `path` is a readable and listable directory.
    """
    return (bool(path) and os.path.isdir(path)
            and os.access(path, os.R_OK | os.X_OK))


def lookup_dirs(additional_dirs=[]):
    u""" Gets an ordered list of config directories.

    :param list additional_dirs:
        Include directories in the list, if they are `readable`.

    :return list:
        A prioritized list of real, accessible directories.
    """
    return filter(
        is_readable_dir,
        map(lambda d: os.path.abspath(os.path.expanduser(d)),
            [default_dir, user_dir] + additional_dirs))


def read(config, root_ns=default_root_ns, additional_dirs=[]):
    u""" Update `config` with data from config files.

    This function will:

       1. Look at each file in the first lookupdir.
       2. If a `<root_ns>.<ext>` exists, parse and load into `config` (at root
          level).
       3. For each other file `<name>.<ext>`, sorted by the length of <name>
          length, load it into config[<name>] if config[<name>] exists.
          The name length ordering makes sure that `foo.<ext>` gets loaded
          _before `foo.bar.<ext>`.
       4. Repeat for next lookup dir.

    :param Configuration config:
        The configuration to update.

    :param str root_ns:
        The namespace of this configuration.

    :param list additional_dirs:
        Additional directories to look for config files in. See `lookup_dirs`
        for more info.
    """
    def _get_config_files(confdir):
        u""" Yield config files from confdir. """

        def _file_sorter(a, b):
            u""" Sort files in confdir. """
            a, b = _f2key(a), _f2key(b)
            # The root config should always be first
            if a == root_ns:
                return cmp(0, 1)  # a before b
            elif b == root_ns:
                return cmp(1, 0)  # b before a
            # Otherwise, we use the string length to select read order.
            return cmp(len(a), len(b))

        # Do we have config files that match a specific thing?
        files = map(lambda f: os.path.join(confdir, f),
                    filter(lambda f: not f.startswith(os.path.extsep),
                           os.listdir(confdir)))
        files.sort(_file_sorter)
        for f in files:
            yield f

    for d in lookup_dirs(additional_dirs=additional_dirs):
        for f in _get_config_files(d):
            key = _f2key(f)
            # TODO: Keep track of changes by files, warn if a file changes
            # something that has already been set from another file?
            if key == root_ns:
                config.load_dict(read_config(f))
            elif key in config:
                # TODO: Replace entire key?
                config[key] = read_config(f)


def read_config(filename):
    u""" Read a config file.

    :param str filename:
        The config filename.

    :return:
        The structured data from `filename`.
    """
    parser = _parsers.get_parser(filename)
    return parser.read(filename)
