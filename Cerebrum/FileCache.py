#!/usr/bin/env python
# encoding: utf-8
#
# Copyright 2014-2015 University of Oslo, Norway
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
u""" This module contains utilities to fetch and cache large sets of data.

This is to avoid having to do similar, expensive lookups all over again in new
scripts. More specifically, this is done to isolate the ugliness of shared
pickles between LDAP exports.

"""

from __future__ import with_statement

import cerebrum_path
import cereconf

import sys
import os.path
import datetime
import pickle
import json

from Cerebrum.Utils import Factory
from Cerebrum.utils.filelock import (ReadLock,
                                     WriteLock)


class _FileCache(object):
    """ Base cache class. Subclass for different dump formats. """
    dump_dir = getattr(cereconf, 'CACHE_DIR', os.path.join(sys.prefix, 'var', 'cache'))
    build_callback = None

    def __init__(self, max_age=None, db=None, logger=None):
        assert hasattr(self, 'name')
        self.db = db or Factory.get('Database')()
        self.logger = logger or Factory.get_logger('cronjob')
        self.max_age = max_age
        self.when = None
        self.filetype = 'tmp'
        self.clear_data()
        self.logger.debug("Initialized cache {!r}, max age is {!r}".format(
            self.name, self.max_age))

    def build(self):
        """ (Re)builds the cache.

        This decides what the cache actually should contain.

        """
        self.logger.info("Rebuilding cache {!r}".format(self.name))
        if not callable(self.build_callback):
            raise NotImplementedError("Cache {!r} has no rebuild method".format(self.name))
        self.data = self.build_callback(db=self.db, logger=self.logger)
        self.when = datetime.datetime.now()
        self.save()
        self.logger.info("Done rebuilding cache {!r}".format(self.name))

    def get_data(self):
        if self.__data is None:
            self.load()
        if self.need_rebuild():
            self.build()
        return self.__data

    def set_data(self, data):
        self.__data = data
        self.saved = False

    def clear_data(self):
        self.__data = None
        self.saved = False

    data = property(get_data, set_data, clear_data)

    def need_rebuild(self):
        if self.__data is None:
            return True
        if self.when is None:
            return True
        if (self.max_age is not None
                and (self.when + datetime.timedelta(**self.max_age)) < datetime.datetime.now()):
            return True
        return False

    @property
    def filename(self):
        u""" Full path to the file where this cache should be stored. """
        return os.path.join(self.dump_dir, 'cache-{}.{}'.format(self.name, self.filetype))

    @property
    def updated(self):
        u""" The timestamp in human readable form. """
        return datetime.datetime.fromtimestamp(self.timestamp).strftime('%Y-%m-%d %H:%M:%S')

    @property
    def timestamp(self):
        u""" Timestamp for last changed. """
        if self.when is None:
            return 0
        return int(self.when.strftime('%s'))

    def save(self):
        u""" Save this cache as a file. """
        if self.saved:
            return
        data = {'data': self.__data,
                'timestamp': self.timestamp, }
        with WriteLock(self.filename + '.lock'):
            with open(self.filename, 'wb') as f:
                self.dumper(data=data, fp=f)
        self.logger.debug("Saved cache {!r}".format(self.filename))
        self.saved = True

    def load(self):
        u""" Try to load this cache from a file. """
        try:
            with ReadLock(self.filename + '.lock'):
                with open(self.filename, 'rb') as f:
                    data = self.loader(fp=f)
                if 'data' in data and 'timestamp' in data:
                    self.data = data['data']
                    self.when = datetime.datetime.fromtimestamp(data['timestamp'] or 0)
                    self.logger.info("Loaded cache {!r} from {}".format(
                        self.filename,
                        self.when.strftime('%c')))
                    self._saved = True
                    return True
        except:
            pass
        self.logger.error("Unable to load cache {!r}".format(self.filename))
        return False

    def loader(self, f):
        u""" Loads data from a file. Implement in a subclass. """
        raise NotImplementedError

    def dumper(self, data, f):
        u""" Dumps data to a file. Implement in a subclass. """
        raise NotImplementedError

    def __repr__(self):
        return "Cache(name={}, when={}, file={})".format(self.name,
                                                         self.updated,
                                                         self.filename)

    def __str__(self):
        return repr(self)

    def __unicode__(self):
        return unicode(str(self), 'utf-8')


class _PickleCache(_FileCache):
    """ Cache using the Python pickle format. """
    def __init__(self, **kwargs):
        super(_PickleCache, self).__init__(**kwargs)
        self.filetype = 'pickle'

    def loader(self, fp):
        """ Loads data from a pickle file. """
        return pickle.load(file=fp)

    def dumper(self, data, fp):
        """ Dumps data from a pickle file. """
        return pickle.dump(obj=data, file=fp)


class _JsonCache(_FileCache):
    """ Cache using the JSON format. """
    def __init__(self, **kwargs):
        super(_JsonCache, self).__init__(**kwargs)
        self.filetype = 'json'

    def loader(self, fp):
        """ Loads data from a JSON file. """
        return json.load(fp=fp)

    def dumper(self, data, fp):
        """ Dumps data to a JSON file. """
        return json.dump(obj=data, fp=fp, ensure_ascii=False)
