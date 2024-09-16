# encoding: utf-8
""" Unit tests for mod:`Cerebrum.modules.job_runner.health` """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import io
import textwrap

import pytest

from Cerebrum.modules.job_runner import health


#
# HealthCheck tests
#


def test_health_check_init():
    assert health.HealthCheck()


def test_health_check_enabled():
    hc = health.HealthCheck(check_ok=True, check_overdue=None)
    assert hc.enabled


def test_health_check_disabled():
    hc = health.HealthCheck(check_ok=False, check_overdue=0)
    assert not hc.enabled


#
# get_health_report tests
#


class _MockAction(object):

    def __init__(self, health=None, last_done_at=0, last_success_at=0,
                 last_status="ok"):
        self.health = health
        self.last_done_at = int(last_done_at)
        self.last_success_at = int(last_success_at)
        self.last_status = last_status


class _MockJobQueue(object):

    def __init__(self, jobs):
        self._jobs = jobs

    def get_known_jobs(self):
        return dict(self._jobs)

    def get_known_job(self, job_name):
        return self._jobs[job_name]

    def last_status(self, job_name):
        return self.get_known_job(job_name).last_status

    def last_success_at(self, job_name):
        return self.get_known_job(job_name).last_success_at

    def last_done_at(self, job_name):
        return self.get_known_job(job_name).last_done_at


class _MockJobRunner(object):

    def __init__(self, **jobs):
        self.queue_paused_at = 0
        self.job_queue = _MockJobQueue(jobs)


@pytest.fixture
def job_runner():
    return _MockJobRunner(
        foo=_MockAction(
            health=health.HealthCheck(check_ok=True),
            last_status="exit_code=1",
        ),
        bar=_MockAction(
            health=health.HealthCheck(check_overdue=30),
            last_status="ok",
        ),
        baz=_MockAction(last_status="unknown"),
    )


def test_health_report_state(job_runner):
    """ A hacky test that checks if the report is somewhat sane. """
    report = health.get_health_report(job_runner)
    assert report['state']['curr_time']
    assert not report['state']['paused_at']


def test_health_report_discovery(job_runner):
    """ Check that the discovery list contains all jobs with health checks. """
    report = health.get_health_report(job_runner)
    items = report['discovery']
    assert len(items) == 2
    assert set(d['job_name'] for d in items) == set(('foo', 'bar'))


def test_health_report_jobs(job_runner):
    """ Check that the jobs list contains status for all jobs. """
    report = health.get_health_report(job_runner)
    jobs = report['jobs']
    assert len(jobs) == 3
    assert set(jobs) == set(('foo', 'bar', 'baz'))


def test_health_report_job_status(job_runner):
    """ Check that the jobs list contains status for all jobs. """
    report = health.get_health_report(job_runner)
    job = report['jobs']['foo']
    assert job['prev_msg'] == "exit_code=1"
    assert not job['prev_ok']


#
# write_health_report tests
#
# Uses `new_file` fixture from `conftest`
#


def test_write_health_report(new_file):
    data = {
        "foo": "blåbær",
        "bar": [1, 2, 3],
    }
    health.write_health_report(new_file, data)

    with io.open(new_file, mode="r", encoding="utf-8") as f:
        content = f.read()
    assert content == textwrap.dedent(
        """
        {
          "bar": [
            1,
            2,
            3
          ],
          "foo": "bl\\u00e5b\\u00e6r"
        }
        """
    ).lstrip()
