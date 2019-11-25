# encoding: utf-8
""" Log handlers. """
from __future__ import absolute_import

import codecs
import logging
import os
import re
import stat
import string
import sys
import time

from Cerebrum.modules.job_runner.times import to_seconds
from .config import LoggerConfig
from .stream import CerelogStreamWriter


DEFAULT_DIRECTORY = LoggerConfig.logdir.default
DEFAULT_DIR_PERMS = 0o770
DEFAULT_ENCODING = 'utf-8'
_MIDNIGHT = to_seconds(days=1)


def get_script_name():
    # TODO: Ugh, find a better way...
    #       Maybe walk up the stack and identify the filename?
    #       We still need to avoid runpy.py and friends...
    return os.path.basename(sys.argv[0])


class BaseFileHandler(logging.FileHandler, object):
    """ new-style FileHandler class. """
    # This allows us to implement descriptors in mixins.
    pass


class MakeDirectoriesMixin(BaseFileHandler):
    """ Make parent directories for logfiles. """

    directory_permissions = DEFAULT_DIR_PERMS

    def _open(self):
        path = os.path.dirname(os.path.abspath(self.baseFilename))
        if not os.path.exists(path):
            os.makedirs(path, self.directory_permissions)
        return super(MakeDirectoriesMixin, self)._open()


class PermissionMixin(BaseFileHandler):
    """ This mixin enforces log file permissions.

    Note that the permissions are changed *after* the file has been opened
    (since we're unable to change them if the file does not exist yet).
    """

    def __init__(self, filename, permissions=None, **kwargs):
        """
        :param int permissions:
            Numerical permission mode passed to os.chmod()
        """
        # TODO: Translate human-readable permissions (u=rw,g=r,o-rwx)?
        self.permissions = permissions
        super(PermissionMixin, self).__init__(filename, **kwargs)

    def _open(self):
        stream = super(PermissionMixin, self)._open()
        # Force our permissions
        if self.permissions is not None:
            os.chmod(self.baseFilename, self.permissions)
        return stream


class FilenameTemplateMixin(BaseFileHandler):
    """ Configure and inject variables into the filename.

    FileHandlers with this mixins will have the 'filename' argument modified in
    the following manner:

    - Strings like $$, $identifier, ${identifier} will be interpreted and
      substituted with `string.Template`.

    - Strings like %c, will be interpreted and substituted using
      `time.strftime`.

    The following `$`-prefixed variables will work:

    $root
        the configured root directory for log files.

    $script
        the name of the currently executed script

    $datetime
        a default date and time date format `strftime`
    """

    default_context = {
        'root': DEFAULT_DIRECTORY,
        'date': '%Y-%m-%dT%H:%M:%S',
        'script': get_script_name,
    }

    @classmethod
    def configure(cls, config):
        cls.default_context['root'] = config.logdir

    def __init__(self, filename, **kwargs):
        """
        :param str directory:
            Directory to place log files in.

        :param str filename: A filename or filename template for log files.
        """
        filename = self._build_filename(filename)
        super(FilenameTemplateMixin, self).__init__(filename, **kwargs)

    def _build_filename(self, template_string):
        """ build filename from template string. """
        template = string.Template(template_string)
        context = dict()

        if not template.template:
            raise ValueError(
                "invalid filename {0}".format(repr(template_string)))

        for key, val in self.default_context.items():
            context[key] = val() if callable(val) else val

        try:
            filename = template.substitute(**context)
        except KeyError as e:
            raise ValueError('invalid filename substitution {0}'.format(e))

        return time.strftime(filename)


