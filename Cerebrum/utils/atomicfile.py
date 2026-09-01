# -*- coding: utf-8 -*-
#
# Copyright 2016-2026 University of Oslo, Norway
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
# Copyright 2002-2015 University of Oslo, Norway
"""
File-like objects with validation and atomic file replacement.

These file writers are all *atomic file writers*.  They write to a temporary
file, and only move the written file to its intended location when the file is
*closed*.  This final move will *replace* an existing file, if it exists.

By writing to a temporary file, and moving it into place, the target file
*won't* be truncated, and won't be incomplete if the write operation fails for
any reason.

This behavior is implemented by the base class, :class:`AtomicFileWriter`.
Subclasses like the :class:`SimilarSizeWriter` adds additional *file checks*,
which may prevent the target file from being *replaced* when certain conditions
aren't met.


cereconf
=========
FILE_CHECKS_DISABLED
    Disable *file checks* in AtomicFileWriter subclasses.

    When set to ``True``, all file checks in AtomicFileWriter subclasses are
    disabled.

SIMILARSIZE_CHECK_DISABLED
    Disable file checks in :class:`SimilarSizeWriter`.

    When set to ``True``, file checks in :class:`SimilarSizeWriter` are
    disabled.

SIMILARSIZE_LIMIT_MULTIPLIER
    Modifies the change limit for :class:`SimilarSizeWriter`.

    The default value is ``1.0``, i.e. no multiplier.  This setting can be
    raised or lowered to globally change the file size change limit.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import filecmp
import inspect
import io
import os
import random
import shutil
from string import ascii_lowercase, digits
from warnings import warn as _warn

import six

import cereconf

from . import reprutils


def _copydoc(obj, replace=False):
    """ Copy docstring from another object. """
    def wrapper(val):
        doc = getattr(obj, '__doc__', None) or ''
        if not replace:
            doc = "\n\n".join(
                (doc,
                 inspect.cleandoc(getattr(val, '__doc__', None) or '')))
        val.__doc__ = doc or None
        return val
    return wrapper


def _random_string(length, characters=ascii_lowercase + digits):
    """ Generate a random string of given length using the given characters."""
    random.seed()
    # pick "length" number of letters, then combine them to a string
    return ''.join([random.choice(characters) for _ in range(length)])


def _count_lines(fname):
    """ Return the number of lines in a file """
    if not os.path.exists(fname):
        return 0
    with open(fname) as f:
        return f.read().count(os.linesep) + 1


class FileChangeError(RuntimeError):
    """ Indicates a problem with the file change. """
    # TODO: Pass AtomicFileWriter object to error, and include info (name,
    # tmpname, etc...) in error message
    pass


class FileSizeChangeError(FileChangeError):
    """ Indicates a problem with a change in file size. """
    pass


class FileChangeTooBigError(FileSizeChangeError):
    """ Indicates that a file has changed too much. """
    pass


class FileTooSmallError(FileSizeChangeError):
    """ Indicates that the new file is too small. """
    pass


class FileWriterWarning(RuntimeWarning):
    """ Warnings about abnormal settings. """
    pass


def _fwarn(msg):
    """ Issue a FileWriterWarning with message `msg`. """
    # count consecutive stackframes from this module to find stacklevel
    frame = inspect.currentframe()
    this_filename = frame.f_code.co_filename
    local_stackframes = 0
    while frame and frame.f_code.co_filename == this_filename:
        local_stackframes += 1
        frame = frame.f_back
    _warn(msg, FileWriterWarning, stacklevel=local_stackframes+1)


class AtomicFileWriter(reprutils.ReprFieldMixin):
    """
    Atomic file writer.

    This class acts as a write-only file object that doesn't truncate the
    target file before all writing is finished, and the file is closed.  In
    practice, we write changes to a *temporary* file, and only replace the
    *target* file when closing the file object:

    1. When opening a target file (filename) for writing, this class
    will create a new, temporary file (filename.xyz).  This file is created in
    the same directory as the target file.

    2. Write all changes to the temporary file.

    3. When closing, move the *temporary* file to ``filename`` (replacing
       the target file if it exists).
    """
    repr_id = False
    repr_module = False
    repr_fields = ("name", "closed")

    tmpfile_ext_chars = ascii_lowercase + digits
    """ Characters to use in the temporary file name extension. """

    tmpfile_ext_length = 5
    """ Length of the temporary file extension. """

    tmpfile_ext_tries = 10
    """ Number of tries to create a unique temporary file. """

    def __init__(self, name,
                 mode='w',
                 buffering=-1,
                 encoding=None,
                 errors=None,
                 newline=None,
                 closefd=True,
                 replace_equal=False):
        """ Creates a new, writable file-like object.

        :param str name:
            The target filename (file to write).

        :param str mode:
            The file mode (see :attr:`file.mode`).  Note that files *must* be
            opened in a write mode ('a', 'w'). Appending ('a') can be slow, as
            it needs to make a full copy of the original file.

        :param bool replace_equal:
            Replace the file `name` even if no changes were written.

            If ``False``, this class will *not* replace an existing target
            file, if the temporary file is identical.  This is the default.

            If ``True``, we will replace the target ``name`` when it is
            identical to the temporary file that we actually wrote to.

        The other parameters are passed through to :func:`io.open`.
        """
        if not any(n in mode for n in 'aw'):
            raise ValueError(
                'Writer cannot open {!r} in read-only mode'
                ' (mode={!r})'.format(name, mode))

        self.__name = name
        tmpname = self.__generate_tmpname(name)

        if 'a' in mode and os.path.exists(name):
            shutil.copy2(name, tmpname)

        self.__file = io.open(tmpname,
                              mode=mode,
                              buffering=buffering,
                              encoding=encoding,
                              errors=errors,
                              newline=newline,
                              closefd=closefd)

        self.__replace_equal = replace_equal

    def __enter__(self):
        """
        Enter AtomicFileWriter context.

        This allows us to use the AtomicFileWriter class and subclasses as a
        file-like context:

        >>> with AtomicFileWriter('/tmp/foo') as f:
        >>>    f.write('some text')

        See __exit__ for context behaviour

        """
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Exit AtomicFileWriter context and handle exceptions.

        This method handles context exit. We will always attempt to close the
        actual file object, but:

        - If no exception was raised, we close the temporary file and
          then move it to the target file (replacing any previous version).

        - If an exception was raised, we close the temporary file without
          renaming it (i.e. *not* replacing any previous version).

        """
        if exc_type is None:
            # No exception was raised, exiting context normally
            self.close()
            return

        # An exception of type exc_type was raised
        try:
            self.__file.close()
        except Exception:
            pass
        six.reraise(exc_type, exc_value, traceback)

    @classmethod
    def __generate_tmpname(cls, realname):
        random.seed()
        for attempt in six.moves.range(cls.tmpfile_ext_tries):
            name = os.path.extsep.join(
                (realname,
                 ''.join([random.choice(cls.tmpfile_ext_chars) for n
                          in range(cls.tmpfile_ext_length)])))
            if not os.path.exists(name):
                return name
        raise IOError("Unable to find available temporary filename")

    @property
    def name(self):
        """ target file name. """
        return self.__name

    @property
    def tmpname(self):
        """ temporary file name. """
        return self.__file.name

    @property
    def replace(self):
        """ if the temporary file should replace the target file. """
        try:
            return self.__replace
        except AttributeError:
            return True

    @replace.setter
    def replace(self, value):
        self.__replace = bool(value)

    @property
    @_copydoc(io.FileIO.mode)
    def mode(self):
        return self.__file.mode

    @property
    def errors(self):
        """
        The error setting of the file encoder.

        See :func:`io.open` and :class:`codecs.Codec` for details.
        """
        return self.__file.errors

    @property
    def encoding(self):
        """
        The encoding of the file stream.

        See :func:`io.open` for details.
        """
        return self.__file.encoding

    @property
    def discarded(self):
        """
        True if any changes were discarded without replacing the target file.

        This can happen if AtomicFileWriter is configured NOT to replace the
        target file when no changes are present.
        """
        try:
            return self.__discarded
        except AttributeError:
            return False

    @property
    def replaced(self):
        """ True if the target file has been replaced with a new file. """
        try:
            return self.__replaced
        except AttributeError:
            return False

    @property
    def closed(self):
        """ True if the temporary file is closed. """
        return self.__file.closed

    @property
    def validate(self):
        """ True if the tmpfile will get validated. """
        try:
            return self.__validate
        except AttributeError:
            return True

    @validate.setter
    def validate(self, value):
        self.__validate = bool(value)
        if not self.__validate:
            _fwarn('File checks are now disabled')

    def validate_output(self):
        """ Validate output (i.e. the temporary file) prior to renaming it.

        This method is intended to be overridden in subclasses.  If
        the content fails to meet the method's expectations, it should
        raise an exception.

        :raise FileChangeError:
            When the written file has changed beyond the acceptable criteria.
        """
        pass

    @_copydoc(io.FileIO.close)
    def close(self):
        """
        In addition to the normal close behaviour:

        Closes the temporary file, and if applicable, replaces the target file.
        Updates the ``discarded`` and ``replaced`` properties:

        ``replaced``
            ``True`` if ``tmpname`` replaced ``name``.

        ``discarded``
            ``True`` if ``tmpname`` is deleted without replacing ``name``.

        """
        if self.closed:
            return
        ret = self.__file.close()
        if ret is None:
            # close() didn't encounter any problems.  Do validation of
            # the temporary file's contents.  If that doesn't raise
            # any exceptions rename() to the real file name.
            if getattr(cereconf, 'FILE_CHECKS_DISABLED', False):
                _fwarn("All file checks are disabled by global setting"
                       " 'cereconf.FILE_CHECKS_DISABLED'")
            elif not self.validate:
                _fwarn("All file checks are disabled")
            else:
                self.validate_output()

            if ((not self.__replace_equal) and
                    os.path.exists(self.name) and
                    filecmp.cmp(self.tmpname, self.name, shallow=False)):
                os.unlink(self.tmpname)
                self.__discarded = True
            elif self.replace:
                os.rename(self.tmpname, self.name)
                self.__replaced = True
        return ret

    @_copydoc(io.FileIO.flush)
    def flush(self):
        return self.__file.flush()

    @_copydoc(io.FileIO.write)
    def write(self, data):
        return self.__file.write(data)


