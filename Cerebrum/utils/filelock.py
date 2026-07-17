# encoding: utf-8
#
# Copyright 2015-2024 University of Oslo, Norway
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
This module contains simple file locking tools.

The code is based on <https://github.com/derpston/python-simpleflock/>, which
is published under the terms of WTFPL <http://www.wtfpl.net/>.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import errno
import fcntl
import os
import time


DEFAULT_TIMEOUT = 60


class SimpleFlock(object):
    """
    Provides the simplest possible interface to flock-based file locking.

    Intended for use as a context manager (``with`` syntax).
    It will create/truncate/delete the lock file as necessary.
    """

    def __init__(self, path, lock_type, timeout=None):
        self._path = path
        if lock_type is None:
            raise LockError("Must specify lock_type")
        self.lock_type = lock_type
        self._timeout = timeout
        self._fd = None

    def __enter__(self):
        self._fd = os.open(self._path, os.O_CREAT)
        start_lock_search = time.time()
        while True:
            try:
                fcntl.flock(self._fd, self.lock_type | fcntl.LOCK_NB)
                # Lock acquired!
                return
            except IOError as ex:
                # Resource temporarily unavailable
                if ex.errno != errno.EAGAIN:
                    raise
                elif (self._timeout is not None
                      and time.time() > (start_lock_search + self._timeout)):
                    # Exceeded the user-specified timeout.
                    raise LockError("Timeout exceeded for lock "
                                    + repr(self._path))

            # It would be nice to avoid an arbitrary sleep here, but spinning
            # without a delay is also undesirable.
            time.sleep(0.1)

    def __exit__(self, *args):
        fcntl.flock(self._fd, fcntl.LOCK_UN)
        os.close(self._fd)
        self._fd = None

        # Try to remove the lock file, but don't try too hard because it is
        # unnecessary.  This is mostly to help the user see whether a lock
        # exists by examining the filesystem.
        try:
            os.unlink(self._path)
        except Exception:
            pass


class LockError(Exception):
    pass


class ReadLock(SimpleFlock):
    """Acquires a shared file lock."""

    def __init__(self, path, timeout=DEFAULT_TIMEOUT):
        super(ReadLock, self).__init__(path,
                                       lock_type=fcntl.LOCK_SH,
                                       timeout=timeout)


class WriteLock(SimpleFlock):
    """Acquires an exclusive file lock."""

    def __init__(self, path, timeout=DEFAULT_TIMEOUT):
        super(WriteLock, self).__init__(path,
                                        lock_type=fcntl.LOCK_EX,
                                        timeout=timeout)
