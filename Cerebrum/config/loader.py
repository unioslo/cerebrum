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


def read(config, rootname="config", additional_dirs=[]):
    """ Update `config` with data from config files.

    This function will:

       1. Look at each file in the first lookupdir.
       2. If a `<rootname>.<ext>` exists, parse and load into `config` (at root
          level).
       3. For each other file `<name>.<ext>`, sorted by the length of <name>
          length, load it into config[<name>] if config[<name>] exists.
          The name length ordering makes sure that `foo.<ext>` gets loaded
          _before `foo.bar.<ext>`.
       4. Repeat for next lookup dir.

    :param Configuration config:
        The configuration to update.

    :param str rootname:
        The name of this config.

    :param list additional_dirs:
        Additional directories to look for config files in. See `lookup_dirs`
        for more info.
    """
    def _get_config_files(confdir):
        """ Yield config files from confdir. """

        def _file_sorter(a, b):
            """ Sort files in confdir. """
            a, b = _f2key(a), _f2key(b)
            # The root config should always be first
            if a == rootname:
                return cmp(0, 1)  # a before b
            elif b == rootname:
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
            if key == rootname:
                config.load_dict(read_config(f))
            elif key in config:
                # TODO: Replace entire key?
                config[key] = read_config(f)


def read_config(filename):
    """ Read a config file.

    :param str filename:
        The config filename.

    :return:
        The structured data from `filename`.
    """
    parser = _parsers.get_parser(filename)
    return parser.read(filename)
