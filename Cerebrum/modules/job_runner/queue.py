# -*- coding: utf-8 -*-

# Copyright 2018 University of Oslo, Norway
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
""" Job Runner queue. """
import logging
import os
import signal
import time

from Cerebrum import Errors
from .job_config import reload_job_config


current_time = time.time()
logger = logging.getLogger(__name__)


class DbQueueHandler(object):
    """ Database module that tracks last_run time. """

    def __init__(self, db):
        self.db = db
        self.logger = logger.getChild('DbQueueHandler')

    def get_last_run(self):
        """ Get all known last run times.

        :return dict:
            Return a dictionary that maps job names/ids to timestamps.
        """
        ret = {}
        for r in self.db.query(
                """
                SELECT id, timestamp
                FROM [:table schema=cerebrum name=job_ran]
                """):
            ret[r['id']] = r['timestamp'].ticks()
        self.logger.debug("get_last_run: %r", ret)
        return ret

    def update_last_run(self, job, timestamp):
        """ Set last run time for a job.

        :param str job:
            The job id/title.
        :param int timestamp:
            The timestamp when the job ran
        """
        timestamp = self.db.TimestampFromTicks(int(timestamp))
        self.logger.debug("update_last_run(%r, %r)" % (job, timestamp))

        try:
            self.db.query_1(
                """
                SELECT 'yes' AS yes
                FROM [:table schema=cerebrum name=job_ran]
                WHERE id=:id""",
                {'id': job})
        except Errors.NotFoundError:
            self.db.execute(
                """
                INSERT INTO [:table schema=cerebrum name=job_ran]
                (id, timestamp)
                VALUES (:id, :timestamp)""",
                {'id': job, 'timestamp': timestamp})
        else:
            self.db.execute(
                """UPDATE [:table schema=cerebrum name=job_ran]
                SET timestamp=:timestamp
                WHERE id=:id""",
                {'id': job, 'timestamp': timestamp})

        self.db.commit()