class SimilarSizeWriter(AtomicFileWriter):
    """
    This file writer will fail if the file size changes too much.

    Clients will normally govern the exact limits for 'similar size'
    themselves, but there are times when it is convenient to have
    central overrides/modifications of these values. SimilarSizeWriter
    therefore makes use of the following ``cereconf`` variables:

    SIMILARSIZE_CHECK_DISABLED
        If this is set to True, no checks will be done when validating the file
        size, i.e. validation will always succeed.

    SIMILARSIZE_LIMIT_MULTIPLIER
        Modifies the change limit by multiplying it by the given number
        (default is 1.0, i.e. to not modify the value given by the client)

    Since central changes to the defaults for these values (especially
    central disabling) is risky, non-default values for these
    variables will generate warnings.

    Clients can also disable/enable the checks directly by setting the
    `validate` attribute of the writer-object, though this will not override
    ``SIMILARSIZE_CHECK_DISABLED``.
    """

    DEFAULT_FACTOR = 1.0

    def __init__(self, *args, **kwargs):
        super(SimilarSizeWriter, self).__init__(*args, **kwargs)
        self.__factor = self.DEFAULT_FACTOR

    @property
    def max_pct_change(self):
        """ Maximum change allowed for the new file, in percent. """
        try:
            return self.__percentage * self.__factor
        except AttributeError:
            return None

    @max_pct_change.setter
    def max_pct_change(self, percent):
        self.__percentage = float(percent)

    @max_pct_change.deleter
    def max_pct_change(self):
        del self.__percentage

    def validate_output(self):
        super(SimilarSizeWriter, self).validate_output()

        if cereconf.SIMILARSIZE_CHECK_DISABLED:
            _fwarn("Similar size check disabled by global setting"
                   " 'cereconf.SIMILARSIZE_CHECK_DISABLED'")
            return
        if self.max_pct_change is None:
            _fwarn("No limit for similar size check set")
            return
        if not os.path.exists(self.name):
            return
        old_size = os.path.getsize(self.name)
        if old_size == 0:
            return

        new_size = os.path.getsize(self.tmpname)
        change_percentage = 100 * (float(new_size) / old_size) - 100
        if abs(change_percentage) > self.max_pct_change:
            raise FileChangeTooBigError(
                "SimilarSizeWriter: File size of {!r} changed more than"
                " {:.1f}% ({:d} bytes -> {:d} bytes, {:+.2f}%)".format(
                    self.name, self.max_pct_change, old_size, new_size,
                    change_percentage))


