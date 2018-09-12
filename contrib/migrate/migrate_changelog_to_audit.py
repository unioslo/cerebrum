from __future__ import absolute_import, print_function

import Queue
import argparse
import collections
import functools
import logging
import os
import threading

import pytz
import six

import cereconf

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum import Cache
from Cerebrum.Constants import _CerebrumCode, SynchronizedDatabase
from Cerebrum.DatabaseAccessor import DatabaseAccessor
from Cerebrum.Entity import Entity, EntityName
from Cerebrum.Utils import Factory
from Cerebrum.modules.audit import auditdb
from Cerebrum.modules.audit import auditlog
from Cerebrum.modules.audit import record
from Cerebrum.utils import json


# TODO: Change to cronjob?
DEFAULT_LOG_PRESET = 'console'
SCRIPT = os.path.basename(__file__).replace('.pyc', '.py').replace('.', '-')
logger = logging.getLogger(SCRIPT)


ENTITY_TYPE_NAMESPACE = getattr(cereconf, 'ENTITY_TYPE_NAMESPACE', dict())


def _get_mx_dst(mx_datetime):
    """ Figure out if DST is in effect on a given mx.DateTime object. """
    # We need to know this when the naive datetime hits an ambiguous time:
    # - in CET the clock strikes 02:05 twice when turning back the clocks.
    # - in CET the clock never strikes 02:05 when turing the clocks ahead.
    if mx_datetime.tz == 'CEST':
        return True
    if mx_datetime.tz == 'CET':
        return False
    return None


def _get_mx_timezone(mx_datetime):
    """ Translate mx.DateTime time zone name to something standardized. """
    timezone = mx_datetime.tz
    if timezone == 'CEST':
        # CEST is just CET with summer time
        # pytz-timezones will apply summer time correctly when localizing a
        # naive datetime objects.
        return 'CET'
    return timezone


def mx_to_datetime(mx_datetime):
    """ Transform an mx.DateTime object to a localized python datetime. """
    default_is_dst = _get_mx_timezone(mx_datetime)
    tz_candidate = _get_mx_timezone(mx_datetime)
    naive = mx_datetime.pydatetime()
    tz = pytz.timezone(tz_candidate)
    return tz.localize(naive, is_dst=default_is_dst)


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
        entity = Entity(self._db)
        try:
            entity.find(e_id)
            return six.text_type(self.co.EntityType(entity.entity_type))
        except Cerebrum.Errors.NotFoundError:
            return None

    entity_name_cache = CacheDescriptor('entity_name', size=10000)

    @entity_name_cache
    def _get_name(self, e_id, e_type):
        namespace = ENTITY_TYPE_NAMESPACE.get(six.text_type(e_type))
        if namespace is None:
            return None
        else:
            namespace = self.co.ValueDomain(namespace)
        entity = EntityName(self._db)
        try:
            entity.find(e_id)
            return entity.get_name(namespace)
        except Cerebrum.Errors.NotFoundError:
            return None

    def build_meta(self, change_type, operator_id, entity_id, target_id):
        change = six.text_type(change_type)
        operator_type = self._get_type(operator_id)
        operator_name = self._get_name(operator_id, operator_type)
        entity_type = self._get_type(entity_id)
        entity_name = self._get_name(entity_id, entity_type)
        target_type = self._get_type(target_id)
        target_name = self._get_name(target_id, target_type)
        return {
            'change': change,
            'operator_type': operator_type,
            'operator_name': operator_name,
            'entity_type': entity_type,
            'entity_name': entity_name,
            'target_type': target_type,
            'target_name': target_name,
        }


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

        timestamp = mx_to_datetime(row['tstamp'])
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


def change_id_range_type(value):
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


class Worker(threading.Thread):
    """Thread executing tasks from a given tasks queue"""

    def __init__(self, queue):
        super(Worker, self).__init__()
        self.rows = queue
        self.daemon = True
        self.errors = dict()
        self.stats = collections.Counter(ok=0, failed=0)
        self.err_stats = collections.Counter()
        self.db = Factory.get('Database')()
        self.migrate = ChangeLogMigrator(self.db)

    def run(self):
        logger.debug("Worker thread starting")
        while True:
            try:
                row_dct = self.rows.get(True, 5)
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
    queue_timeout = 10
    # 10 seconds * 60 tries -- we've tried to queue for 10 minutes!
    queue_max_tries = 60

    def __init__(self, numworkers, commit=False, stats_interval=None):
        self.rows = Queue.Queue(self.queue_max_size)
        self.workers = []
        self.commit = commit
        self.stats = collections.Counter()
        self.errors = dict()
        for _ in range(numworkers):
            worker = Worker(self.rows)
            self.workers.append(worker)
            worker.start()
        if stats_interval:
            self._stats = WorkerStats(self, float(stats_interval))
            self._stats.start()

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
        self._stats.cancel()

        for thread in self.workers:
            logger.info("Thread %r: %r", thread, thread.stats)
            if self.commit:
                logger.info("Commiting changes")
                thread.db.commit()
            else:
                logger.info("Rolling back changes")
                thread.db.rollback()
            self.stats.update(thread.stats)
            self.errors.update(thread.errors)

        if hasattr(self, '_stats'):
            logger.info("Waiting for stats thread to complete")
            self._stats.join(10)
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

    logger.info("queueing done, processing %d change_log records",
                total_events)
    pool.wait_completion()

    logger.info('processing done, target %d change_log records', total_events)
    logger.info('stats=%r, processed=%d, queued=%d',
                pool.stats, sum(pool.stats.values()), total_events)

    if args.commit:
        logger.info("Commiting changes")
        db.commit()
    else:
        logger.info("Rolling back changes")
        db.rollback()


DEFAULT_THREADS_NUM = 4
DEFAULT_THREADS_STATS_INVERVAL = 10.0
DEFAULT_CHUNK_SIZE = 100


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description="Migrate changelog records to the audit log")

    parser.add_argument(
        'change_ids',
        nargs='+',
        # type=change_id_type,
        type=change_id_range_type,
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

    grouping = parser.add_argument_group('processing options')
    grouping.add_argument(
        '-k', '--change-handler-key',
        dest='change_handler_key',
        type=str,
        default='cl_to_audit_log',
        help='Track processed records using %(metavar)s, '
             'default is %(default)s',
        metavar='KEY',
    )
    grouping.add_argument(
        '--chunk-size',
        type=int,
        default=DEFAULT_CHUNK_SIZE,
        help='process chunks of size %(metavar)s, default is %(default)s',
        metavar='N')

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
