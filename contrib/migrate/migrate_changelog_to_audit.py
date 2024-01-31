#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2018-2023 University of Oslo, Norway
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
""" Populate mod_auditlog from mod_changelog. """
from __future__ import (
    absolute_import,
    division,
    print_function,
)

import Queue
import argparse
import collections
import functools
import logging
import threading

import cereconf

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum import Cache
from Cerebrum.Constants import _CerebrumCode, SynchronizedDatabase
from Cerebrum.DatabaseAccessor import DatabaseAccessor
from Cerebrum.Utils import Factory
from Cerebrum.modules.audit import auditdb
from Cerebrum.modules.audit import auditlog
from Cerebrum.modules.audit import record
from Cerebrum.utils import date_compat
from Cerebrum.utils import json


DEFAULT_LOG_PRESET = 'cronjob'
logger = logging.getLogger(__name__)
ENTITY_TYPE_NAMESPACE = getattr(cereconf, 'ENTITY_TYPE_NAMESPACE', dict())


#
# This is a hack to get around thread-safety issues with _CerebrumCode.sql
#
class _SqlDescriptor(object):
    """ An alternative implementation of _CerebrumCode.sql

    This implementation does not use ping() to figure out if a new
    SynchronizedDatabase() needs to be created. Rather, it creates a
    SynchronizedDatabase() and uses it for the rest of the lifetime of
    _CerebrumCode.

    This avoids some threading issues with the database and
    SynchronizedDatabase - which really isn't thread safe.
    """

    def fget(self, obj):
        """ property compatible __get__. """
        with _CerebrumCode._db_proxy_lock:
            if _CerebrumCode._private_db_proxy is None:
                _CerebrumCode._private_db_proxy = SynchronizedDatabase()
            return _CerebrumCode._private_db_proxy

    def fset(self, obj, value):
        """ property compatible __set__. """
        with _CerebrumCode._db_proxy_lock:
            _CerebrumCode._private_db_proxy = value

    def __get__(self, obj, cls=None):
        if obj is None:
            return self
        return self.fget(obj)

    def __set__(self, obj, value):
        return self.fset(obj, value)


_CerebrumCode.sql = _SqlDescriptor()


class CacheDescriptor(object):
    """ A descriptor that can be used to cache method results. """

    def __init__(self, name, size=500):
        self.name = name
        self.size = size

    @property
    def cache_name(self):
        return '_cache__{name}_{id:02x}'.format(name=self.name, id=id(self))

    @property
    def stats_name(self):
        return '_stats__{name}_{id:02x}'.format(name=self.name, id=id(self))

    def _make_cache(self):
        return Cache.Cache(mixins=[Cache.cache_mru, Cache.cache_slots],
                           size=self.size)

    def _make_stats(self):
        return collections.Counter(hits=0, misses=0)

    def get_cache(self, obj):
        if not hasattr(obj, self.cache_name):
            setattr(obj, self.cache_name, self._make_cache())
        return getattr(obj, self.cache_name)

    def get_stats(self, obj):
        if not hasattr(obj, self.stats_name):
            setattr(obj, self.stats_name, self._make_stats())
        return getattr(obj, self.stats_name)

    def __get__(self, obj, cls=None):
        """ fetch the hits/misses statistics. """
        if obj is None:
            return self
        return self.get_stats(obj)

    def __repr__(self):
        return ('{cls.__name__}'
                '({obj.name!r},'
                ' size={obj.size!r}'
                ')').format(cls=type(self), obj=self)

    def __call__(self, func):
        """ cache decorator. """
        @functools.wraps(func)
        def wrapper(bound_obj, *args):
            cache = self.get_cache(bound_obj)
            stats = self.get_stats(bound_obj)
            if args in cache:
                stats['hits'] += 1
                result = cache[args]
            else:
                stats['misses'] += 1
                cache[args] = result = func(bound_obj, *args)
            return result
        return wrapper


class AuditRecordBuilder(auditlog.AuditRecordBuilder):
    """ AuditRecordBuilder that caches db lookups.

    The regular AuditRecordBuilder needs to look up entity_types and
    entity_names in the database each time it is needed, as the values may have
    changed.

    The one used for migration does not need to do this, and would be able to
    benefit from a cache to reduce the number of methods.
    A cache is used here to avoid having the *entire* entity_type and
    entity_name tables in memory, allthough that may be even quicker.
    """

    entity_type_cache = CacheDescriptor('entity_type', size=10000)

    @entity_type_cache
    def _get_type(self, e_id):
        return super(AuditRecordBuilder, self)._get_type(e_id)

    entity_name_cache = CacheDescriptor('entity_name', size=10000)

    @entity_name_cache
    def _get_name(self, e_id, e_type):
        return super(AuditRecordBuilder, self)._get_name(e_id, e_type)


