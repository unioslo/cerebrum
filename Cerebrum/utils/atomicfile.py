# coding: utf-8
#
# Copyright 2016 University of Oslo, Norway
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
""" File writers. """

import cereconf
import os.path
import filecmp
import random
from string import ascii_lowercase, digits


def random_string(length, characters=ascii_lowercase + digits):
    """Generate a random string of given length using the given characters."""
    random.seed()
    # pick "length" number of letters, then combine them to a string
    return ''.join([random.choice(characters) for _ in range(length)])


class AtomicFileWriter(object):

    def __init__(self, name, mode='w', buffering=-1, replace_equal=False):
        self._name = name
        self._tmpname = self.make_tmpname(name)
        self.__file = open(self._tmpname, mode, buffering)
        self.closed = False
        self.replaced_file = False
        self._replace_equal = replace_equal

    def close(self, dont_rename=False):
        if self.closed:
            return
        ret = self.__file.close()
        self.closed = True
        if ret is None:
            # close() didn't encounter any problems.  Do validation of
            # the temporary file's contents.  If that doesn't raise
            # any exceptions rename() to the real file name.
            self.validate_output()
            if not self._replace_equal:
                if (os.path.exists(self._name) and
                        filecmp.cmp(self._tmpname, self._name, shallow=0)):
                    os.unlink(self._tmpname)
                else:
                    if not dont_rename:
                        os.rename(self._tmpname, self._name)
                    self.replaced_file = True
            else:
                if not dont_rename:
                    os.rename(self._tmpname, self._name)
                self.replaced_file = True
        return ret

    def validate_output(self):
        """Validate output (i.e. the temporary file) prior to renaming it.

        This method is intended to be overridden in subclasses.  If
        the content fails to meet the method's expectations, it should
        raise an exception.

        """
        pass

    # TODO: Use the temp file functions provided by the standard library!
    def make_tmpname(self, realname):
        for _ in range(10):
            name = realname + '.' + random_string(5)
            if not os.path.exists(name):
                break
        else:
            raise IOError("Unable to find available temporary filename")
        return name

    def flush(self):
        return self.__file.flush()

    def write(self, data):
        return self.__file.write(data)


class FileSizeChangeError(RuntimeError):

    """Indicates a problem related to change in file size for files
    updated by the *SizeWriter classes.
    """
    pass


class FileChangeTooBigError(FileSizeChangeError):

    """Indicates that a file has either grown or been reduced beyond
    acceptable limits.
    """
    pass


