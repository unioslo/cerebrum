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
"""
This module contains an abstract file cache object.

File caches are typically used to preserve data from one script/job to another,
or to prevent some expensive process from running too often.  Example use
cases:

1. Two separate LDAP exports that *really* should work in the same transaction.
   E.g. groups and members + users and memberships - to ensure the two agree on
   memberhips, the membership data can be generated once in a common
   transaction, and used by both jobs.

2. Some job collates data from Cerebrum and a second, slower system.  If the
   job needs to run often, we can reduce our dependency on the slow system by
   caching relevant data, and only rebuild the cache when needed.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import datetime
import json
import logging
import os
import pickle
import sys

import cereconf
from Cerebrum.utils import file_stream
from Cerebrum.utils import filelock
from Cerebrum.utils import reprutils
from Cerebrum.utils import date as date_utils
from Cerebrum.utils.descriptors import lazy_property

logger = logging.getLogger(__name__)


def default_build_callback(db):
    raise NotImplementedError("No cache build callback")


class FileCache(reprutils.ReprFieldMixin):
    """ Base cache class. Subclass for different dump formats. """

    # repr settings
    repr_id = False
    repr_module = False
    repr_fields = ("name", "updated", "filename")

    #
    # file extension - should be implemented by serialization mixins
    #
    filetype = "tmp"

    #
    # build_callback - should be replaced in subclass
    #
    build_callback = staticmethod(default_build_callback)

    #
    # cache name - should be set in subclass
    #
    name = None

    def __init__(self, db, max_age=None, dump_dir=None):
        if not self.name:
            raise NotImplementedError("No cache name")
        self.db = db
        self.max_age = max_age
        self._when = None
        self.saved = False
        if dump_dir:
            self.dump_dir = dump_dir
        del self.data
        logger.debug("Initialized cache %s (max_age=%s)",
                     repr(self.name), repr(self.max_age))

    def build(self):
        """ (Re)builds the cache.

        This decides what the cache actually should contain.
        """
        # FIXME: If there are multiple processes attempting to use the same,
        # outdated cache, they will race to rebuild the cache.
        logger.debug("Rebuilding cache %s", repr(self.name))
        self.data = self.build_callback(self.db)
        self._when = date_utils.now()
        self.save()
        logger.debug("Rebuilt cache %s", repr(self.name))

    @lazy_property
    def dump_dir(self):
        return getattr(cereconf, "CACHE_DIR",
                       os.path.join(sys.prefix, "var/cache"))

    @property
    def max_age(self):
        return self.__max_age

    @max_age.setter
    def max_age(self, value):
        if value and not isinstance(value, datetime.timedelta):
            # backwards compatibility - allow init from dict
            value = datetime.timedelta(**value)
        if value and value != abs(value):
            raise ValueError("max_age cannot be negative")
        self.__max_age = value

    @property
    def data(self):
        if self.__data is None:
            self.load()
        if self.need_rebuild():
            self.build()
        return self.__data

    @data.setter
    def data(self, data):
        self.__data = data
        self.saved = False

    @data.deleter
    def data(self):
        self.__data = None
        self.saved = False

    def need_rebuild(self, _now=None):
        """ check if the current cache needs a rebuild. """
        now = _now or date_utils.now()
        if self.__data is None:
            # No data - needs rebuild
            return True
        if not self._when:
            # No age info - needs rebuild
            return True
        if not self.max_age:
            # No time limit - always rebuild
            return True

        next_rebuild = self._when + self.max_age
        if self.max_age and next_rebuild < now:
            return True
        return False

    @property
    def filename(self):
        """ Full path to the file where this cache should be stored. """
        return os.path.join(self.dump_dir,
                            "cache-{}.{}".format(self.name, self.filetype))

    @property
    def updated(self):
        """ Last updated in as a human readable string, in the local tz. """
        when = date_utils.from_timestamp(self.timestamp)
        return when.isoformat()

    @property
    def timestamp(self):
        """ Timestamp for last changed. """
        if self._when:
            return int(date_utils.to_timestamp(self._when))
        return 0

    def __dump_dict(self):
        """ dump current cache to a serialized dict. """
        return {
            'data': self.__data,
            'timestamp': self.timestamp,
        }

    def __load_dict(self, content):
        """ load cache from a serialized dict. """
        # ensure that content is complete
        data = content['data']
        when = date_utils.from_timestamp(content['timestamp'] or 0)
        # override current data
        self.data = data
        self._when = when
        self.saved = True

    def save(self):
        """ Save this cache as a file. """
        if self.saved:
            return
        self.dumper(self.__dump_dict())
        logger.info("Saved cache %s to %s",
                    repr(self.name), repr(self.filename))
        self.saved = True

    def load(self):
        """ Try to load this cache from a file. """
        try:
            self.__load_dict(self.loader())
            logger.info("Loaded cache %s from %s (updated at %s)",
                        repr(self.name), repr(self.filename),
                        self.updated)
            return True
        except Exception:
            pass
        logger.error("Unable to load cache %s", repr(self.filename))
        return False

    def loader(self):
        """ Loads data from a file. Implement in a subclass. """
        raise NotImplementedError

    def dumper(self, data):
        """ Dumps data to a file. Implement in a subclass. """
        raise NotImplementedError

    def __repr__(self):
        return "Cache(name={}, when={}, file={})".format(self.name,
                                                         self.updated,
                                                         self.filename)


class PickleCache(FileCache):
    """ Cache using the Python pickle format. """

    filetype = "pickle"

    def loader(self):
        """ Loads data from a pickle file. """
        with filelock.ReadLock(self.filename + '.lock'):
            with file_stream.get_input_context(self.filename,
                                               encoding=None,
                                               stdin=None) as f:
                return pickle.loads(f.read())

    def dumper(self, data):
        """ Dumps data from a pickle file. """
        with filelock.WriteLock(self.filename + '.lock'):
            with file_stream.get_output_context(self.filename,
                                                encoding=None,
                                                stdout=None) as f:
                return f.write(pickle.dumps(data))


class JsonCache(FileCache):
    """ Cache using the JSON format. """

    filetype = "json"

    def loader(self):
        """ Loads data from a JSON file. """
        with filelock.ReadLock(self.filename + '.lock'):
            with file_stream.get_input_context(self.filename,
                                               encoding="utf-8",
                                               stdin=None) as f:
                return json.loads(f.read())

    def dumper(self, data):
        """ Dumps data to a JSON file. """
        encoding = None if str is bytes else "utf-8"
        with filelock.WriteLock(self.filename + '.lock'):
            with file_stream.get_output_context(self.filename,
                                                encoding=encoding,
                                                stdout=None) as f:
                json.dump(obj=data, fp=f, indent=2, sort_keys=True,)
                f.write("\n")
                f.flush()