class ChangeLogMigrator(DatabaseAccessor):
    """ Migrate change_log records into audit_log records. """

    @property
    def initial_account_id(self):
        if not hasattr(self, '_default_op'):
            account = Factory.get('Account')(self._db)
            account.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
            self._default_op = account
        return self._default_op.entity_id

    @property
    def builder(self):
        if not hasattr(self, '_audit_record_builder'):
            self._audit_record_builder = AuditRecordBuilder(self._db)
        return self._audit_record_builder

    @property
    def auditlog(self):
        if not hasattr(self, '_audit_log_accessor'):
            self._audit_log_accessor = auditdb.AuditLogAccessor(self._db)
        return self._audit_log_accessor

    def row_to_record(self, row):
        """ Build a DbAuditRecord from a change_log db_row. """

        def int_or_none(v):
            return v if v is None else int(v)

        timestamp = date_compat.get_datetime_tz(row['tstamp'])
        change_id = int(row['change_id'])

        if row['change_by'] is None:
            change_by = self.initial_account_id
        else:
            change_by = int(row['change_by'])

        change_params = row['change_params']
        try:
            if not change_params:
                change_params = {}
            else:
                change_params = json.loads(change_params)
        except Exception:
            logger.warn("unable to deserialize change_params=%r",
                        change_params)
            raise

        record_data = self.builder(
            int(row['subject_entity']),
            int(row['change_type_id']),
            int_or_none(row['dest_entity']),
            change_params,
            change_by,
            row['change_program'],
        ).to_dict()

        record_data['record_id'] = change_id
        record_data['timestamp'] = timestamp

        return record.DbAuditRecord.from_dict(record_data)

    def process_row(self, row):
        record = self.row_to_record(row)
        logger.debug('got record %r, with metadata=%r',
                     record, record.metadata)
        self.auditlog.append(record)


class Worker(threading.Thread):
    """Thread executing tasks from a given tasks queue"""

    timeout = 5

    def __init__(self, queue, commit=False):
        super(Worker, self).__init__()
        self.rows = queue
        self.commit = commit
        self.daemon = True
        self.errors = dict()
        self.stats = collections.Counter(ok=0, failed=0)
        self.stop = threading.Event()
        self.err_stats = collections.Counter()
        self.db = Factory.get('Database')()
        self.migrate = ChangeLogMigrator(self.db)

    def cancel(self):
        self.stop.set()

    def run(self):
        logger.debug("Worker thread starting")
        while not self.stop.is_set():
            try:
                row_dct = self.rows.get(True, self.timeout)
            except Queue.Empty:
                logger.warn("queue is empty")
                continue

            try:
                self.migrate.process_row(row_dct)
                self.stats['ok'] += 1
            except Exception as e:
                logger.error('unable to process %r', row_dct, exc_info=True)
                self.errors[row_dct['change_id']] = e
                self.err_stats[type(e).__name__] += 1
                self.stats['failed'] += 1
            finally:
                self.rows.task_done()

        logger.info("statistics: %r", self.stats)
        if self.commit:
            logger.info("commiting changes")
            self.db.commit()
        else:
            logger.info("rolling back changes")
            self.db.rollback()
        logger.info("thread done")


class WorkerStats(threading.Thread):
    """ Thread that periodically inspects workers and logs statistics.  """

    def __init__(self, pool, interval):
        super(WorkerStats, self).__init__(name='StatsThread')
        self.daemon = True
        self.threads = pool.workers
        self.queue = pool.rows
        self.stop = threading.Event()
        self.interval = interval

    def cancel(self):
        self.stop.set()

    def _log_stats(self):
        stats = collections.Counter()
        for th in self.threads:
            logger.debug('processed[%s]: %r', th.name, th.stats)
            stats.update(th.stats)
        logger.info('processed: %r', stats)

    def _log_errors(self):
        total = 0
        stats = collections.Counter()
        for th in self.threads:
            errs = len(th.errors)
            st = dict(th.err_stats)
            logger.debug('errors[%s]: %r', th.name, stats)
            stats.update(st)
            total += errs
        logger.info('errors: %r', stats)

    def _log_queue_size(self):
        size = self.queue.qsize()
        logger.info("queue size: %r items", size)

    def _log_caches(self):
        type_stats = collections.Counter()
        name_stats = collections.Counter()
        for th in self.threads:
            type_stats.update(th.migrate.builder.entity_type_cache)
            name_stats.update(th.migrate.builder.entity_name_cache)
        logger.info('cache name=%r type=%r', name_stats, type_stats)

    def run(self):
        while not self.stop.wait(self.interval):
            self._log_stats()
            self._log_errors()
            self._log_queue_size()
            self._log_caches()


