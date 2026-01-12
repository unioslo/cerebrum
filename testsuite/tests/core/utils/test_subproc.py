# encoding: utf-8
""" Tests for mod:`Cerebrum.utils.subproc` """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import logging
import signal
import textwrap

import pytest
import six

from Cerebrum.utils import subproc
from Cerebrum.testutils import file_utils
from Cerebrum.testutils.log_utils import StrictNullHandler


@pytest.fixture(scope='module', autouse=True)
def _patch_logging():
    """ catch badly formatted log records in subproc.logger. """
    subproc.logger.addHandler(StrictNullHandler())
    subproc.logger.setLevel(-100)


FILE_CONTENTS = """
Some text snippets from
<https://www.w3.org/2001/06/utf-8-test/UTF-8-demo.html>.
Original by Markus Kuhn, adapted for HTML by Martin Dürst.

Sample text
‾‾‾‾‾‾‾‾‾‾‾
Mathematics:
  ∮ E⋅da = Q,  n → ∞, ∑ f(i) = ∏ g(i), ∀x∈ℝ: ⌈x⌉ = −⌊−x⌋, α ∧ ¬β = ¬(¬α ∨ β),

Greek:
  Σὲ γνωρίζω ἀπὸ τὴν κόψη

Runes:
  ᚻᛖ ᚳᚹᚫᚦ ᚦᚫᛏ ᚻᛖ ᛒᚢᛞᛖ ᚩᚾ ᚦᚫᛗ ᛚᚪᚾᛞᛖ ᚾᚩᚱᚦᚹᛖᚪᚱᛞᚢᛗ ᚹᛁᚦ ᚦᚪ ᚹᛖᛥᚫ

Braille:
  ⡌⠁⠧⠑ ⠼⠁⠒  ⡍⠜⠇⠑⠹⠰⠎ ⡣⠕⠌
""".lstrip()


@pytest.fixture
def text_file(new_file):
    # new_file from conftest
    file_utils.write_text(new_file, FILE_CONTENTS, encoding="utf-8")
    return new_file


def test_run_stdout(text_file):
    # cmd = ["cat", text_file]
    script = textwrap.dedent(
        """
        from __future__ import print_function
        import io, sys
        print(io.open(sys.argv[1], encoding="utf-8").read(), end="")
        """
    ).lstrip()
    cmd = ["python", "-c", script, text_file]
    result = subproc.run(cmd, retval=("stdout",))
    assert result[0] == FILE_CONTENTS


def test_run_rc_success():
    # cmd = ["true"]
    cmd = ["python", "-c", "raise SystemExit(0)"]
    result = subproc.run(cmd, retval=("rc",))
    assert result == (0,)


def test_run_rc_error():
    # cmd = ["false"]
    cmd = ["python", "-c", "raise SystemExit(1)"]
    result = subproc.run(cmd, retval=("rc",))
    assert result == (1,)


def test_run_rc_signal():
    # cmd = ["bash", "-c", "kill $$"]
    script = textwrap.dedent(
        """
        import os, signal
        os.kill(os.getpid(), signal.SIGTERM)
        """
    ).lstrip()
    cmd = ["python", "-c", script]
    result = subproc.run(cmd, retval=("rc",))
    assert result[0] == - signal.SIGTERM


def test_run_retval_valid():
    # cmd = ["echo", "foo"]
    cmd = ["python", "-c", "print('foo')"]
    result = subproc.run(cmd, retval=("stdout", "stderr", "rc"))
    assert len(result) == 3
    assert result == ("foo\n", "", 0)


def test_run_retval_invalid():
    # cmd = ["echo", "foo"]
    cmd = ["python", "-c", "print('foo')"]
    with pytest.raises(ValueError) as exc_info:
        subproc.run(cmd, retval=("stdin",))

    error_text = six.text_type(exc_info.value)
    assert "invalid retval:" in error_text
    assert "stdin" in error_text


def test_run_error():
    # cmd = ["false"]
    cmd = ["python", "-c", "raise SystemExit(1)"]
    with pytest.raises(RuntimeError) as exc_info:
        subproc.run(cmd)

    error_text = six.text_type(exc_info.value)
    assert "failed with exit code" in error_text


def test_run_logging(caplog):
    caplog.set_level(logging.DEBUG)
    cmd = ["python", "-c", "print('foo'); print('bar')"]
    subproc.run(cmd, retval=())

    records = caplog.records
    assert len(records) == 5

    assert records[0].levelno == logging.DEBUG
    assert records[0].msg == "run(%s, retval=%s, encoding=%s)"

    assert records[1].levelno == logging.INFO
    assert records[1].msg == "[%d] start: %s"

    assert records[2].levelno == logging.DEBUG
    assert records[2].msg == "[%d] stdout: %s"
    assert records[2].args[1] == "foo"

    assert records[3].levelno == logging.DEBUG
    assert records[3].msg == "[%d] stdout: %s"
    assert records[3].args[1] == "bar"

    assert records[4].levelno == logging.INFO
    assert records[4].msg == "[%d] done: %s=%r"


def test_run_logging_custom_levels(caplog):
    caplog.set_level(logging.DEBUG)
    script = textwrap.dedent(
        """
        from __future__ import print_function
        import sys
        print("foo", file=sys.stdout)
        print("bar", file=sys.stderr)
        """
    ).lstrip()
    cmd = ["python", "-c", script]
    subproc.run(cmd, retval=(), log_stdout=logging.WARNING,
                log_stderr=logging.ERROR)

    # We can't guarantee that the log record from stderr comes after the log
    # record from stdout - it depends on which buffer is available first:
    records = sorted(caplog.records, key=lambda r: r.levelno)
    assert len(records) == 5

    assert records[-2].levelno == logging.WARNING
    assert records[-2].msg == "[%d] stdout: %s"
    assert records[-2].args[1] == "foo"

    assert records[-1].levelno == logging.ERROR
    assert records[-1].msg == "[%d] stderr: %s"
    assert records[-1].args[1] == "bar"


def test_run_logging_no_levels(caplog):
    caplog.set_level(logging.DEBUG)
    script = textwrap.dedent(
        """
        from __future__ import print_function
        import sys
        print("foo", file=sys.stdout)
        print("bar", file=sys.stderr)
        """
    ).lstrip()
    cmd = ["python", "-c", script]
    subproc.run(cmd, retval=(), log_stdout=None, log_stderr=None)

    assert len(caplog.records) == 3
