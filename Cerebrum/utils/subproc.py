#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2025-2026 University of Oslo, Norway
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
Utilities for spawning processes.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import io
import logging
import select
import shlex
import subprocess
import sys

try:
    from shlex import quote as _quote
except ImportError:
    from pipes import quote as _quote

from . import text_compat

logger = logging.getLogger(__name__)


def format_command(argv):
    """
    Format a command string from an argument list

    :type argv: list[str]
    :rtype: str
    """
    if hasattr(shlex, "join"):
        return shlex.join(argv)
    else:
        return ' '.join(_quote(i) for i in argv)


RETURN_STDOUT = "stdout"
RETURN_STDERR = "stderr"
RETURN_RC = "rc"

_RETURN_TYPES = (
    RETURN_STDOUT,
    RETURN_STDERR,
    RETURN_RC,
)


def run(argv, retval=None, encoding="utf-8",
        log_stdout=logging.DEBUG, log_stderr=logging.WARNING):
    """
    Run a subprocess and log output.

    This is a re-implementation of `Cerebrum.Utils.spawn_and_log_output`
    with less odd behaviour.

    :type argv: list, tuple
    :param argv: The command and arguments to run

    :type retval: tuple
    :param retval:
        A tuple with the return values for this function.

        E.g. retval=("stdout", "stderr", "rc") would return a tuple with
        those values, in that order.

    :type encoding: str
    :param encoding: expected stdout/stderr output encoding

    :param log_stdout:
        Log stdout at log level log_stdout (or None to ignore)

    :param log_stderr:
        Log stderr at log level log_stderr (or None to ignore)

    :rtype: tuple
    :returns:
        Up to three values, in the order specified by retval.

    :raises RuntimeError:
        On non-zero exit code, unless "rc" is present in retval

        If "rc" is specified as a return value, we assume you *don't* want an
        error.
    """
    logger.debug("run(%s, retval=%s, encoding=%s)",
                 repr(argv), repr(retval), repr(encoding))
    if retval is None:
        retval = ()
    for return_type in retval:
        if return_type not in _RETURN_TYPES:
            raise ValueError("invalid retval: " + repr(return_type))

    use_stdout = log_stdout is not None or RETURN_STDOUT in retval
    use_stderr = log_stderr is not None or RETURN_STDERR in retval
    py3_args = {'encoding': None} if sys.version_info > (3,) else {}
    proc = subprocess.Popen(
        argv,
        stdout=subprocess.PIPE if use_stdout else None,
        stderr=subprocess.PIPE if use_stderr else None,
        universal_newlines=False,
        **py3_args
    )
    write_lines = {
        fd: []
        for fd in (proc.stdout, proc.stderr)
        if fd is not None
    }
    pretty = format_command(argv)

    # fanout stdout, stderr -> loggers
    output_logger = logger  # in case we want to change logger
    output_logger.info("[%d] start: %s", proc.pid, pretty)
    if use_stdout and log_stdout is not None:
        write_lines[proc.stdout].append(
            lambda line: output_logger.log(log_stdout, "[%d] stdout: %s",
                                           proc.pid, line.rstrip())
        )
    if use_stderr and log_stderr is not None:
        write_lines[proc.stderr].append(
            lambda line: output_logger.log(log_stderr, "[%d] stderr: %s",
                                           proc.pid, line.rstrip())
        )

    # fanout strout, stderr -> buffers
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    if use_stdout and RETURN_STDOUT in retval:
        write_lines[proc.stdout].append(stdout_buffer.write)
    if use_stderr and RETURN_STDERR in retval:
        write_lines[proc.stderr].append(stderr_buffer.write)

    # fanout - read and process lines from fd -> write_lines[fd]
    while write_lines:
        ready, _, _ = select.select(write_lines.keys(), [], [])
        for fd in ready:
            if fd not in write_lines:
                continue
            handlers = write_lines[fd]
            line = text_compat.to_text(fd.readline(), encoding=encoding)
            if line:
                for fn in handlers:
                    fn(line)
            else:
                fd.close()
                del write_lines[fd]

    # handle exit
    proc.wait()
    rc = proc.returncode

    retval_map = {
        RETURN_STDOUT: stdout_buffer.getvalue,
        RETURN_STDERR: stderr_buffer.getvalue,
        RETURN_RC: (lambda: rc),
    }

    if rc < 0:
        # err = True
        level = logging.ERROR
        etype = "signal"
    elif rc > 0:
        # err = True
        level = logging.ERROR
        etype = "exit"
    else:
        # err = False
        level = logging.INFO
        etype = "exit"

    output_logger.log(level, "[%d] done: %s=%r", proc.pid, etype, rc)

    if rc and RETURN_RC not in retval:
        raise RuntimeError("command %r failed with exit code: %d"
                           % (pretty, rc))

    return tuple(retval_map[r]() for r in retval)


def _main():
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(levelname)s [%(name)s]: %(message)s",
    )

    argv = sys.argv[1:]
    stdout, stderr = run(argv, retval=("stdout", "stderr"))
    print(format_command(argv), "stdout:", len(stdout), "chars")
    print(format_command(argv), "stderr:", len(stderr), "chars")


if __name__ == "__main__":
    _main()