class ThreadPool(object):
    """ Pool of threads consuming tasks from a queue. """

    queue_max_size = 10000
    queue_max_tries = 60
    queue_timeout = 10

    def __init__(self, numworkers, commit=False, stats_interval=None):
        self.rows = Queue.Queue(self.queue_max_size)
        self.workers = []
        self.errors = dict()
        for _ in range(numworkers):
            worker = Worker(self.rows, commit=commit)
            self.workers.append(worker)
            worker.start()
        if stats_interval:
            self._stats_thread = WorkerStats(self, float(stats_interval))
            self._stats_thread.start()
        else:
            self._stats_thread = None

    def get_stats(self):
        stats = collections.Counter()
        for th in self.workers:
            stats.update(th.stats)
        return stats

    def get_error_stats(self):
        errors = collections.Counter()
        for th in self.workers:
            errors.update(th.err_stats)
        return errors

    def add_row(self, row_dct):
        """Add a task to the queue"""
        try:
            for next_attempt in range(self.queue_max_tries - 1, -1, -1):
                try:
                    self.rows.put(row_dct, True, self.queue_timeout)
                    break
                except Queue.Full:
                    if next_attempt:
                        continue
                    else:
                        raise
        except Exception:
            logger.error('unable to add task', exc_info=True)

    def wait_completion(self):
        """Wait for completion of all the tasks in the queue"""
        logger.info("Waiting for workers to complete")
        self.rows.join()
        logger.info("Workers done")

        logger.info("Stopping threads")
        if self._stats_thread:
            self._stats_thread.cancel()
        for thread in self.workers:
            thread.cancel()

        logger.info("Waiting for threads to complete")
        for thread in self.workers:
            logger.info("... waiting for thread %r", thread)
            # Depending on number of changes, this could take a while -- it
            # needs to commit everything here.
            thread.join()

        if self._stats_thread:
            logger.info("... waiting for stats thread")
            self._stats_thread.join(self._stats_thread.interval + 1)
        logger.info("Threads completed")


def queue_and_process(args):
    db = Factory.get("Database")()

    pool = ThreadPool(args.threads,
                      commit=args.commit,
                      stats_interval=args.stats)

    # queue the change_ids that actually exists
    total_events = 0
    for min_id, max_id in args.change_ids:
        logger.debug("processing %r - %r", min_id, max_id)
        num_events = 0
        for num_events, row in enumerate(
                db.get_log_events(start_id=min_id, max_id=max_id),
                1):
            pool.add_row(dict(row))
        logger.debug("added %r rows", num_events)
        total_events += num_events

    # Done queueing, just wait for worker threads to be done
    logger.info("queueing done, processing %d change_log records",
                total_events)
    pool.wait_completion()

    logger.info('processing done, target %d change_log records', total_events)
    stats = pool.get_stats()
    logger.info('queued=%d, processed=%d, stats=%r',
                total_events, sum(stats.values()), stats)


def change_id_tuple_type(value):
    """ strval to ints.

    >>> list(change_id_type('8'))
    (8, 8)
    >>> list(change_id_type('3-5'))
    (3, 5)
    """
    start, _, end = value.partition('-')
    start = int(start)
    if end:
        end = int(end)
        return (start, end)
    else:
        return (start, start)


DEFAULT_THREADS_NUM = 4
DEFAULT_THREADS_STATS_INVERVAL = 10.0
DEFAULT_CHUNK_SIZE = 100


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description="Migrate changelog records to the audit log")

    parser.add_argument(
        'change_ids',
        nargs='+',
        type=change_id_tuple_type,
        help='change_id to process (range N-M or single value N)')

    commit_mutex = parser.add_mutually_exclusive_group()
    commit_mutex.add_argument(
        '-c', '--commit',
        dest='commit',
        action='store_true',
        help='commit changes')
    commit_mutex.add_argument(
        '-r', '--dryrun',
        dest='commit',
        action='store_false',
        help='dry run (do not commit -- this is the default)')
    commit_mutex.set_defaults(commit=False)

    threading_args = parser.add_argument_group('threading')
    threading_args.add_argument(
        '--threads',
        type=int,
        default=DEFAULT_THREADS_NUM,
        help='use %(metavar)s threads, default is %(default)s',
        metavar='N')
    threading_args.add_argument(
        '--stats',
        type=float,
        default=DEFAULT_THREADS_STATS_INVERVAL,
        help='report statistics every %(metavar)s seconds, '
             'default is %(default)s',
        metavar='N')

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf(DEFAULT_LOG_PRESET, args)

    logger.info('Start of script %s', parser.prog)
    logger.debug("args: %r", args)

    queue_and_process(args)

    logger.info('Done with script %s', parser.prog)


if __name__ == '__main__':
    main()