class CerelogStreamMixin(BaseFileHandler):
    """ Injects a custom cerebrum StreamWriter into the FileHandler. """

    default_encoding = DEFAULT_ENCODING

    def _open(self):
        """ open steam using CerelogStreamWriter. """
        # TODO: Replace CerelogStreamWriter with default StreamWriter
        #       Then we could get rid of this entire method.
        mode = self.mode
        if 'b' not in mode:
            mode = mode + 'b'

        encoding = self.encoding or self.default_encoding

        # We want to make sure that both unicode and str objects can be output
        # to the logger without the client code having to care about the
        # situation.
        #
        # The problem with the object returned from codecs.open(), is that it
        # assumes that whatever is given to write() is *already* in the
        # encoding specified as the parameter. This works most of the time,
        # but breaks down when we pass a string (byte seq) with øæå in latin-1
        # to a stream that assumes the input is in UTF-8.
        #
        # This is a slight variation of what codecs.open() does (and python's
        # logging module uses codecs.open() to enable various encodings for
        # the logs on file)
        stream = open(self.baseFilename, mode)
        encoder, decoder, reader, writer = codecs.lookup(encoding)

        srw = codecs.StreamReaderWriter(stream, reader, CerelogStreamWriter)
        srw.encoding = encoding
        srw.writer.encoding = srw.encoding
        srw.writer.encode = encoder

        self.stream = srw
        return self.stream


class DelayedFileHandler(FilenameTemplateMixin,
                         MakeDirectoriesMixin,
                         PermissionMixin,
                         CerelogStreamMixin,
                         BaseFileHandler,
                         object):
    """ A handler class which delays opening files until necessary.

    This is the base file handler for all Cerebrum logging. It's basically
    L{logging.FileHandler}, but will:

    - Create parent directories, if they are missing
    - Set file permissions, if given as 'persmissions' (see PermissionMixin)
    - Expand log filename using template variables
    - Use the CerebrumStreamWriter to handle encoding.

    """
    def __init__(self, *args, **kwargs):
        kwargs['delay'] = True
        super(DelayedFileHandler, self).__init__(*args, **kwargs)


class OneRunHandler(DelayedFileHandler):
    """A file handler that logs one job run into exactly one log file.

    Basically, this is just like a FileHandler, except that it uses a file
    naming scheme; The 'filename' is turned into a directory, and each new
    OneRunHandler will create a separate file with a timestamped name in this
    directory.
    """

    # TODO: Replace this with a generic CerebrumHandler that requires
    # 'filename' just like the others?

    default_filename = "${root}/${script}/log-${date}"

    def __init__(self, filename=default_filename, **kwargs):
        super(OneRunHandler, self).__init__(filename, **kwargs)


# TODO: Cronjobs should use OneRunHandler


