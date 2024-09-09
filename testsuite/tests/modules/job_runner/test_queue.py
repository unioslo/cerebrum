# encoding: utf-8
"""
Unit tests for mod:`Cerebrum.modules.job_runner.queue`.

These tests are a bit messy, as the job queue itself is a bit messy.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import datetime
import io

import pytest

from Cerebrum.modules.job_runner import queue
from Cerebrum.modules.job_runner import job_config
from Cerebrum.utils import date as date_utils


class _DbWrapper(object):
    """
    Need to override db.commit, as the `DbQueueHandler.update_last_run()`
    method commits changes, and the default database fixture remaps commit
    to rollback
    """
    def __init__(self, db):
        self.db = db

    def query(self, *args, **kwargs):
        return self.db.query(*args, **kwargs)

    def query_1(self, *args, **kwargs):
        return self.db.query_1(*args, **kwargs)

    def execute(self, *args, **kwargs):
        return self.db.execute(*args, **kwargs)

    def rollback(self, *args, **kwargs):
        return self.db.rollback(*args, **kwargs)

    def commit(self, *args, **kwargs):
        pass


@pytest.fixture
def database(database):
    # clear the job history for the test database transaction:
    database.execute(
        """
        DELETE FROM [:table schema=cerebrum name=job_ran]
        """.strip()
    )
    return _DbWrapper(database)


#
# DbQueueHandler tests
#


@pytest.fixture
def empty_db_queue(database):
    return queue.DbQueueHandler(database)


LAST_RUNS = {
    'foo': date_utils.apply_timezone(
        datetime.datetime(1998, 6, 28, 23, 30, 11, 987654),
        date_utils.UTC,
    ),
    'bar': date_utils.apply_timezone(
        datetime.datetime(2024, 9, 4, 15, 30),
        date_utils.UTC,
    ),
}


@pytest.fixture
def db_queue(empty_db_queue):
    for name, when in LAST_RUNS.items():
        empty_db_queue.db.execute(
            """
            INSERT INTO [:table schema=cerebrum name=job_ran]
              (id, timestamp)
            VALUES
              (:id, :timestamp)
            """,
            {'id': name, 'timestamp': when},
        )
    return empty_db_queue


def test_get_last_run_empty(empty_db_queue):
    """ Get an empty last_run log. """
    last_run = empty_db_queue.get_last_run()
    assert last_run == {}


def test_get_last_run(db_queue):
    """ Get the last_run log. """
    last_run = db_queue.get_last_run()
    assert last_run == {k: date_utils.to_timestamp(LAST_RUNS[k])
                        for k in LAST_RUNS}


def test_update_last_run_new(db_queue):
    """ Add a new job to last_run log. """
    ts = 899076611
    db_queue.update_last_run("baz", ts)
    last_run = db_queue.get_last_run()
    assert 'baz' in last_run
    assert last_run['baz'] == ts


def test_update_last_run_timestamp(db_queue):
    """ Update a job in the last_run log with a timestamp. """
    ts = 899076611
    db_queue.update_last_run("foo", ts)
    last_run = db_queue.get_last_run()
    assert 'foo' in last_run
    assert last_run['foo'] == ts


def test_update_last_run_datetime(db_queue):
    """ Update a job in the last_run log with a datetime. """
    ts = 899076611
    dt = date_utils.from_timestamp(ts)
    db_queue.update_last_run("foo", dt)
    last_run = db_queue.get_last_run()
    assert 'foo' in last_run
    assert last_run['foo'] == ts


#
# JobQueue tests
#


CONFIG_CONTENT = """
import os

from Cerebrum.utils.date import to_seconds
from Cerebrum.modules.job_runner.job_actions import Action, Jobs, System
from Cerebrum.modules.job_runner.job_utils import Time, When
from Cerebrum.modules.job_runner.health import HealthCheck


class AllJobs(Jobs):

    pre_job = Action(call=None)
    post_job = Action(call=None)
    conflicting_job = Action(call=None)

    test_job = Action(
        call=None,
        pre=["pre_job"],
        post=["post_job"],
        nonconcurrent=["conflicting_job"],
    )

    scheduled_time = Action(
        call=None,
        when=When(time=[Time(min=[0, 15, 30, 45])]),
    )

    scheduled_freq = Action(
        call=None,
        when=When(freq=to_seconds(minutes=15)),
    )