class SimilarSizeWriter(AtomicFileWriter):

    """This file writer will fail if the file size has changed by more
    than a certain percentage (if using 'set_size_change_limit')
    and/or by a certain number of lines (if using
    'set_line_count_change_limit') from the old to the new version.

    Clients will normally govern the exact limits for 'similar size'
    themselves, but there are times when it is convenient to have
    central overrides/modifications of these values. SimilarSizeWriter
    therefore makes use of the following 'cereconf'-variables:

    SIMILARSIZE_CHECK_DISABLED - If this is set to True, no checks
    will be done when validating the file size, i.e. validation will
    always succeed.

    SIMILARSIZE_LIMIT_MULTIPLIER - Modifies the change limit by
    multiplying it by the given number (default is 1.0, i.e. to not
    modify the value given by the client)

    Since central changes to the defaults for these values (especially
    central disabling) is risky, non-default values for these
    variables will generate warnings via the logger.

    Clients can also disable/enable the checks directly by calling the
    'set_checks_enabled', though this will not override
    SIMILARSIZE_CHECK_DISABLED.

    """

    __checks_enabled = True

    def __init__(self, *args, **kwargs):
        super(SimilarSizeWriter, self).__init__(*args, **kwargs)
        from Cerebrum.Utils import Factory
        self.__percentage = self.__line_count = None
        self._logger = Factory.get_logger("cronjob")

    def set_checks_enabled(self, new_enabled_status):
        """Method for activating (new_enabled_status is 'True') or
        de-activating (new_enabled_status is 'False') all similar size
        checks being run by a given program.

        Default state, before this method has been called, is for
        checks to be enabled.

        """
        self._logger.debug("SimilarSizeWriter: setting checks_enabled to '%s'"
                           % new_enabled_status)
        SimilarSizeWriter.__checks_enabled = new_enabled_status

    def set_size_change_limit(self, percentage):
        """Method for setting a limit based on percentage change in
        file size (bytes). The exact percentage can be centrally
        modified by setting SIMILARSIZE_SIZE_LIMIT_MULTIPLIER to
        something other than 1.0 in cereconf.

        """
        self.__percentage = percentage * cereconf.SIMILARSIZE_LIMIT_MULTIPLIER
        if cereconf.SIMILARSIZE_LIMIT_MULTIPLIER != 1.0:
            self._logger.warning("SIMILARSIZE_LIMIT_MULTIPLIER is set to "
                                 "a value other than 1.0; change limit "
                                 "will be %s%% rather than client's explicit "
                                 "setting of %s%%.",
                                 self.__percentage, percentage)
        self._logger.debug("SimilarSize size change limit set to '%d'",
                           self.__percentage)

    def set_line_count_change_limit(self, num):
        """Method for setting a limit based on change in number of
        lines in the generated file. The exact number can be centrally
        modified by setting SIMILARSIZE_SIZE_LIMIT_MULTIPLIER to
        something other than 1.0 in cereconf.

        """
        self.__line_count = num * cereconf.SIMILARSIZE_LIMIT_MULTIPLIER
        if cereconf.SIMILARSIZE_LIMIT_MULTIPLIER != 1.0:
            self._logger.warning(("SIMILARSIZE_LIMIT_MULTIPLIER is set to " +
                                 "a value other than 1.0; change limit " +
                                 "will be %s lines rather than client's "
                                 "explicit " +
                                 "setting of %s lines.")
                                 % (self.__line_count, num))
        self._logger.debug("SimilarSize line count change limit set to '%d'"
                           % self.__line_count)

    def __count_lines(self, fname):
        """Return the number of lines in a file"""
        return open(fname).read().count(os.linesep)

    def validate_output(self):
        """Checks if the new file's size change (compared to the old
        file) is within acceptable limits as previously set. If the
        file did not exist or if the old file was empty, the new file
        will be considered 'valid' no matter how large or small it is.

        If neither file size nor line count are set, an AssertionError
        will be raised.

        If SIMILARSIZE_CHECK_DISABLED is set to 'True' in cereconf,
        validation will always succeed, no matter what, as is the case
        if 'set_checks_enabled(False)' has been called.

        """
        if cereconf.SIMILARSIZE_CHECK_DISABLED:
            # Having the check globally disabled is not A Good Thing(tm),
            # so we warn about it, in all cases.
            self._logger.warning("SIMILARSIZE_CHECK_DISABLED is 'True'; no "
                                 "'similar filesize' comparisons will be done.")
            return
        if not SimilarSizeWriter.__checks_enabled:
            # Checks have been specifically disabled by a client, but
            # we'll still inform them about it, in case they don't
            # realize it
            self._logger.info("Client has disabled similarsize checks for now;"
                              "no 'similar filesize' comparisons will be done.")
            return
        if not os.path.exists(self._name):
            return
        old = os.path.getsize(self._name)
        if old == 0:
            # Any change in size will be an infinite percent-wise size
            # change.  Treat this as if the old file did not exist at
            # all.
            return
        new = os.path.getsize(self._tmpname)
        assert self.__percentage or self.__line_count
        if self.__percentage:
            change_percentage = 100 * (float(new) / old) - 100
            if abs(change_percentage) > self.__percentage:
                raise FileChangeTooBigError(
                    "%s: File size changed more than %d%%: "
                    "%d -> %d (%+.1f)" % (self._name, self.__percentage,
                                          old, new, change_percentage))
        if self.__line_count:
            old = self.__count_lines(self._name)
            new = self.__count_lines(self._tmpname)
            if abs(old - new) > self.__line_count:
                raise FileChangeTooBigError(
                    "%s: File changed more than %d lines: "
                    "%d -> %d (%i)" % (self._name, self.__line_count,
                                       old, new, abs(old - new)))


class FileTooSmallError(FileSizeChangeError):

    """Indicates that the new version of the file in question is below
    acceptable size.
    """
    pass


class MinimumSizeWriter(AtomicFileWriter):

    """This file writer would fail, if the new file size is less than
    a certain number of bytes. All other file size changes are
    permitted, regardless of the original file's size.
    """

    def set_minimum_size_limit(self, size):
        self.__minimum_size = size

    def validate_output(self):
        super(MinimumSizeWriter, self).validate_output()

        new_size = os.path.getsize(self._tmpname)
        if new_size < self.__minimum_size:
            raise FileTooSmallError("%s: File is too small: current: %d, minimum allowed: %d" %
                                   (self._name, new_size, self.__minimum_size))