class SimilarLineCountWriter(AtomicFileWriter):
    """
    This file writer will fail if the line count changes too much.

    This file will raise a :class:`.FileChangeTooBig` error if the file changes
    more than a certain number of lines. All other file changes are permitted,
    regardless of the original file size.
    """

    @property
    def max_line_change(self):
        """ change limit for the new file, in lines. """
        try:
            return self.__limit
        except AttributeError:
            return None

    @max_line_change.setter
    def max_line_change(self, line_count):
        self.__limit = int(line_count)

    @max_line_change.deleter
    def max_line_change(self):
        try:
            del self.__limit
        except AttributeError:
            pass

    def validate_output(self):
        super(SimilarLineCountWriter, self).validate_output()

        if self.max_line_change is None:
            _fwarn("No limit for similar line count check set")
            return
        if not os.path.exists(self.name):
            return

        if self.max_line_change is not None:
            old_size = _count_lines(self.name)
            new_size = _count_lines(self.tmpname)
            if abs(new_size - old_size) > self.max_line_change:
                raise FileChangeTooBigError(
                    "{!s}: File changed more than {:d} lines"
                    " ({:d} -> {:d}, {:+d} lines)".format(
                        self.name, self.max_line_change,
                        old_size, new_size, new_size - old_size))


class MinimumSizeWriter(AtomicFileWriter):
    """
    This file writer will fail if the file size is too small.

    This file will raise a :class:`.FileTooSmallError` if the final file is
    less than a certain number of bytes.  All other file size changes are
    permitted, regardless of the original file's size.
    """

    ABSOLUTE_MIN_SIZE = 0

    @property
    def min_size(self):
        """ minimum file size for the changed file, in bytes. """
        try:
            return self.__limit
        except AttributeError:
            return self.ABSOLUTE_MIN_SIZE

    @min_size.setter
    def min_size(self, size):
        self.__limit = max(int(size), self.ABSOLUTE_MIN_SIZE)

    @min_size.deleter
    def min_size(self):
        del self.__limit

    def validate_output(self):
        super(MinimumSizeWriter, self).validate_output()

        if not self.min_size:
            _fwarn("No limit for minimum size check set")
            return

        new_size = os.path.getsize(self.tmpname)
        if new_size < self.min_size:
            raise FileTooSmallError(
                "{!s}: File is too small (current: {:d} bytes,"
                " minimum allowed: {:d} bytes".format(
                    self.name, new_size, self.min_size))


class AtomicStreamRecoder(AtomicFileWriter):
    """
    AtomicFileWriter with bytestring support.

    ``xmlprinter.xmlprinter`` encodes data in the desired encoding before
    writing to the stream, and AtomicFileWriter *requires* unicode-objects to
    be written.

    This hack turns AtomicFileWriter into a bytestring writer. Just make sure
    the AtomicStreamRecoder is configured to use the same encoding as the
    xmlprinter.

    The *proper* fix would be to retire the xmlprinter module, and replace it
    with something better.
    """
    def write(self, data):
        if isinstance(data, bytes) and self.encoding:
            # will be re-encoded in the same encoding by 'write'
            data = data.decode(self.encoding)
        return super(AtomicStreamRecoder, self).write(data)


class SimilarSizeStreamRecoder(SimilarSizeWriter):
    """
    SimilarSizeWriter with bytestring support.

    See :class:`.AtomicStreamRecoder` for details.
    """

    def write(self, data):
        if isinstance(data, bytes) and self.encoding:
            # will be re-encoded in the same encoding by 'write'
            data = data.decode(self.encoding)
        return super(SimilarSizeStreamRecoder, self).write(data)