def get_jobs():
    return AllJobs().get_jobs()
""".lstrip()


@pytest.fixture
def job_module(config_file):
    with io.open(config_file, mode="w", encoding="utf-8") as f:
        f.write(CONFIG_CONTENT)
    return job_config.get_job_config(config_file)


@pytest.fixture
def job_queue(database, job_module):
    return queue.JobQueue(job_module, database, debug_time=0)


def test_queue_init(job_queue):
    assert job_queue


def test_queue_get_known_jobs(job_queue):
    jobs = job_queue.get_known_jobs()
    assert 'test_job' in jobs


def test_queue_get_known_job(job_queue):
    job = job_queue.get_known_job("test_job")
    assert job
    assert job.pre == ["pre_job"]


def test_queue_insert_job(job_queue):
    queue = job_queue.get_run_queue()
    job_queue.insert_job(queue, "test_job")
    assert job_queue.is_queued("test_job")


def test_queue_job_start(job_queue):
    # setup test_job
    queue = job_queue.get_run_queue()
    job_queue.insert_job(queue, "test_job")

    # start test_job
    job_queue.job_started("test_job", -1)
    assert not job_queue.is_queued("test_job")
    assert job_queue.is_running("test_job")


def test_queue_job_done(job_queue):
    # setup test_job
    queue = job_queue.get_run_queue()
    job_queue.insert_job(queue, "test_job")
    job_queue.job_started("test_job", -1)

    # complete test_job
    job_queue.job_done("test_job", -1)
    assert not job_queue.is_queued("test_job")
    assert not job_queue.is_running("test_job")
    assert job_queue.last_status("test_job") == "ok"
    assert (job_queue.last_success_at("test_job")
            > job_queue.last_started_at("test_job"))


def test_queue_job_failed(job_queue):
    # setup test_job
    queue = job_queue.get_run_queue()
    job_queue.insert_job(queue, "test_job")
    job_queue.job_started("test_job", -1)

    # complete test_job
    job_queue.job_done("test_job", -1, ok=False, msg="error")
    assert not job_queue.is_queued("test_job")
    assert not job_queue.is_running("test_job")
    assert job_queue.last_status("test_job") == "error"
    assert (job_queue.last_failure_at("test_job")
            > job_queue.last_started_at("test_job"))


def test_queue_pre_missing(job_queue):
    assert not job_queue.has_queued_prerequisite("test_job")


def test_queue_pre_queued(job_queue):
    queue = job_queue.get_run_queue()
    job_queue.insert_job(queue, "pre_job")
    assert job_queue.has_queued_prerequisite("test_job")


def test_queue_no_conflict(job_queue):
    queue = job_queue.get_run_queue()
    job_queue.insert_job(queue, "conflicting_job")
    assert not job_queue.has_conflicting_jobs_running("test_job")


def test_queue_with_conflict(job_queue):
    queue = job_queue.get_run_queue()
    job_queue.insert_job(queue, "conflicting_job")
    job_queue.job_started("conflicting_job", -1)
    assert job_queue.has_conflicting_jobs_running("test_job")


def test_get_running_jobs(job_queue):
    # setup and start test_job
    queue = job_queue.get_run_queue()
    job_queue.insert_job(queue, "test_job")
    job_queue.job_started("test_job", -1)

    running = job_queue.get_running_jobs()
    assert len(running) == 1
    job = running[0]
    assert all(k in job for k in ('name', 'pid', 'call', 'started'))
    assert job['name'] == "test_job"
    assert job['pid'] == -1


def test_get_next_job_time(job_queue):
    # ensure all known jobs have never ran:
    for k in job_queue.get_known_jobs():
        job_queue._last_run[k] = 0

    result = job_queue.get_next_job_time()
    queue = job_queue.get_run_queue()
    assert result < 0
    assert set(queue) == set(("scheduled_freq", "scheduled_time"))