class JobQueue(object):
    """Handles the job-queuing in job_runner.

    Supports detecion of jobs that are independent of other jobs in
    the ready-to-run queue.  A job is independent if no pre/post jobs
    for the job exists in the queue.  This check is done recursively.
    Note that the order of pre/post entries for job does not indicate
    a dependency.
    """

    def __init__(self, job_module, db, debug_time=0):
        """Initialize the JobQueue.

        :param types.Module job_module:
            A module that implements get_jobs()
        :param Cerebrum.Database.Database db:
            A database connection for queueing jobs
        :param int debug_time:
            Number of seconds to increase current-time with for each call to
            get_next_job_time().  Default is to use the system-clock.
        """
        self._scheduled_jobs = job_module
        self.logger = logger.getChild('JobQueue')
        self.db_qh = DbQueueHandler(db)

        self._known_jobs = {}
        self._run_queue = []
        self._running_jobs = []
        self._last_run = {}
        self._started_at = {}
        self._last_duration = {}  # For statistics in --status
        self._debug_time = debug_time
        self._forced_run_queue = []
        self._last_status = {}

        self.reload_scheduled_jobs()

    def reload_scheduled_jobs(self):
        self._scheduled_jobs = reload_job_config(self._scheduled_jobs)
        old_jobnames = set(self._known_jobs.keys())
        new_jobnames = set()
        for job_name, job_action in self._scheduled_jobs.get_jobs().items():
            self._add_known_job(job_name, job_action)
            new_jobnames.add(job_name)

        # TODO: Identify modified jobs, implement Action.__eq__?
        for name in old_jobnames - new_jobnames:
            del self._known_jobs[name]
            self.logger.info("Removed job %r", name)
        for name in new_jobnames - old_jobnames:
            self.logger.info("Added job %r", name)

        # Also check if last_run values has been changed in the DB (we
        # don't bother with locking the update to the dict)
        for k, v in self.db_qh.get_last_run().items():
            self._last_run[k] = v

    def get_known_job(self, job_name):
        return self._known_jobs[job_name]

    def get_known_jobs(self):
        return self._known_jobs

    def _add_known_job(self, job_name, job_action):
        """Adds job to list of known jobs, preserving
        state-information if we already know about the job"""
        if job_action.call:
            job_action.call.set_logger(self.logger)
            job_action.call.set_id(job_name)
        if job_name in self._known_jobs:  # Preserve info when reloading
            job_action.copy_runtime_params(self._known_jobs[job_name])
        self._known_jobs[job_name] = job_action
        # By setting _last_run to the current time we prevent jobs
        # with a time-based When from being ran imeadeately (note that
        # reload_scheduled_jobs will overwrite this value if an entry
        # exists in the db)
        if job_action.when and job_action.when.time:
            self._last_run[job_name] = time.time()
        else:
            self._last_run[job_name] = 0
        self._last_duration[job_name] = 0

    def has_queued_prerequisite(self, job_name, depth=0):
        """Recursively check if job_name has a pre-requisite in run_queue."""

        # TBD: if a multi_ok=1 job has pre/post dependencies, it could
        # be delayed so that the same job is executed several times,
        # example (conver_ypmap is a post-job for both generate jobs):
        #     ['generate_group', 'convert_ypmap', 'generate_passwd',
        #     'convert_ypmap']
        # Is this a problem.  If so, how do we handle it?

        # If a pre or post job of the main job is in the queue
        if depth > 0 and job_name in self._run_queue:
            return True
        # Job is currently running
        if job_name in [x[0] for x in self._running_jobs]:
            return True
        # Check any pre jobs for queue existence
        for tmp_name in self._known_jobs[job_name].pre:
            if self.has_queued_prerequisite(tmp_name, depth+1):
                return True
        # Check any post-jobs (except at depth=0, where the post-jobs
        # should be executed after us)
        if depth > 0:
            for tmp_name in self._known_jobs[job_name].post:
                if self.has_queued_prerequisite(tmp_name, depth+1):
                    return True
        else:
            # Check if any jobs in the queue has the main-job as a post-job.
            for tmp_name in self._run_queue:
                if job_name in self._known_jobs[tmp_name].post:
                    return True
            # any running jobs which has main-job as post-job
            for tmp_name in [x[0] for x in self._running_jobs]:
                if job_name in self._known_jobs[tmp_name].post:
                    return True
        return False

    def get_running_jobs(self):
        return [
            {'name': x[0],
             'pid': x[1],
             'call': (x[0] in self._known_jobs
                      and self._known_jobs[x[0]].call or None),
             'started': self._started_at[x[0]]}
            for x in self._running_jobs
        ]

    def kill_running_jobs(self, sig=signal.SIGTERM):
        """Send signal to all running jobs"""
        for i in self._running_jobs:
            try:
                os.kill(i[1], sig)
            except OSError:
                # Job have already quitted
                pass

    def job_started(self, job_name, pid, force=False):
        self._running_jobs.append((job_name, pid))
        self._started_at[job_name] = time.time()
        if force:
            self._forced_run_queue.remove(job_name)
        else:
            self._run_queue.remove(job_name)
        self.logger.debug("Started [%s]" % job_name)

    def job_done(self, job_name, pid, error=None, force=False):
        if pid is not None:
            self._running_jobs.remove((job_name, pid))

        self._last_status[job_name] = error or 'ok'

        if job_name in self._started_at:
            self._last_duration[job_name] = (
                time.time() - self._started_at[job_name])
            self.logger.debug("Completed [%s/%i] after %f seconds",
                              job_name,
                              pid or -1,
                              self._last_duration[job_name])
        else:
            if force:
                self._forced_run_queue.remove(job_name)
            else:
                self._run_queue.remove(job_name)
            self.logger.debug("Completed [%s/%i] (start not set)",
                              job_name, pid or -1)
        if job_name not in self._known_jobs:   # due to reload of config
            self.logger.debug("Completed unknown job %s", job_name)
            return
        if (pid is None
                or (self._known_jobs[job_name].call
                    and self._known_jobs[job_name].call.wait)):
            self._last_run[job_name] = time.time()
            self.db_qh.update_last_run(job_name, self._last_run[job_name])
        else:
            # This means that an assertRunning job has terminated.
            # Don't update last_run as this would delay an attempt to
            # restart the job.
            pass

    def get_forced_run_queue(self):
        return self._forced_run_queue

    def get_run_queue(self):
        return self._run_queue

    def get_next_job_time(self, append=False):
        """find job that should be run due to the current time, or
        being a pre-requisit of a ready job.  Returns number of
        seconds to next event, and stores the queue internally."""

        global current_time
        jobs = self._known_jobs
        if append:
            queue = self._run_queue[:]
        else:
            queue = []
        if self._debug_time:
            current_time += self._debug_time
        else:
            current_time = time.time()
        min_delta = 999999
        for job_name in jobs.keys():
            next_delta = jobs[job_name].next_delta(self._last_run[job_name],
                                                   current_time)
            if next_delta is None:
                continue
            if append and job_name in self._run_queue:
                # Without this, a previously added job that has a
                # pre/post job with multi_ok=True would get the
                # pre/post job appended once each time
                # get_next_job_time was called.
                continue

            # TODO: vent med å legge inn jobbene, slik at de som
            # har when=time kommer før de som har when=freq.
            if next_delta <= 0:
                logger.debug('job=%r has delta=%r', job_name, next_delta)
                pre_len = len(queue)
                self.insert_job(queue, job_name)
                if pre_len == len(queue):
                    # no jobs was added
                    continue

            min_delta = min(next_delta, min_delta)
        self.logger.debug("Delta=%i, a=%i/%i Queue: %s",
                          min_delta, append, len(self._run_queue), repr(queue))
        self._run_queue = queue
        return min_delta

    def insert_job(self, queue, job_name, _already_checked=None):
        """
        Add job to queue, with dependencies.

        Note: Job will only be added if it doesn't violate constraints for
        queueing.
        """
        # Protect against recursion loop
        if _already_checked is None:
            _already_checked = set()
        if job_name in _already_checked:
            return
        _already_checked.add(job_name)

        job = self._known_jobs[job_name]

        if job_name in queue and not job.multi_ok:
            logger.debug('job=%r is queued, multi_ok=%r',
                         job_name, job.multi_ok)
            return

        if (job.max_freq and
                current_time - self._last_run[job_name] < job.max_freq):
            logger.debug('job=%r ran less than %r sec ago',
                         job_name, job.max_freq)
            return

        # TODO: What if job.multi_ok? Should it not be added then?
        if job_name in (x[0] for x in self._running_jobs):
            logger.debug('job=%r is currently running', job_name)
            return

        # Try to add pre-jobs
        for pre_job_name in job.pre or []:
            self.insert_job(queue, pre_job_name,
                            _already_checked=_already_checked)

        logger.info('adding job=%r to queue', job_name)
        queue.append(job_name)

        # Try to add post-jobs
        for post_job_name in job.post or []:
            self.insert_job(queue, post_job_name,
                            _already_checked=_already_checked)

    def has_conflicting_jobs_running(self, job_name):
        """Finds out if there are any jobs running that conflict with
        the given job, as defined by the job's setup (via Action)

        Returns True if there are any such jobs, False otherwise

        """
        this_job = self._known_jobs[job_name]
        for potential_anti_job in [x[0] for x in self._running_jobs]:
            if potential_anti_job in this_job.nonconcurrent:
                # It's confirmed that there's at least one running job
                # that conflicts
                return True
        return False

    def is_running(self, job_name):
        """ Check if job is currently running. """
        running = set(tup[0] for tup in self._running_jobs)
        return job_name in running

    def last_started_at(self, job_name):
        """
        Check when a given job was last started.

        :returns:
            Returns timestamp in localtime, or 0 if the job hasn't been started
            or is unknown.
        """
        return self._started_at.get(job_name, 0)

    def last_done_at(self, job_name):
        """
        Check when a given job was last done.

        ..note:: Failed jobs also counts as 'done'.

        :returns:
            Returns timestamp in localtime, or 0 if the job hasn't been started
            or is unknown.
        """
        return self._last_run.get(job_name, 0)

    def is_queued(self, job_name, include_forced=False):
        """
        Check if job is currently queued.

        :param job_name:
        :param include_forced: If True, also check the forced_run_queue

        :returns: True if the job_name is queued.
        """
        if include_forced and job_name in self._forced_run_queue:
            return True
        return job_name in self._run_queue

    def last_status(self, job_name):
        return self._last_status.get(job_name) or 'unknown'
