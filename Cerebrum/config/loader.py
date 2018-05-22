#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2015-2018 University of Oslo, Norway
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

"""Cerebrum module for loading configuration files.

This module contains functionality for finding and loading config files from
well-defined locations on the file system.

It is a bridge between the `parsers` module and the `configuration` module.


TODO: Improvements:

1. Improve error handling:
  - If multiple errors exist in config files, we should gather them up and
    present all the errors.
  - Reading config should be 'transactional'. If any errors exists, no
    configuration should be changed.
"""
from __future__ import unicode_literals

import logging
import os
import sys

from Cerebrum.config.configuration import Configuration
from . import parsers as _parsers


# Make it possible to override sys.prefix for configuration path purposes
sys_prefix = os.getenv('CEREBRUM_SYSTEM_PREFIX', sys.prefix)

# Default directory for global configuration files.
default_dir = os.getenv('CEREBRUM_CONFIG_ROOT',
                        os.path.join(sys_prefix, 'etc', 'cerebrum', 'config'))

# Default directory for user configuration files.
user_dir = os.path.join('~', '.cerebrum', 'config')

# Default name of the root configuration file.
default_root_ns = None

# Module logger
logger = logging.getLogger(__name__)


def _f2key(f):
    """ Get config namespace from filename. """
    return os.path.splitext(os.path.basename(f))[0]


def _f2ext(f):
    """ Get file extension from filename. """
    return os.path.splitext(f)[1].lstrip('.')


def is_readable_dir(path):
    """ Checks if path is a readable directory.

    :param str path:
        A file system path.

    :return bool:
        True if `path` is a readable and listable directory.
    """
    return (bool(path) and os.path.isdir(path) and
            os.access(path, os.R_OK | os.X_OK))


def lookup_dirs(additional_dirs=[]):
    """ Gets an ordered list of config directories.

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
    """ Update `config` with data from config files.

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
    logger.debug("read cls={t!r} root={r!r} dirs={d!r}"
                 "".format(t=type(config), r=root_ns, d=additional_dirs))

    def _get_config_files(confdir):
        """ yield config files from confdir. """

        def _file_sorter(a, b):
            """ sort files in confdir. """
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

    # TODO: Transactional update: Make a copy here, then update the copy

    for d in lookup_dirs(additional_dirs=additional_dirs):
        logger.debug('processing configs from {0}'.format(d))
        for f in _get_config_files(d):
            # logger.debug('considering {0}'.format(f))
            key = _f2key(f)
            # TODO: Handle errors here
            #       Also, maybe keep track of changes by files, warn if a file
            #       changes something that has already been set from another
            #       file?
            if key == root_ns:
                logger.debug('loading root using namespace {0!r}'.format(key))
                config.load_dict(read_config(f))
            elif key in config:
                # TODO: Find a more elegant way of handling nested structures
                if not isinstance(config[key], Configuration):
                    continue
                logger.debug('loading namespace {0!r}'.format(key))
                config[key].load_dict(read_config(f))

    # TODO: Then validate the copy, and write changes back to the original
    # config object to complete the 'transaction'.


def read_config(filename):
    """ Read a config file.

    :param str filename:
        The config filename.

    :return:
        The structured data from `filename`.
    """
    parser = _parsers.get_parser(filename)
    logger.debug("read_config parser={p!r} filename={f!r}"
                 "".format(f=filename, p=parser))
    return parser.read(filename)
