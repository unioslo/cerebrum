# encoding: utf-8
"""
Unit tests for :mod:`Cerebrum.modules.no.uio.sympa`.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import logging

import pytest

from Cerebrum.modules.sympa import commands
from Cerebrum.utils.subproc import format_command
from Cerebrum.testutils.log_utils import StrictNullHandler


@pytest.fixture(scope='module', autouse=True)
def _patch_logging():
    """ catch badly formatted log records in reguser.logger """
    # consider mistakes in log formatting to be a test failure
    commands.logger.addHandler(StrictNullHandler())
    commands.logger.setLevel(-100)


SYMPA_SCRIPT = "/path/to/sympa-wrapper"


@pytest.fixture(autouse=True)
def _patch_cereconf(cereconf):
    """ patch cereconf with known values. """
    # consider mistakes in log formatting to be a test failure
    cereconf.SYMPA_SCRIPT = SYMPA_SCRIPT


@pytest.fixture
def runner():
    return commands.SympaCommands(
        dryrun=True,
    )


def test_init(runner):
    assert runner
    assert runner.dryrun


def test_repr(runner):
    repr_text = repr(runner)
    expected = "SympaCommands(dryrun=True)"
    assert repr_text == expected


def test_run_command_success(caplog):
    caplog.set_level(logging.INFO)
    runner = commands.SympaCommands(dryrun=False)
    cmd = ["python", "-c", "raise SystemExit(0)"]
    assert runner._run_command(cmd)
    assert len(caplog.records) == 2
    assert caplog.records[0].message.endswith(
        "start: python -c 'raise SystemExit(0)'"
    )
    assert caplog.records[1].message.endswith("done: exit=0")


def test_run_command_error(caplog):
    caplog.set_level(logging.INFO)
    runner = commands.SympaCommands(dryrun=False)
    cmd = ["python", "-c", "raise SystemExit(1)"]
    assert not runner._run_command(cmd)
    assert len(caplog.records) == 2
    assert caplog.records[0].message.endswith(
        "start: python -c 'raise SystemExit(1)'"
    )
    assert caplog.records[1].message.endswith("done: exit=1")


RUNHOST = "sympa.example.org"
LISTNAME = "example@lists.example.org"
ADMINS = "foo.bar@example.org"
PROFILE = "discussion_list"
DESCRIPTION = "Sympa test list for unit tests"


NEWLIST_ARGS = [RUNHOST, LISTNAME, ADMINS, PROFILE, DESCRIPTION]


def test_newlist_cmd(runner):
    cmd = runner._newlist_args(*NEWLIST_ARGS)
    assert cmd == [
        SYMPA_SCRIPT, RUNHOST,
        "newlist", LISTNAME,
        ADMINS, PROFILE, DESCRIPTION,
    ]


def test_newlist(runner):
    assert runner.newlist(*NEWLIST_ARGS)


def test_newlist_logs(caplog, runner):
    caplog.set_level(logging.DEBUG)
    runner.newlist(*NEWLIST_ARGS)
    plain_cmd = format_command(runner._newlist_args(*NEWLIST_ARGS))

    assert len(caplog.records) == 2

    debug_msg = ("%s.newlist(%s)"
                 % (repr(runner), ", ".join(repr(a) for a in NEWLIST_ARGS)))
    assert caplog.records[0].levelno == logging.DEBUG
    assert caplog.records[0].message == debug_msg

    info_msg = "dryrun: " + plain_cmd
    assert caplog.records[1].levelno == logging.INFO
    assert caplog.records[1].message == info_msg


RMLIST_ARGS = [RUNHOST, LISTNAME]


def test_rmlist_cmd(runner):
    cmd = runner._rmlist_args(*RMLIST_ARGS)
    assert cmd == [
        SYMPA_SCRIPT, RUNHOST,
        "rmlist", LISTNAME,
    ]


def test_rmlist(runner):
    assert runner.rmlist(*RMLIST_ARGS)


def test_rmlist_logs(caplog, runner):
    caplog.set_level(logging.DEBUG)
    runner.rmlist(*RMLIST_ARGS)
    plain_cmd = format_command(runner._rmlist_args(*RMLIST_ARGS))

    assert len(caplog.records) == 2

    debug_msg = ("%s.rmlist(%s)"
                 % (repr(runner), ", ".join(repr(a) for a in RMLIST_ARGS)))
    assert caplog.records[0].levelno == logging.DEBUG
    assert caplog.records[0].message == debug_msg

    info_msg = "dryrun: " + plain_cmd
    assert caplog.records[1].levelno == logging.INFO
    assert caplog.records[1].message == info_msg
