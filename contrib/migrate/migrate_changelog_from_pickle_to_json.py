from __future__ import absolute_import, print_function

import Queue
import argparse
import collections
import six
import logging
import threading

try:
    import cPickle as pickle
except ImportError:
    import pickle

import cereconf

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Constants import _CerebrumCode, SynchronizedDatabase
from Cerebrum.DatabaseAccessor import DatabaseAccessor
from Cerebrum.Utils import Factory
from Cerebrum.utils.date import apply_timezone
from Cerebrum.utils.funcwrap import memoize
from Cerebrum.modules.ChangeLog import _params_to_db


DEFAULT_LOG_PRESET = 'cronjob'
logger = logging.getLogger(__name__)


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


class ChangeLogMigrator(DatabaseAccessor):
    """ Migrate change_log change_params from pickle to json. """

    @property
    def clconst(self):
        if not hasattr(self, '_clconst'):
            try:
                self._clconst = Factory.get('CLConstants')(self._db)
            except ValueError:
                self._clconst = Factory.get('Constants')(self._db)
        return self._clconst

    @memoize
    def get_change_type(self, code):
        return self.clconst.ChangeType(code)

    def fix_change_params(self, params):
        def fix_string(s):
            try:
                return s.decode('UTF-8')
            except UnicodeDecodeError:
                return s.decode('ISO-8859-1')

        def fix_mx(o):
            if o.hour == o.minute == 0 and o.second == 0.0:
                return six.text_type(o.pydate().isoformat())
            return six.text_type(apply_timezone(o.pydatetime()).isoformat())

        def fix_object(d):
            return dict(
                (self.fix_change_params(k), self.fix_change_params(v))
                for k, v in d.items())

        def fix_array(l):
            return list(map(self.fix_change_params, l))

        if isinstance(params, bytes):
            return fix_string(params)
        if isinstance(params, dict):
            return fix_object(params)
        if isinstance(params, (list, tuple)):
            return fix_array(params)
        if hasattr(params, 'pydate'):
            return fix_mx(params)
        # throw away any occurrences of <type 'type'>
        if params is type:
            return None
        return params

    def process_row(self, row):
        change_id = row['change_id']
        change_params = row['change_params']
        change_type_id = row['change_type_id']
        try:
            depickled = pickle.loads(change_params.encode('ISO-8859-1'))
        except Exception:
            logger.error("unable to deserialize change_params=%r",
                         change_params)
            raise
        new_params = self.fix_change_params(depickled)
        change_type = self.get_change_type(change_type_id)
        orig = change_type.format_params(new_params)
        new = change_type.format_params(_params_to_db(new_params))
        if orig != new:
            logger.error(u'Failed for change {}'.format(change_id))
            logger.error(u'Params: {}'.format(new_params))
            logger.error(u'Format spec: {}'.format(change_type.format))
            logger.error(u'Original: {}'.format(orig))
            logger.error(u'New: {}'.format(new))
            raise Exception()
        # self.logger.debug('changing %d from %r to %r',
        #                   change_id, depickled, new_params)
        self._db.update_log_event(change_id, new_params)


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
            logger.info("committing changes")
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

    def run(self):
        while not self.stop.wait(self.interval):
            self._log_stats()
            self._log_errors()
            self._log_queue_size()


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


def get_unprocessed_count():
    db = Factory.get('Database')()
    return db.query_1(
        "SELECT count(*) FROM change_log "
        "WHERE change_params IS NOT NULL "
        "AND change_params NOT LIKE :matcher",
        dict(matcher='{%'))


def queue_and_process(args):
    db = Factory.get("Database")()

    pool = ThreadPool(args.threads,
                      commit=args.commit,
                      stats_interval=args.stats)

    # queue the change_ids that actually exists and need to be processed
    total_rows = 0
    for min_id, max_id in args.process:
        logger.debug("processing %r - %r", min_id, max_id)
        rows = db.query(
            'SELECT change_id, change_params, change_type_id FROM '
            '[:table schema=cerebrum name=change_log] '
            'WHERE change_id >= :mn '
            'AND change_id <= :mx '
            'AND change_params IS NOT NULL '
            'AND change_params NOT LIKE :matcher',
            dict(mn=min_id, mx=max_id, matcher='{%'))
        for row in rows:
            pool.add_row(dict(row))
        num_rows = db.rowcount
        logger.debug("added %r rows", num_rows)
        total_rows += num_rows

    # Done queueing, just wait for worker threads to be done
    logger.info("queueing done, processing %d change_log records",
                total_rows)
    pool.wait_completion()

    logger.info('processing done, target %d change_log records', total_rows)
    stats = pool.get_stats()
    logger.info('queued=%d, processed=%d, stats=%r',
                total_rows, sum(stats.values()), stats)


def queue_and_process_unprocessed(args):
    db = Factory.get("Database")()

    pool = ThreadPool(args.threads,
                      commit=args.commit,
                      stats_interval=args.stats)

    # queue the change_ids that need to be processed
    total_rows = 0
    logger.debug("looking for up to %d changelog rows",
                 args.process_unprocessed)
    rows = db.query(
        'SELECT change_id, change_params, change_type_id FROM '
        '[:table schema=cerebrum name=change_log] '
        'WHERE change_params IS NOT NULL '
        'AND change_params NOT LIKE :matcher '
        'LIMIT :limit',
        dict(limit=args.process_unprocessed, matcher='{%'))
    for row in rows:
        pool.add_row(dict(row))
    num_rows = db.rowcount
    logger.debug("added %r rows", num_rows)
    total_rows += num_rows

    # Done queueing, just wait for worker threads to be done
    logger.info("queueing done, processing %d change_log records",
                total_rows)
    pool.wait_completion()

    logger.info('processing done, target %d change_log records', total_rows)
    stats = pool.get_stats()
    logger.info('queued=%d, processed=%d, stats=%r',
                total_rows, sum(stats.values()), stats)


def update_sql_metainfo():
    #unprocessed = get_unprocessed_count()
    #if unprocessed != 0:
    #    raise Exception(
    #        'Cannot update changelog version, still {} unprocessed'.format(
    #            unprocessed))
    from Cerebrum import Metainfo
    db = Factory.get("Database")()
    meta = Metainfo.Metainfo(db)
    meta.set_metainfo("sqlmodule_changelog", "1.4")
    db.commit()
    logger.info("changelog version set to 1.4")


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
        description="Migrate changelog record data from pickle to json")

    task_args = parser.add_argument_group('tasks (mutually exclusive)')
    task_args.add_argument(
        '-p', '--process',
        nargs='+',
        type=change_id_tuple_type,
        help='process specific change_ids (range N-M or single value N)')
    task_args.add_argument(
        '--count-unprocessed',
        action='store_true',
        help='count number of unprocessed changelog records')
    task_args.add_argument(
        '--mark-migration-complete',
        action='store_true',
        help=('marks migration from changelog 1.3 to 1.4 as complete if '
              'there are no unprocessed records'))
    task_args.add_argument(
        '--process-unprocessed',
        type=int,
        help='find and process up to N unprocessed changelog records',
        metavar='N')

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

    if args.count_unprocessed:
        logger.info('Counting unprocessed changelog records...')
        unprocessed = get_unprocessed_count()
        logger.info('Number of unprocessed records: %d', unprocessed)
    elif args.process_unprocessed is not None:
        queue_and_process_unprocessed(args)
    elif args.process is not None:
        queue_and_process(args)
    elif args.mark_migration_complete:
        update_sql_metainfo()
    else:
        logger.info('Nothing to do')

    logger.info('Done with script %s', parser.prog)


if __name__ == '__main__':
    main()