class CerebrumRotatingHandler(DelayedFileHandler):
    """ Cerebrum's own rotating handler.

    This handler rotates the logs much like handlers.RotatingFileHandler,
    except that the file opening is delayed, and rotation requires threading
    locks.

    By default, the file grows indefinitely. You can specify particular values
    of L{maxBytes} and L{backupCount} to allow the file to rollover at a
    predetermined size.

    Rollover occurs whenever the current log file is nearly maxBytes in
    length. If BACKUPCOUNT is >= 1, the system will successively create new
    files with the same pathname as the base file, but with extensions '.1',
    '.2' etc. appended to it. For example, with a BACKUPCOUNT of 5 and a base
    file name of 'app.log', you would get 'app.log', 'app.log.1', 'app.log.2',
    ... through to 'app.log.5'. The file being written to is always 'app.log'.
    When it gets filled up, it is closed and renamed to 'app.log.1', and if
    files 'app.log.1', 'app.log.2' etc. exist, then they are renamed to
    'app.log.2', 'app.log.3' etc.  respectively.

    If L{maxBytes} is zero, rollover never occurs.
    """

    def __init__(self, filename, maxBytes=0, backupCount=0, **kwargs):
        # 'w' would truncate, and it makes no sense for this handler.
        if maxBytes > 0:
            kwargs['mode'] = 'a+'

        super(CerebrumRotatingHandler, self).__init__(filename, **kwargs)
        self.maxBytes = maxBytes
        self.backupCount = backupCount

    def emit(self, record):
        """Emit a record.

        Output the record to the file, catering for rollover as described
        in doRollover().

        """
        try:
            if self.shouldRollover(record):
                self.doRollover(record)
            super(CerebrumRotatingHandler, self).emit(record)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)

    def shouldRollover(self, record):
        """Should we rotate the log files?"""

        # IVR 2007-02-13 TBD: There is a slight problem with delayed file
        # opening here: the stream is not open until the first write. So,
        # technically, we can cross a rollover limit :(

        # maxBytes == 0 => no rollover. Ever
        if self.maxBytes <= 0:
            return False

        msg = self.format(record)
        if (self.stream and not self.stream.closed and
                self.stream.tell() + len(msg) >= self.maxBytes):
            return True
        return False

    def doRollover(self, record):
        """This is a slightly modified copy of logging.RotatingFileHandler.

        Essentially, we need to prevent multiple threads from screwing things
        up.

        """
        # IVR 2007-11-27 If two threads sharing the same logger (e.g. in
        # job_runner) arrive here simultaneously, we need to make sure that
        # only one of them actually rotates the logger. The only way to force
        # this is to make sure that the calling thread has to grab a lock and
        # perform the entire operation as a critical section.
        #
        # Additionally, no matter how this method fails, the lock must be
        # released.
        try:
            self.acquire()

            # Check one more time, if we *really* should roll over. Perhaps a
            # differnt thread has already done that.
            if not self.shouldRollover(record):
                return

            if self.stream and not self.stream.closed:
                self.stream.close()

            try:
                # Do NOT move the files, unless self.baseFilename actually
                # exists. This is just a precaution (it should not be
                # necessary, though).
                if (os.path.exists(self.baseFilename)
                        and self.backupCount > 0):
                    for i in range(self.backupCount - 1, 0, -1):
                        sfn = "%s.%d" % (self.baseFilename, i)
                        dfn = "%s.%d" % (self.baseFilename, i + 1)
                        if os.path.exists(sfn):
                            if os.path.exists(dfn):
                                os.remove(dfn)

                            os.rename(sfn, dfn)

                    dfn = self.baseFilename + ".1"
                    if os.path.exists(dfn):
                        os.remove(dfn)

                    os.rename(self.baseFilename, dfn)

                # delayed opening. The superclass will take care of everything
                self.stream = None
            except:
                # Something went wrong before we managed to complete
                # rotations. Let's re-open the stream and hope for the best. In
                # case of failure, it is preferrable to write to the same file,
                # rather than barf with some sort of error message. If the
                # error is transient, all will be well and the file will be
                # rotated next time around. If not, at least we'd be able to
                # scribble some messages to the file.
                if self.stream and self.stream.closed:
                    self._open()
                    # Make sure the caller knows that something broke down.
                    raise
        finally:
            self.release()


