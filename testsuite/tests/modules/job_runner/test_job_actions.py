# encoding: utf-8
"""
Unit tests for mod:`Cerebrum.modules.job_runner.job_actions`.

TODO: Figure out how to best start, manage, and test sub-processes created by
e.g.  ``System.execute``.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import io
import os

import pytest
import six

from Cerebrum.modules.job_runner import job_actions


@pytest.fixture(autouse=True)
def _patch_cereconf(cereconf, write_dir):
    cereconf.JOB_RUNNER_LOG_DIR = write_dir


#
# LockExists exception tests
#


def test_lock_exists_init():
    lock_error = job_actions.LockExists(1001)
    assert lock_error.acquire_pid == os.getpid()
    assert lock_error.lock_pid == 1001


def test_lock_exists_msg():
    lock_error = job_actions.LockExists(1001)
    assert six.text_type(lock_error) == "locked by pid=1001"


#
# Action tests
#


def test_action_init():
    call = object()
    when = object()
    notwhen = object()
    health = object()
    action = job_actions.Action(
        pre=["foo"],
        post=["bar"],
        call=call,
        max_freq=10,
        when=when,
        notwhen=notwhen,
        max_duration=20,
        multi_ok=True,
        nonconcurrent=["foo", "bar"],
        health=health,
    )
    assert action.pre == ["foo"]
    assert action.post == ["bar"]
    assert action.call is call
    assert action.max_freq == 10
    assert action.when is when
    assert action.notwhen is notwhen
    assert action.max_duration == 20
    assert action.multi_ok
    assert set(action.nonconcurrent) == set(("foo", "bar"))
    assert action.health is health


class MockSystemAction(job_actions.CallableAction):

    def __init__(self, cmd, params):
        super(MockSystemAction, self).__init__()
        self.cmd = cmd
        self.params = list(params)


def test_action_pretty_cmd():

    def generate_path():
        return "/tmp/bar"

    action = job_actions.Action(
        call=MockSystemAction(
            "/usr/bin/ls",
            [
                "-l", "-d",
                "/tmp/foo bar",
                generate_path,
            ],
        ),
    )
    cmd = action.get_pretty_cmd()
    assert cmd == "/usr/bin/ls -l -d '/tmp/foo bar' /tmp/bar"


#
# LockFile tests
#
# Uses `write_dir` fixture from `conftest`
#


@pytest.fixture
def lock_file():
    """ a lock file in the `write_dir` fixture. """
    return job_actions.LockFile("test")


def test_lock_file_init(lock_file):
    assert lock_file
    assert lock_file.name == "test"


def test_lock_file_dir(lock_file, write_dir):
    assert lock_file.lock_dir == write_dir


def test_lock_file_repr(lock_file):
    assert repr(lock_file) == "<LockFile name=" + repr(lock_file.name) + ">"


def test_lock_file_filename(lock_file, write_dir):
    assert lock_file.filename == os.path.join(write_dir,
                                              "job-runner-test.lock")


def test_lock_file_read(lock_file):
    with io.open(lock_file.filename, mode="w", encoding="ascii") as f:
        f.write("hello")
    assert lock_file.read() == "hello"


def test_lock_file_write(lock_file):
    lock_file.write("hello")
    with io.open(lock_file.filename, mode="r", encoding="ascii") as f:
        assert f.read() == "hello"


def test_lock_file_exists(lock_file):
    with io.open(lock_file.filename, mode="w", encoding="ascii") as f:
        f.write("hello")
    assert lock_file.exists()


#
# CallableAction tests
#


def test_callable_action_init():
    action = job_actions.CallableAction()
    assert action.id is None
    assert action.wait


def test_callable_action_setup():
    action = job_actions.CallableAction()
    assert action.setup()


def test_callable_action_set_id():
    action = job_actions.CallableAction()
    action.set_id("test")
    assert action.id == "test"
    assert action.lockfile
    assert action.lockfile.name == "test"


#
# System tests
#


def test_system_init():
    def generate_path():
        return "/tmp/bar"

    call = job_actions.System(
        "/usr/bin/ls",
        params=[
            "-l", "-d",
            "/tmp/foo bar",
            generate_path,
        ],
        stdout_ok=True,
    )
    assert call.cmd == "/usr/bin/ls"
    assert call.params == ["-l", "-d", "/tmp/foo bar", generate_path]


@pytest.fixture
def system_call():
    call = job_actions.System(
        "/usr/bin/bash",
        params=[
            "-c", "echo foo",
        ],
        stdout_ok=True,
    )
    call.set_id("test")
    return call


def test_system_run_dir(system_call, write_dir):
    assert system_call.run_dir == os.path.join(write_dir, "test")


def test_system_stdout_file(system_call, write_dir):
    assert system_call.stdout_file == os.path.join(write_dir,
                                                   "test/stdout.log")


def test_system_stderr_file(system_call, write_dir):
    assert system_call.stderr_file == os.path.join(write_dir,
                                                   "test/stderr.log")


#
# Jobs tests
#


def test_unique_job_actions():
    job_cls, action_cls = job_actions.Jobs, job_actions.Action
    cls_foo = type(str("Foo"), (job_cls,), {'foo': action_cls()})
    cls_bar = type(str("Bar"), (job_cls,), {'foo': action_cls()})
    with pytest.raises(ValueError) as exc_info:
        type(str("FooBar"), (cls_foo, cls_bar), {})
    error = six.text_type(exc_info.value)
    assert error == "Bar.foo already defined in Foo"


def test_jobs_get_jobs():
    # this test mainly checks the `get_jobs()` method and results
    job_cls = type(
        str("Jobs"),
        (job_actions.Jobs,),
        {
            'foo': job_actions.Action(post=["bar"]),
            'bar': job_actions.Action(pre=["foo"], post=["baz"]),
            'baz': job_actions.Action(pre=["bar"]),
        },
    )
    jobs = job_cls().get_jobs()
    assert len(jobs) == 3
    assert jobs['foo'] == job_cls.foo


def test_jobs_get_jobs_cycle():
    job_cls = type(
        str("Jobs"),
        (job_actions.Jobs,),
        {
            'foo': job_actions.Action(pre=["bar"]),
            'bar': job_actions.Action(pre=["foo"]),
        },
    )
    with pytest.raises(ValueError) as exc_info:
        job_cls().get_jobs()

    error = six.text_type(exc_info.value)
    assert error.startswith("joblist has a cycle: ")


def test_jobs_validate_missing_pre():
    # this test mainly checks the `get_jobs()` method and results
    job_cls = type(
        str("Jobs"),
        (job_actions.Jobs,),
        {
            'foo': job_actions.Action(pre=["bar"]),
        },
    )
    with pytest.raises(ValueError) as exc_info:
        job_cls().validate()

    error = six.text_type(exc_info.value)
    assert error.startswith("Undefined pre-job 'bar'")


def test_jobs_validate_missing_post():
    # this test mainly checks the `get_jobs()` method and results
    job_cls = type(
        str("Jobs"),
        (job_actions.Jobs,),
        {
            'foo': job_actions.Action(post=["bar"]),
        },
    )
    with pytest.raises(ValueError) as exc_info:
        job_cls().validate()

    error = six.text_type(exc_info.value)
    assert error.startswith("Undefined post-job 'bar'")
