#!/usr/bin/env python2
# encoding: utf-8
#
# Copyright 2014 University of Oslo, Norway
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
scripts. More specificly, this is done to isolate the ugliness of shared
pickles between UiO LDAP exports.

"""
from __future__ import with_statement
import sys
import pickle
import os.path

try:
    import mx.DateTime
    now = mx.DateTime.now
    delta = mx.DateTime.DateTimeDeltaFromSeconds
    ticks = mx.DateTime.DateTimeFromTicks
except ImportError:
    import datetime
    now = datetime.datetime.now
    delta = lambda s: datetime.timedelta(0, s)
    ticks = datetime.datetime.fromtimestamp

try:
    import cerebrum_path
    import cereconf
except ImportError:
    cereconf = object()

from Cerebrum.Utils import Factory, simple_memoize

_caches = dict()
_names = dict()


def get_cache_obj(name, db=None):
    """ Get the named cache, and update if it's older than max_age.

    :param DatabaseAccessor db: Database transaction for generating the Cache.
    :param str name: The name of the cache.
    :param int max_age: Max age in seconds.

    """
    Factory.get_logger("cronjob")
    db = db or Factory.get
    if name in _caches:
        cache = _caches[name]
    elif name in _names:
        cache = _names[name](db=db)
    else:
        raise NotImplementedError("No known cache %r" % name)
    _caches[name] = cache
    return cache


def get_cache(name, max_age, db=None):
    """ Get the named cache, and update if it's older than max_age.

    :param DatabaseAccessor db: Database transaction for generating the Cache.
    :param str name: The name of the cache.
    :param int max_age: Max age in seconds.

    """
    cache = get_cache_obj(name, db=db)
    cache.load()
    if cache.need_rebuild():
        cache.build()
    return cache


def get_cache_data(name, db=None):
    cache = get_cache(name, db=db)
    return cache.data


def write_cache(name, data):
    cache = get_cache_obj(name)
    cache.data = data
    cache.save()


def new_cache(new_cache, callback=None, seconds=None):
    def name_cache_cls(cls):
        class Cache(cls):
            name = new_cache
            if callable(callback):
                build_cb = staticmethod(callback)
            if seconds is not None:
                max_age = seconds
        _names[new_cache] = Cache
        return cls
    return name_cache_cls


class _Cache(object):

    dump_dir = getattr(cereconf,
                       'PICKLE_CACHE_DIR',
                       os.path.join(sys.prefix, 'var', 'cache'))

    build_cb = None

    def __init__(self, name, db=None):
        if db:
            self.__db = db
        self.name = name
        self.when = None
        self.clear_data()
        self.logger.debug("Initialized cache %r", self.name)

    def build(self):
        """ (Re)builds the cache.

        This decides what the cache actually should contain.

        """
        self.logger.debug("Rebuilding cache %r", self.name)
        if callable(self.build_cb):
            self.data = self.build_cb(self.db, self.logger)
        else:
            raise NotImplementedError("Cache %r has no rebuild method")
        self.when = now()
        self.save()
        self.logger.debug("Done rebuilding cache %r", self.name)

    def get_data(self):
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
                and (self.when + delta(self.max_age)) < now()):
            return True
        return False

    @property
    @simple_memoize
    def db(self):
        return Factory.get('Database')()

    @property
    @simple_memoize
    def logger(self):
        return Factory.get_logger('console')

    @property
    def filename(self):
        u""" Full path to the file where this cache should be stored. """
        return os.path.join(self.dump_dir,
                            'crb-cache-%s.pickle' % self.name)

    @property
    def updated(self):
        u""" The timestamp in human readable form. """
        return ticks(self.timestamp).strftime('%Y-%m-%d %H:%M:%S')

    @property
    def timestamp(self):
        u""" Timestamp for last changed. """
        if self.when is None:
            return 0
        return int(self.when.strftime('%s'))

    def save(self):
        u""" Save this cache as a pickle file. """
        if self._saved:
            return
        data = {'data': self.__data,
                'timestamp': self.timestamp, }
        with open(self.filename, 'w') as f:
            pickle.dump(data, f)
        self.logger.debug("Saved cache %r", self.filename)
        self._saved = True

    def load(self):
        u""" Try to load this cache from a pickle file. """
        try:
            with open(self.filename, 'r') as f:
                data = pickle.load(f)
            if 'data' in data and 'timestamp' in data:
                self.data = data['data']
                self.when = ticks(data['timestamp'] or 0)
                self.logger.debug("Loaded cache %r", self.filename)
                self._saved = True
                return True
        except:
            pass
        self.logger.debug("Unable to load cache %r", self.filename)
        return False

    def __repr__(self):
        return "Cache(name=%s, when=%s, file=%s)" % (self.name,
                                                     self.updated,
                                                     self.filename)

    def __str__(self):
        return repr(self)

    def __unicode__(self):
        return unicode(str(self), 'utf-8')


def fetch_accounts(db, logger):
    logger.debug("Fetching accounts")
    ac = Factory.get("Account")(db)
    accs = [dict(a) for a in ac.search()]
    logger.debug("Got %d accounts", len(accs))


@new_cache('account_example', callback=fetch_accounts, seconds=60)
class _ExampleAccountCache(_Cache):

    def __init__(self, **kwargs):
        super(_ExampleAccountCache, self).__init__(self.name, **kwargs)


@new_cache('student_letters')
class _StudentPasswordLetters(_Cache):

    """ Class for caching passwords for new students. """

    def __init__(self, **kwargs):
        super(_StudentPasswordLetters, self).__init__(self.name, **kwargs)


def main(args=None):
    """ Build a named cache. """
    try:
        import argparse
    except ImportError:
        import Cerebrum.extlib.argparse as argparse
    from Cerebrum.Utils import Factory
    logger = Factory.get_logger('cronjob')

    parser = argparse.ArgumentParser(description="Generate pickle caches.")
    parser.add_argument('-a', '--max-age',
                        dest='max_age',
                        metavar='SECONDS',
                        default=3600,
                        help='Max age in seconds')
    parser.add_argument('names',
                        metavar='NAME',
                        type=str,
                        nargs='+',
                        help='A cache name that should be generated')
    args = parser.parse_args(args)

    db = Factory.get('Database')()

    logger.info("Generating %d caches: %r", len(args.names), args.names)
    for name in args.names:
        logger.info("Generating cache %r", name)
        try:
            c = get_cache(name, args.max_age, db=db)
            print repr(c)
            c.save()
            import code
            code.interact(local=locals())
        except Exception, e:
            logger.error('Unable to build cache %r (%s): %s',
                         name, e.__class__.__name__, e, exc_info=e)


if __name__ == '__main__':
    main()
    del cerebrum_path
    del cereconf