class CerebrumTimedRotatingHandler(CerebrumRotatingHandler):
    """Timed rotating handler with Cerebrum

    This handler rotates based on time just as the TimedRotatingFileHandler
    found in the standard logging library, but is thread safe like
    CerebrumRotatingHandler.
    """
    _intervals = {
        'S': {
            'interval': to_seconds(seconds=1),
            'suffix': "%Y-%m-%d_%H-%M-%S",
            'match': r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}$",
        },
        'M': {
            'interval': to_seconds(minutes=1),
            'suffix': "%Y-%m-%d_%H-%M",
            'match': r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}$",
        },
        'H': {
            'interval': to_seconds(hours=1),
            'suffix': "%Y-%m-%d_%H",
            'match': r"^\d{4}-\d{2}-\d{2}_\d{2}$",
        },
        'D': {
            'interval': to_seconds(days=1),
            'suffix': "%Y-%m-%d",
            'match': r"^\d{4}-\d{2}-\d{2}$",
        },
        'W': {
            'interval': to_seconds(weeks=1),
            'suffix': "%Y-%m-%d",
            'match': r"^\d{4}-\d{2}-\d{2}$",
        },
    }

    def __init__(self, filename, when='H', interval=1, backupCount=0,
                 utc=False, **kwargs):
        super(CerebrumRotatingHandler, self).__init__(filename, **kwargs)
        self.when = when.upper()
        self.backupCount = backupCount
        self.utc = utc
        # Calculate the real rollover interval, which is just the number of
        # seconds between rollovers.  Also set the filename suffix used when
        # a rollover occurs.  Current 'when' events supported:
        # S - Seconds
        # M - Minutes
        # H - Hours
        # D - Days
        # midnight - roll over at midnight
        # W{0-6} - roll over on a certain day; 0 - Monday
        #
        # Case of the 'when' specifier is not important; lower or upper case
        # will work.

        # If 'MIDNIGHT' - use 'D' interval params
        if self.when == 'MIDNIGHT':
            interval_key = 'D'
        else:
            interval_key = self.when[0]

        try:
            params = self._intervals[interval_key]
            self.interval = params['interval'] * interval
            self.suffix = params['suffix']
            self.extMatch = re.compile(params['match'])
        except KeyError:
            raise ValueError("Invalid rollover interval specified: %s" %
                             self.when)

        # If 'W_' - set day of week
        if self.when.startswith('W'):
            if len(self.when) != 2:
                raise ValueError(
                    "You must specify a day for weekly rollover from 0 to 6 "
                    "(0 is Monday): %s" % self.when)
            if self.when[1] < '0' or self.when[1] > '6':
                raise ValueError("Invalid day specified for weekly "
                                 "rollover: %s" % self.when)
            self.dayOfWeek = int(self.when[1])

        if os.path.exists(filename):
            t = os.stat(filename)[stat.ST_MTIME]
        else:
            t = int(time.time())
        self.rolloverAt = self.computeRollover(t)

    def computeRollover(self, currentTime):
        """
        Work out the rollover time based on the specified time.
        """
        result = currentTime + self.interval
        # If we are rolling over at midnight or weekly, then the interval is
        # already known.  What we need to figure out is WHEN the next interval
        # is.  In other words, if you are rolling over at midnight, then your
        # base interval is 1 day, but you want to start that one day clock at
        # midnight, not now.  So, we have to fudge the rolloverAt value in
        # order to trigger the first rollover at the right time.  After that,
        # the regular interval will take care of the rest.  Note that this code
        # doesn't care about leap seconds. :)
        if self.when == 'MIDNIGHT' or self.when.startswith('W'):
            # This could be done with less code, but I wanted it to be clear
            if self.utc:
                t = time.gmtime(currentTime)
            else:
                t = time.localtime(currentTime)
            currenthour = t[3]
            currentminute = t[4]
            currentsecond = t[5]
            # r is the number of seconds left between now and midnight
            r = _MIDNIGHT - to_seconds(hours=currenthour,
                                       minutes=currentminute,
                                       seconds=currentsecond)
            result = currentTime + r
            # If we are rolling over on a certain day, add in the number of
            # days until the next rollover, but offset by 1 since we just
            # calculated the time until the next day starts.  There are three
            # cases:
            # Case 1) The day to rollover is today; in this case, do nothing
            # Case 2) The day to rollover is further in the interval (i.e.,
            #         today is day 2 (Wednesday) and rollover is on day 6
            #         (Sunday).  Days to next rollover is simply 6 - 2 - 1, or
            #         3.
            # Case 3) The day to rollover is behind us in the interval (i.e.,
            #         today is day 5 (Saturday) and rollover is on day 3
            #         (Thursday).  Days to rollover is 6 - 5 + 3, or 4.  In
            #         this case, it's the number of days left in the current
            #         week (1) plus the number of days in the next week until
            #         the rollover day (3).
            # The calculations described in 2) and 3) above need to have a day
            # added.  This is because the above time calculation takes us to
            # midnight on this day, i.e. the start of the next day.
            if self.when.startswith('W'):
                day = t[6]  # 0 is Monday
                if day != self.dayOfWeek:
                    if day < self.dayOfWeek:
                        daystowait = self.dayOfWeek - day
                    else:
                        daystowait = 6 - day + self.dayOfWeek + 1
                    newrolloverat = result + to_seconds(days=daystowait)
                    if not self.utc:
                        dstnow = t[-1]
                        dstatrollover = time.localtime(newrolloverat)[-1]
                        if dstnow != dstatrollover:
                            if not dstnow:
                                # DST kicks in before next rollover, so we need
                                # to deduct an hour
                                addend = -3600
                            else:
                                # DST bows out before next rollover, so we need
                                # to add an hour
                                addend = 3600
                            newrolloverat += addend
                    result = newrolloverat
        return result

    def shouldRollover(self, record):
        """
        Determine if rollover should occur.

        record is not used, as we are just comparing times, but it is needed so
        the method signatures are the same
        """
        t = int(time.time())
        if t >= self.rolloverAt:
            return True
        return False

    def getFilesToDelete(self):
        """
        Determine the files to delete when rolling over.

        More specific than the earlier method, which just used glob.glob().
        """
        dirName, baseName = os.path.split(self.baseFilename)
        fileNames = os.listdir(dirName)
        result = []
        prefix = baseName + "."
        plen = len(prefix)
        for fileName in fileNames:
            if fileName[:plen] == prefix:
                suffix = fileName[plen:]
                if self.extMatch.match(suffix):
                    result.append(os.path.join(dirName, fileName))
        result.sort()
        if len(result) < self.backupCount:
            result = []
        else:
            result = result[:len(result) - self.backupCount]
        return result

    def doRollover(self, record):
        """
        This is a slightly modified copy of CerebrumRotatingHandler and
        logging.handlers.TimedRotatingFileHandler

        In essence we have to rotate based on time, but it also has to be
        thread safe.
        """
        try:
            self.acquire()

            # Check one more time, if we *really* should roll over. Perhaps a
            # differnt thread has already done that.
            if not self.shouldRollover(record):
                return

            if self.stream and self.stream.closed:
                self.stream.close()

            try:
                # get the time that this sequence started at and make it a
                # TimeTuple
                currenttime = int(time.time())
                dstnow = time.localtime(currenttime)[-1]
                t = self.rolloverAt - self.interval
                if self.utc:
                    timetuple = time.gmtime(t)
                else:
                    timetuple = time.localtime(t)
                    dstthen = timetuple[-1]
                    if dstnow != dstthen:
                        if dstnow:
                            addend = 3600
                        else:
                            addend = -3600
                        timetuple = time.localtime(t + addend)
                dfn = self.baseFilename + "." + time.strftime(self.suffix,
                                                              timetuple)
                if os.path.exists(dfn):
                    os.remove(dfn)
                if os.path.exists(self.baseFilename):
                    os.rename(self.baseFilename, dfn)
                if self.backupCount > 0:
                    for s in self.getFilesToDelete():
                        os.remove(s)
                newrolloverat = self.computeRollover(currenttime)
                while newrolloverat <= currenttime:
                    newrolloverat = newrolloverat + self.interval
                # If DST changes and midnight or weekly rollover, adjust for
                # this.
                if (self.when == 'MIDNIGHT' or
                        self.when.startswith('W')) and not self.utc:
                    dstatrollover = time.localtime(newrolloverat)[-1]
                    if dstnow != dstatrollover:
                        if not dstnow:
                            # DST kicks in before next rollover, so we need to
                            # deduct an hour
                            addend = -3600
                        else:
                            # DST bows out before next rollover, so we need to
                            # add an hour
                            addend = 3600
                        newrolloverat += addend
                self.rolloverAt = newrolloverat

                # delayed opening. The superclass will take care of everything
                self.stream = None
            except:
                # Something went wrong before we managed to complete
                # rotations. Let's re-open the stream and hope for the best. In
                # case of failure, it is preferrable to write to the same file,
                # rather than barf with some sort of error message. If the
                # error is transient, all will be well and the file will be
                # rotated next time around. If not, at least we'd be able to
                # scribble some messages to the file.
                if self.stream and self.stream.closed:
                    self._open()
                    # Make sure the caller knows that something broke down.
                    raise
        finally:
            self.release()


def configure(config):
    """ patch handlers with values from config.

    :param LoggingEnvironment config:
        The configuration to use.
    """
    FilenameTemplateMixin.configure(config)
