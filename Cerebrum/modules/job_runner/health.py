# -*- coding: utf-8 -*-

# Copyright 2021-2024 University of Oslo, Norway
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
Job Runner health check.

This file implements various functions and helpers to generate a health report
for Zabbix.

The report includes some monitoring values for the job runner daemon, as well
as a discovery key to be used by Zabbix 4 discovery rules.  Each
py:class:`Cerebrum.modules.job_runner.job_actions.Action` can include an
optional py:class:`.HealthCheck` to be included in the report.

Each key-value pair in the discovery dicts are intended to be mapped to an *LLD
Macro* in the discovery rule configuration.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import logging
import json
import time

from Cerebrum.utils import file_stream

logger = logging.getLogger(__name__)


class HealthCheck(object):
    """ Per job health check settings.

    This object represent the health check settings for a given Action.
    """
    def __init__(self, check_ok=False, check_overdue=None):
        """
        :param check_ok:
            Add monitoring of previous run result.

            This setting should enable monitoring of the *prev_ok* job value in
            the report, indicating the previous exit status of the job:

            - 0 - the previous run failed
            - 1 - no previous run, or the previous run succeeded

        :param check_overdue:
            Add monitoring of time since last successful run.

            The value is a threshold (in seconds), and should be greater than
            the max expected frequency of the job.

            If set, the report will include a positive *overdue* job item in
            report if the job hasn't succeeded in *check_overdue* seconds (i.e.
            the job is *overdue* seconds overdue for a successful run).
        """
        self.check_ok = bool(check_ok)
        self.check_overdue = int(check_overdue) if check_overdue else None

    @property
    def enabled(self):
        return any((
            self.check_ok,
            self.check_overdue,
        ))


class HealthMonitor(object):
    """
    A simple wrapper for generating JSON reports.

    This needs to run as a thread within the job_runner process (for access
    to the same job_runner object).
    """

    def __init__(self, job_runner, filename, interval=60):
        self.job_runner = job_runner
        self.filename = filename
        self.interval = interval

    def run(self):
        self._is_running = True
        logger.info('writing health report to %s every %d seconds)',
                    self.filename, self.interval)
        while self._is_running:
            logger.debug('generating report')
            report_data = get_health_report(self.job_runner)
            write_health_report(self.filename, report_data)
            logger.debug('sleeping for %d seconds', self.interval)
            time.sleep(self.interval)


def _check_status(msg):
    """ Decide if the previous run of a job was successful. """
    # TODO: We should really just be able to *ask* this directly
    # TODO: We should really persist this, so we know the current state on
    #       startup (i.e. no "unknown")
    if msg == "ok":
        return True
    if msg == "unknown":
        # job hasn't run yet, which also means that is hasn't failed yet
        return True
    if msg.startswith("exit_code=0"):
        # job finished ok, but something noticable happened,
        # usually this means that the job unexpectedly wrote to stdout/stderr
        return True

    # any other msg usually means that a job has failed
    return False


def get_health_report(job_runner):
    now = time.time()

    report = {
        # Zabbix autodiscovery rules:
        'discovery': [],
        # Current job state:
        'jobs': {},
        # Current server state:
        'state': {
            'curr_time': int(now),
            'paused_at': int(job_runner.queue_paused_at),
        },
    }

    queue = job_runner.job_queue
    for job_name in sorted(queue.get_known_jobs()):
        msg = queue.last_status(job_name)
        last_success = queue.last_success_at(job_name)
        job_report = report['jobs'][job_name] = {
            'is_overdue': 0,
            'last_done_at': int(queue.last_done_at(job_name)),
            'last_success_at': int(last_success),
            'prev_msg': msg,
            'prev_ok': 1 if _check_status(msg) else 0,
        }

        job_action = queue.get_known_job(job_name)
        if not job_action.health or not job_action.health.enabled:
            # no health checks for this job
            continue

        report['discovery'].append({
            # LLD Macro:
            # A unique name, as well as a reference to data in $.jobs
            'job_name': job_name,
            # LLD Macro:
            # Decides if a last_value item/trigger should be created for this
            # job.
            'check_ok': bool(job_action.health.check_ok),
            # LLD Macro:
            # Decides if an is_overdue item/trigger should be created for this
            # job, and what the overdue threshold is.
            'check_overdue': int(job_action.health.check_overdue or 0),
        })

        # Calculate *is_overdue* value, if applicable
        if job_action.health.check_overdue:
            if not last_success and msg == "unknown":
                # No runs after server startup, so we have no last known time
                # to compare with.  For now we assume last_done_at is a success
                # (i.e. the last_run value from before shutdown/restart
                # regardless of it being successful).
                #
                # TODO: This will lead to false results, especially for brand
                # new jobs w/o a last_run at all.  Potential fixes:
                # - Store and restore a last_success value in the database
                # - Use server start time as a last_success
                last_success = queue.last_done_at(job_name)
            delta = now - last_success
            overdue = int(delta - job_action.health.check_overdue)
            if overdue > 0:
                # job hasn't succeeded in *delta* seconds, and is *overdue*
                # seconds overdue!
                job_report['is_overdue'] = overdue
    return report


def format_health_report(report_data):
    return json.dumps(
        obj=report_data,
        indent=2,
        sort_keys=True,
        separators=(',', ': '),
    ) + "\n"


def write_health_report(filename, report_data):
    """ write json health report. """
    encoding = None if str is bytes else "utf-8"
    with file_stream.get_output_context(filename, encoding=encoding,
                                        stdout=None, stderr=None) as fp:
        logger.debug('writing report to %s', repr(fp))
        json.dump(
            obj=report_data,
            fp=fp,
            indent=2,
            sort_keys=True,
            separators=(',', ': '),
        )
        fp.write("\n")
        fp.flush()
