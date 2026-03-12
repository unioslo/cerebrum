# encoding: utf-8
"""
Unit tests for :mod:`Cerebrum.modules.no.uio.reguser`.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import logging
import os

import pytest

from Cerebrum.modules.no.uio import reguser
from Cerebrum.utils.subproc import format_command
from Cerebrum.testutils.log_utils import StrictNullHandler


@pytest.fixture(scope='module', autouse=True)
def _patch_logging():
    """ catch badly formatted log records in reguser.logger """
    # consider mistakes in log formatting to be a test failure
    reguser.logger.addHandler(StrictNullHandler())
    reguser.logger.setLevel(-100)


REMOTE_HOST = "example@localhost"
REGUSER_CREATE = "/path/to/create_user"
REGUSER_MOVE = "/path/to/move_user"
REGUSER_DELETE = "/path/to/delete_user"


@pytest.fixture(autouse=True)
def _patch_cereconf(cereconf):
    """ patch cereconf with known reguser values. """
    # consider mistakes in log formatting to be a test failure
    cereconf.ARCHIVE_USER_SERVER = REMOTE_HOST
    cereconf.CREATE_USER_SCRIPT = REGUSER_CREATE
    cereconf.MVUSER_SCRIPT = REGUSER_MOVE
    cereconf.RMUSER_SCRIPT = REGUSER_DELETE


@pytest.fixture
def runner():
    return reguser.ReguserCommands(
        dryrun=True,
        remote_dryrun=True,
        remote_debug=True,
    )


def test_init(runner):
    assert runner


def test_repr(runner):
    repr_text = repr(runner)
    expected = "ReguserCommands(dryrun=True, remote_dryrun=True)"
    assert repr_text == expected


def test_remote_host(runner):
    assert runner.remote_host == REMOTE_HOST


def test_run_command_success(caplog):
    caplog.set_level(logging.INFO)
    runner = reguser.ReguserCommands(dryrun=False)
    cmd = ["python", "-c", "raise SystemExit(0)"]
    assert runner._run_command(cmd)
    assert len(caplog.records) == 2
    assert caplog.records[0].message.endswith(
        "start: python -c 'raise SystemExit(0)'"
    )
    assert caplog.records[1].message.endswith("done: exit=0")


def test_run_command_error(caplog):
    caplog.set_level(logging.INFO)
    runner = reguser.ReguserCommands(dryrun=False)
    cmd = ["python", "-c", "raise SystemExit(1)"]
    assert not runner._run_command(cmd)
    print(caplog.records)
    assert len(caplog.records) == 2
    assert caplog.records[0].message.endswith(
        "start: python -c 'raise SystemExit(1)'"
    )
    assert caplog.records[1].message.endswith("done: exit=1")


USERNAME = "foo"
OPERATOR = "example"
UID = 1001
GID = 3001
HOMEDIR = "/path/to/home/foo"
GECOS = "Foo Bar"


CREATE_ARGS = [USERNAME, HOMEDIR, UID, GID, GECOS]


def test_create_user_cmd(runner):
    cmd = runner._create_user_cmd(*CREATE_ARGS)
    assert cmd == [
        "/usr/bin/ssh", REMOTE_HOST,
        "sudo", REGUSER_CREATE,
        "--username", USERNAME,
        "--homedir", HOMEDIR,
        "--uid", str(UID),
        "--gid", str(GID),
        "--gecos", GECOS,
        "--debug",
        "--dryrun",
    ]


def test_create_user(runner):
    assert runner.create_user(*CREATE_ARGS)


def test_create_user_logs(caplog, runner):
    caplog.set_level(logging.DEBUG)
    runner.create_user(*CREATE_ARGS)
    plain_cmd = format_command(runner._create_user_cmd(*CREATE_ARGS))

    assert len(caplog.records) == 2

    debug_msg = ("%s.create_user(%s)"
                 % (repr(runner), ", ".join(repr(a) for a in CREATE_ARGS)))
    assert caplog.records[0].levelno == logging.DEBUG
    assert caplog.records[0].message == debug_msg

    info_msg = "dryrun: " + plain_cmd
    assert caplog.records[1].levelno == logging.INFO
    assert caplog.records[1].message == info_msg


DELETE_GENERATION = 3
DELETE_ARGS = [USERNAME, OPERATOR, HOMEDIR, DELETE_GENERATION]


def test_delete_user_cmd(runner):
    cmd = runner._delete_user_cmd(*DELETE_ARGS)
    assert cmd == [
        "/usr/bin/ssh", REMOTE_HOST,
        "sudo", REGUSER_DELETE,
        "--username", USERNAME,
        "--deleted-by", OPERATOR,
        "--homedir", HOMEDIR,
        "--generation", str(DELETE_GENERATION),
        "--debug",
        "--dryrun",
    ]


def test_delete_user(runner):
    assert runner.delete_user(*DELETE_ARGS)


def test_delete_user_logs(caplog, runner):
    caplog.set_level(logging.DEBUG)
    runner.delete_user(*DELETE_ARGS)
    plain_cmd = format_command(runner._delete_user_cmd(*DELETE_ARGS))

    assert len(caplog.records) == 2

    debug_msg = ("%s.delete_user(%s)"
                 % (repr(runner), ", ".join(repr(a) for a in DELETE_ARGS)))
    assert caplog.records[0].levelno == logging.DEBUG
    assert caplog.records[0].message == debug_msg

    info_msg = "dryrun: " + plain_cmd
    assert caplog.records[1].levelno == logging.INFO
    assert caplog.records[1].message == info_msg


MOVE_SRC = os.path.dirname(HOMEDIR)
MOVE_DEST = "/path/to/new-home"
MOVE_ARGS = [USERNAME, UID, GID, MOVE_SRC, MOVE_DEST, OPERATOR]


def test_move_user_cmd(runner, cereconf):
    cereconf.ARCHIVE_USER_SERVER = None
    runner.remote_dryrun = False
    runner.remote_debug = False
    cmd = runner._move_user_cmd(*MOVE_ARGS)
    assert cmd == [
        "sudo", REGUSER_MOVE,
        "--user", USERNAME,
        "--uid", str(UID),
        "--gid", str(GID),
        "--old-disk", MOVE_SRC,
        "--new-disk", MOVE_DEST,
        "--operator", OPERATOR,
    ]


def test_move_user(runner):
    assert runner.move_user(*MOVE_ARGS)


def test_move_user_logs(caplog, runner):
    caplog.set_level(logging.DEBUG)
    runner.move_user(*MOVE_ARGS)
    plain_cmd = format_command(runner._move_user_cmd(*MOVE_ARGS))

    assert len(caplog.records) == 2

    debug_msg = ("%s.move_user(%s)"
                 % (repr(runner), ", ".join(repr(a) for a in MOVE_ARGS)))
    assert caplog.records[0].levelno == logging.DEBUG
    assert caplog.records[0].message == debug_msg

    info_msg = "dryrun: " + plain_cmd
    assert caplog.records[1].levelno == logging.INFO
    assert caplog.records[1].message == info_msg
