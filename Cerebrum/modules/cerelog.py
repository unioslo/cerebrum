# -*- coding: utf-8 -*-

# Copyright 2004-2015 University of Oslo, Norway
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
"""This module provides a logging framework for Cerebrum.

The idea is based on python's logging module and a few nits of our own.

The logging framework behaviour is controlled by a suitable configuration
file, described here [1]. Although we use the very same format/options as the
standard logging framwork, we still need a special parser for the config
file, for the behaviour sought is quite different from that of
logging.fileConfig. Most noteably:

* Only one logger is initialized. If no name is specified, the root logger
  is used. This is a design choice.

* Only the logger explicitely requested is initialized. We do *not* open
  *all* handers, only those attached to the requested logger. This is
  different from the logging behaviour.

* The root logger (if it is initialized at all) is an instance of
  CerebrumLogger, not logging.RootLogger.

* The parent-child hierarchy is constructed by this module. We do not rely
  on logging.getLogger's behaviour. Nevertheless, the 'dotted name
  hierarchy' is respected, and the logger names themselves serve as a basis
  for the hierarchy.

Furthermore, this module provides additional extensions to the standard
logging framework:

* a CerebrumLogger class, with several additional message levels (five new
  debug levels)

* Additional handlers and formatters.

* Indentation support. Although this option is contrary to the abstraction
  spirit of the logging framework, it has nevertheless been found useful.

The behaviour of this module can be partially controlled from the command
line, through the following arguments:

--logger-name=<name>    -- specify a particular logger to initialize
--logger-level=<level>  -- specify a particular verbosity setting to use

References:
  [1] <URL: http://www.python.org/peps/pep-0282.html>
  [2] <URL: http://www.red-dove.com/python_logging.html>

"""
import cerebrum_path
import cereconf

import ConfigParser
import codecs
import locale
import logging
import os
import os.path
import re
import sys
import threading
import time
from logging import handlers

from inspect import currentframe

# IVR 2007-02-08: This is to help logging.findCaller(). The problem is that
# logging.findCaller looks for the first function up the stack that does not
# belong to logging. This is of course some wrapper from cerelog. So, we need
# to modify findCaller to ignore both logging and cerelog.
if __file__[-4:].lower() in ['.pyc', '.pyo']:
    _srcfile = __file__[:-4] + '.py'
else:
    _srcfile = __file__
_srcfile = os.path.normcase(_srcfile)


# Additional debug levels. They will be added to the logging framework
DEBUG1 = logging.DEBUG - 1
DEBUG2 = DEBUG1-1
DEBUG3 = DEBUG2-1
DEBUG4 = DEBUG3-1
DEBUG5 = DEBUG4-1


def debug(*rest):
    """A shorthand for dumping messages to stderr.

    If the logging framework fails, we may need some way of reporting the
    failures to the client environment. This is the simplest way (Cerebrum's
    dispatcher job_runner captures standard output/error)

    """
    for item in rest:
        sys.stderr.write(str(item))

    sys.stderr.write('\n')


def show_hierarchy(logger):
    """Travel up the logger tree and print information about loggers.

    For debugging purposes ONLY.

    """
    l = logger
    while l:
        debug("Logger %s:" % l.name)
        debug("Level: %s, %s" % (l.level, l.getEffectiveLevel()))
        debug("Handlers: ", ["%s (%s)" % (x, x.level) for x in l.handlers])
        debug("Propagate: ", l.propagate)
        l = l.parent


def init_cerebrum_extensions():
    """Load all cerebrum extensions to logging.

    This function extends the standard logging module with a few attributes
    specific for Cerebrum.

    """
    # Certain things are evaluated in logging package's context
    # setattr(logging, "CerebrumRotatingHandler", CerebrumRotatingHandler)
    # setattr(logging, "CerebrumLogger", CerebrumLogger)

    # A couple of constants for our debugging levels
    for level_name in ("DEBUG1", "DEBUG2", "DEBUG3", "DEBUG4", "DEBUG5"):
        level = globals()[level_name]
        logging.addLevelName(level, level_name)

    logging.setLoggerClass(CerebrumLogger)


def fetch_logger_arguments(options, flags):
    """Extract command line arguments for the cerelog module.

    Unfortunately getopt and other argument parsers reacts adversely to unknown
    arguments. Thus we'd have to process command-line arguments ourselves.

    The fetching process is DESTRUCTIVE. This function can be run only once,
    unless sys.argv is saved before the call and restored after it.

    :type options: sequence (of basestrings)
    :param options:
        A list of options to look for in sys.argv. Each option will also
        extract the option value (the next argument).

    :type flags: sequence (of basestrings)
    :param flags:
        A list of flags/switches to look for in sys.argv. If the flag is
        present, we'll return True as it's value.

    :rtype: dict (of basestring to basestring)
    :return:
        A dictionary mapping entries from L{options} and L{flags} to the values
        belonging to those arguments.

    IVR 2007-02-08 TBD: Ideally, we need to whip out our own argument parser
    on top of getopt/optparse that is cerelog-aware and that can ignore
    arguments it does not understand.

    """
    # key to command line parameter value
    result = dict()
    # the copy of the original sys.argv
    args = sys.argv[:]
    # positions that we'll have to remove from the original sys.argv
    filter_list = list()

    i = 0
    while i < len(args):
        for key in options:
            if not args[i].startswith(key):
                continue

            # We have an option. Two cases:
            # Case 1: key=value
            if args[i].find("=") != -1:
                result[key] = args[i].split("=")[1]
                filter_list.append(i)
            # Case 2: key value. In this case we peek into the next argument
            elif i < len(args)-1:
                result[key] = args[i+1]
                filter_list.append(i)
                filter_list.append(i+1)
                # since we peeked one argument ahead, skip it
                i += 1

        for key in flags:
            if args[i] == key:
                result[key] = True
                filter_list.append(i)

        # next argument
        i += 1

    # We must make sure that every references to sys.argv already made remains
    # intact.
    #
    # IVR 2007-01-30 FIXME: This is not thread-safe
    sys.argv[:] = list()
    for i in range(0, len(args)):
        if i not in filter_list:
            sys.argv.append(args[i])

    return result


def process_arguments():
    """This function looks through command line arguments for parameters
    controlling logging framework behaviour.

    Specifically, these command line arguments carry the following meaning:

    --logger-name=<name> Only the logger specified by <name> shall be
                         opened.  The rest (from the config file) is simply
                         discarded. If none is specified, the 'root' logger
                         is used.

    --logger-level=<num> Set all loggers to log at level <num> and above. If
                         no value is specified, the default for the logging
                         module is used (FIXME: This default is different
                         between python 2.2 and 2.3)

    --logger-no-warn     If present, warnings will NOT be captured by the
                         logger. The default behaviour is to capture warnings.

    --logger-no-exc      If present, exceptions will NOT be captured by the
                         logger. The default behaviour is to capture warnings.

    :rtype: typle (of basestrings)
    :return:
        A tuple containing name of the logger to use and logger's level. Either
        one can be 'missing', in which case None is returned.

    """
    result = fetch_logger_arguments(["--logger-name", "--logger-level", ],
                                    ["--logger-no-warn", "--logger-no-exc", ])

    # If the option is not given, set the logger to capture warnings.
    if not result.get("--logger-no-warn", False):
        captureWarnings(True)

    # If the option is not given, set the logger to capture exceptions
    if not result.get("--logger-no-exc", False):
        set_exception_hook(log_exception_handler)

    return (result.get("--logger-name", None),
            result.get("--logger-level", None))


def process_config(fname, logger_name, logger_level):
    """Process the logging configuration, while respecting the command-line
    arguments.

    We try to mimic logging.fileConfig's behaviour as close as possible.

    :type fname: basestring
    :param fname:
        File name for the configuration file. This file must exist and must be
        readable.

    :type logger_name: basestring
    :param logger_name:
        Logger name to initialize from the config file (there may be many
        loggers specified in that file. We initialize only the one specified).
        If no such logger could be found in the config file, an exception is
        raised.

    :type logger_level: int or basestring
    :param logger_level:
        See L{get_level}.

    :rtype: a logging.getLoggerClass() instance
    :return:
        A logger object (ready for logging). All the dependencies of that
        logger (and only they) are initialized (dependencies in this case means
        formatters, handlers, parents (and the transitive closure thereof)).

    """
    parser = ConfigParser.ConfigParser()
    if hasattr(parser, "readfp") and hasattr(fname, "read"):
        parser.readfp(fname)
    else:
        parser.read(fname)

    # From here on we initialize a single logger (and all its ancestors),
    # identified by L{logger_name}.
    logger = initialize_logger(logger_name, logger_level, parser)

    # Now we *must* create all parents on the way up toward the root
    # logger. getLogger()'s behaviour is to create a PlaceHolder object, which
    # is pretty useless for logging purposes.
    if not logger.propagate:
        logger.parent = None
    else:
        name = logger.name
        current = logger
        pos = name.rfind(".")
        while (pos > 0) and current.propagate:
            parent_name = name[:pos]
            # logger_name is a command-line argument. It should not affect
            # the parents
            parent = initialize_logger(parent_name, None, parser)

            # Link child to its parent
            current.parent = parent
            # Move one level higher up the hierarchy
            current = parent
            pos = name.rfind(".", 0, pos-1)

        # Make sure that the topmost parent of the logger hierarchy points
        # to a root logger initialized by us (logging modules forces a
        # default (uninitialized logger)
        if current.name != "root":
            if current.propagate:
                # Do *not* touch root logger's level
                current.parent = initialize_logger("root", None, parser)
                current.parent.parent = None
            else:
                current.parent = None

    return logger


def get_level(level):
    """Return a number corresponding to the given severity level name/number.

    :param level: int or basestring
    :param level:
        Level specification to check. It could be either an int or a string. If
        it is a string it may be either all digits (for the numerical
        representation of the level) or all letters (for the actual name of the
        level).

    """
    try:
        if (isinstance(level, int) or isinstance(level, basestring)
                and level.isdigit()):
            # check that is has been defined
            level = int(level)
            logging._levelNames[level]
            result = level
        else:
            result = logging._levelNames[level]
            assert isinstance(result, (int, long)), "Bad log level: %s" % level
        return int(result)
    except KeyError:
        print "Undefined logging level: %s" % str(level)
        raise


def initialize_logger(name, level, config):
    """This function creates and initializes a new logger L{name} with config
    information specified in L{config}.

    Once the logger object is created, it's registered with the logging
    framework (this is needed to keep track of parent-child relationships
    between loggers).

    :type name: basestring
    :param name:
        Logger name to use. This also indicated where to look for settings in
        the configuration file.

    :type level: int or basestring
    :param level:
        See L{get_level}.

    :type config: ConfigParser.ConfigParser instance
    :param config:
        A ConfigParser instance associated with the configuration file. The
        content of the config file has already been read and is available via
        the ConfigParser API.

    :rtype: logging.getLoggerClass() instance
    :return:
        A logger object (ready for usage).

    """
    section_name = "logger_" + name
    if not config.has_section(section_name):
        raise ConfigParser.NoSectionError("no logger section " + section_name)

    qualname = config.get(section_name, "qualname")
    options = config.options(section_name)
    if "propagate" in options:
        propagate = config.getint(section_name, "propagate")
    else:
        propagate = 1

    # logging.getLogger does a number of fancy things. If a name does not
    # exist, a suitable logger instance is created anew.
    logger = logging.getLogger(qualname)

    # if there is a command line level override, use it
    if level is not None:
        logger.setLevel(get_level(level))
    # ... otherwise use the level specified in the config file, it it exists
    elif "level" in options:
        logger_level = config.get(section_name, "level")
        logger.setLevel(get_level(logger_level))

    # FIXME: is this really necessary? (stolen from logging)
    for handler in logger.handlers:
        logger.removeHandler(handler)

    logger.propagate = propagate
    logger.disabled = 0
    handler_names = config.get(section_name, "handlers")
    if handler_names:
        for handler_name in handler_names.split(","):
            # allow people to be sloppy with whitespace
            handler_name = handler_name.strip()
            logger.addHandler(initialize_handler(handler_name, config))
    else:
        debug("No handlers specified for %s. Does this make sense?" %
              logger.name)

    # Force propagate to 0 for root loggers
    if logger.name == "root":
        logger.propagate = 0

    return logger


# logging.config does it like this
def _resolve(name):
    """Resolve a dotted name to a global object."""
    name = name.split('.')
    used = name.pop(0)
    found = __import__(used)
    for n in name:
        used = used + '.' + n
        try:
            found = getattr(found, n)
        except AttributeError:
            __import__(used)
            found = getattr(found, n)
    return found


_handlers = dict()
""" Cache of initialized log handlers. """


def initialize_handler(name, config):
    """This function creates and initializes a handler L{name} from an
    ini-file represented by L{config}.

    If a handler L{name} already exists, it is returned without any
    re-initialization. (Imagine for a second that several FileHandlers were
    opened simultaneously for the same file)

    IVR 2008-04-09 NB! The code is NOT thread-safe.

    :type name: basestring
    :param name:
        Handler's name (also used to look up the proper config in the config
        file).

    :type config: See L{initialize_logger}
    :param config: See L{initialize_logger}

    :rtype: an instance of logging.Handler (or its subclasses)
    :return:
        A handler object ready to use.

    """
    if name in _handlers:
        return _handlers[name]

    section_name = "handler_" + name
    klass = config.get(section_name, "class")
    options = config.options(section_name)
    if "formatter" in options:
        formatter = config.get(section_name, "formatter")
    else:
        formatter = ""

    # Look up KLASS in the logging module + this file. The handler could be in
    # either one. If that fails, try imported modules and path
    namespace = logging.__dict__.copy()
    namespace.update(globals())
    if klass in namespace.keys():
        klass = namespace[klass]
    else:
        try:
            klass = eval(klass, globals())
        except (AttributeError, NameError):
            klass = _resolve(klass)

    # We want *all* of our handlers to understand indentation directives. So,
    # we monkey patch the indentation capabilities.
    klass = type("_dynamic_" + name, (klass, IndentingHandler), {})

    arguments = config.get(section_name, "args")
    arguments = eval(arguments, namespace)

    handler = klass(*arguments)

    # If there is a level specification in the ini-file, use it.
    if "level" in options:
        level = config.get(section_name, "level")
        handler.setLevel(get_level(level))

    # formatters are initialized as needed.
    if formatter:
        handler.setFormatter(initialize_formatter(formatter, config))

    _handlers[name] = handler
    return handler


_formatters = dict()
""" Cache of initialized log formatters. """


def initialize_formatter(formatter_name, config):
    """Initializes if necessary and returns a specific formatter.

    :type formatter_name: basestring
    :param formatter_name:
        Formatter's name (also used to look up the proper config in the config
        file).

    :rtype: an instance of logging.Formatter (or its subclasses)
    :return:
        A formatter object ready to use.

    """
    # we have seen this one before...
    if formatter_name in _formatters:
        return _formatters[formatter_name]

    section_name = "formatter_" + formatter_name
    if not config.has_section(section_name):
        raise ConfigParser.NoSectionError(
            "no formatter section %s" % section_name)

    options = config.options(section_name)

    format = datefmt = None
    indent = 0
    if "format" in options:
        format = config.get(section_name, "format", 1)
    if "datefmt" in options:
        datefmt = config.get(section_name, "datefmt", 1)
    if "indent" in options:
        indent = config.get(section_name, "indent", 1)

    # All formatters understand the "indent" command. By default, no
    # indentation takes place.
    _formatters[formatter_name] = IndentingFormatter(format, datefmt, indent)
    return _formatters[formatter_name]


_logger_instance = None
""" Initialized logger instance. """


def get_logger(config_file, logger_name=None):
    """Initialize (if necessary) and return the logger.

    NB! get_logger will actually initialize anything only once. All subsequent
    calls from the same process (thread?) will return a reference to the same
    logger *regardless* of the L{logger_name} specified (this behavior is
    intentional).

    This is the only external interface to this entire module. Client code is
    expected to do something like this::

        >>> from Cerebrum.Utils import Factory
        >>> l = Factory.get_logger('some name')
        >>> l.debug('furrfu')

    The Factory framework is optional, and the logger can be fetched directly.

    :type config_file: basestring
    :param config_file:
        Name of the config file containing the logger's configuration info.

    :type logger_name: basestring or None
    :param logger_name:
        Name of the logger to create. If None is specified, the name is taken
        from the command line. If none was given, 'root' is assumed.

    :rtype: a logging.getLoggerClass() instance.
    :return:
        An initialized logger object ready for usage.

    """
    global _logger_instance

    if _logger_instance is None:
        _logger_instance = cerelog_init(config_file, logger_name)

    return _logger_instance


def cerelog_init(config_file, name):
    """Run-once method for initializing everything in cerelog.

    :type config_file: basestring
    :param config_file:
        Name of the config file containing the logger's configuration info.

    :type name: basestring or None
    :param name:
        Name of the logger to create. If None is specified, the name is taken
        from the command line. If none was given, 'root' is assumed.

    :rtype: See L{process_config}
    :return: See L{process_config}

    """
    # Load our constants
    init_cerebrum_extensions()

    # Load command-line controls
    logger_name, level = process_arguments()

    # If no command-line name was specified, use the one supplied
    if logger_name is None:
        logger_name = name

    # Fall back to root as last resort
    if logger_name is None:
        logger_name = "root"

    # Parse the config file. Do *NOT* ever call this more than once.
    return process_config(config_file, logger_name, level)


class CerelogStreamWriter(codecs.StreamWriter):

    """Convert all input to specified charsets.

    The purpose of this class is to allow:

    stream.write('foo')
    stream.write('foo æøå')
    stream.write(unicode('foo'))
    stream.write(unicode('foo æøå', 'latin1'))

    ... so that the client code does not have to care about the
    encodings, regardless of the encodings specified in logging.ini.

    The unicode objects can be output quite easily. The problem arises with
    non-ascii str objects. We have no way of *knowing* their exact encoding,
    and some guesswork is involved in outputting the strings.

    """

    def __init__(self, stream, errors="strict"):
        codecs.StreamWriter.__init__(self, stream, errors)

        # What's the expected encoding for strings?
        self.incoming_encodings = list()
        for x in (locale.getpreferredencoding(),
                  "utf-8",
                  "iso-8859-1",
                  "windows-1252"):
            if x.lower() not in self.incoming_encodings:
                self.incoming_encodings.append(x.lower())

    def write(self, obj):
        """Force conversion to self.encoding."""

        # We force strings to unicode, so we won't have to deal with encoding
        # crap later.
        if self.incoming_encodings and isinstance(obj, str):
            # The problem at this point is: what is the encoding in which obj
            # is represented? There is no way we can know this for sure, since
            # we have no idea what the environment of python is...
            for encoding in self.incoming_encodings:
                try:
                    obj = obj.decode(encoding)
                    break
                except UnicodeError:
                    pass

            # IVR 2008-05-16 TBD: What do we do here, if obj is NOT unicode?

        data, consumed = self.encode(obj, self.errors)
        self.stream.write(data)

    def writelines(self, lines):
        """"Write concatenated list of strings."""
        self.write(''.join(lines))


class CerebrumLogger(logging.Logger, object):

    """This is the logger class used by the Cerebrum framework."""

    def __init__(self, name, level=logging.NOTSET):
        logging.Logger.__init__(self, name, level)

    def findCaller(self):
        """Find the stack frame of the caller.

        This function overloads the default implementation. This is so that we
        can ignore this module when looking through the call stack.

        """
        f = currentframe().f_back
        rv = "(unknown file)", 0, "(unknown function)"
        while hasattr(f, "f_code"):
            co = f.f_code
            filename = os.path.normcase(co.co_filename)
            if (filename == _srcfile or
                    filename.find("logging/__init__.py") >= 0):
                f = f.f_back
                continue
            rv = (filename, f.f_lineno, co.co_name)
            break
        return rv

    def __cerebrum_debug(self, level, msg, *args, **kwargs):
        if self.manager.disable >= level:
            return
        if self.isEnabledFor(level):
            apply(self._log, (level, msg, args), kwargs)

    def callHandlers(self, record):
        super(CerebrumLogger, self).callHandlers(record)

    def debug1(self, msg, *args, **kwargs):
        self.__cerebrum_debug(DEBUG1, msg, *args, **kwargs)

    def debug2(self, msg, *args, **kwargs):
        self.__cerebrum_debug(DEBUG2, msg, *args, **kwargs)

    def debug3(self, msg, *args, **kwargs):
        self.__cerebrum_debug(DEBUG3, msg, *args, **kwargs)

    def debug4(self, msg, *args, **kwargs):
        self.__cerebrum_debug(DEBUG4, msg, *args, **kwargs)

    def debug5(self, msg, *args, **kwargs):
        self.__cerebrum_debug(DEBUG5, msg, *args, **kwargs)

    def set_indent(self, indent=0):
        for handle in self.handlers:
            if hasattr(handle, "set_indent"):
                handle.set_indent(indent)


class IndentingFormatter(logging.Formatter, object):

    """Mixin to extend the interface of our formatters.

    This class will be 'merged' into all formatters instantiated in
    cerelog. It cannot be used as a stand-alone class.

    """

    def __init__(self, fmt=None, datefmt=None, indent=0):
        super(IndentingFormatter, self).__init__(fmt, datefmt)
        self._indent = indent

    def formatIndent(self, record):
        #
        # IVR 2007-02-13 FIXME: This should be parametrized (logging.ini)
        return " " * self._indent

    def set_indent(self, indent=0):
        assert isinstance(indent, (int, long))
        self._indent = indent

    # Make sure this method is the first format() seen in MRO. Otherwise a
    # default would be used (which ignores the indent directive)
    def format(self, record):
        # IVR 2007-02-08 FIXME: This is a bit of hack, actually. formatTime is
        # similar, though.
        if self._fmt.find("%(indent)") >= 0:
            record.indent = self.formatIndent(record)

        return super(IndentingFormatter, self).format(record)


class IndentingHandler(logging.Handler, object):
    """Mixin to extend the interface of out handlers.

    This class will be 'merged' into all handlers instantiated in cerelog. It
    cannot be used as a stand-alone class.

    """

    def set_indent(self, indent=0):
        if self.formatter:
            self.formatter.set_indent(indent)


class DelayedFileHandler(logging.FileHandler, object):

    """A handler classes which delays opening files until necessary."""

    def __init__(self, filename, mode='a', encoding=None):
        # We just register the stuff that is essential and wait until
        # something exciting happens. Yes, the idea is to call
        # Handler.__init__, not FileHandler.__init__, since FileHandler
        # attemps to open the file immediately.
        logging.Handler.__init__(self)

        self.baseFilename = os.path.abspath(filename)
        self.mode = mode
        self.encoding = encoding or "latin1"
        self.formatter = None
        self.stream = None

        self._lock = threading.RLock()

    def acquire_lock(self):
        self._lock.acquire()

    def release_lock(self):
        self._lock.release()

    def flush(self):
        if self.stream:
            self.stream.flush()

    def close(self):
        if self.stream:
            super(DelayedFileHandler, self).close()

    def emit(self, record):
        if self.stream is None:
            self.open()
        super(DelayedFileHandler, self).emit(record)

    def open(self):
        mode = self.mode
        if 'b' not in mode:
            mode = mode + 'b'

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
        stream = file(self.baseFilename, mode)
        encoder, decoder, reader, writer = codecs.lookup(self.encoding)

        srw = codecs.StreamReaderWriter(stream, reader, CerelogStreamWriter)
        srw.encoding = self.encoding
        srw.writer.encoding = srw.encoding
        srw.writer.encode = encoder

        self.stream = srw
        return self.stream


class OneRunHandler(DelayedFileHandler):

    """A file handler that logs one job run into exactly one file.

    Basically, this is just like a FileHandler, except that the naming scheme
    for its ctor is different. Each log file gets a timestamp in its name for
    uniqueness.

    """

    def __init__(self, dirname, mode='a', encoding=None):
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")
        filename = os.path.join(os.path.abspath(dirname), "log-" + timestamp)
        super(OneRunHandler, self).__init__(filename, mode, encoding)


class CerebrumRotatingHandler(DelayedFileHandler, object):

    """Cerebrum's own rotating handler.

    This handler rotates the logs much like handlers.RotatingFileHandler,
    except that the file opening is delayed.

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

    def __init__(self, logdir, mode="a", maxBytes=0, backupCount=0,
                 encoding=None, directory=None, basename=None):
        """Open a file somewhere[*] in L{logdir} and use it as the stream for
        logging.

        [*] The file naming scheme is a bit different from standard logging
        practice. L{logdir} indicates the base directory where *all* Cerebrum
        logs live. Each application gets its own directory, based on the given
        parameter. If L{directory} is None, its name is calculated dynamically
        from sys.argv[0]. Within such a directory, this handler would create a
        log file named as given by L{basename} or 'log' if None
        specified. This log file's rotation is controlled by
        L{maxBytes}/L{backupCount}.

        """

        self.logdir = logdir
        self.directory = directory or os.path.basename(sys.argv[0])
        self.basename = basename or "log"

        dirpath = os.path.join(self.logdir, self.directory)
        if not os.path.exists(dirpath):
            try:
                os.makedirs(dirpath, 0770)
            except OSError, e:
                if not os.path.exists(dirpath):
                    # the error is not 'file exists', which we ignore
                    raise e

        self.filename = os.path.join(dirpath, self.basename)
        # 'w' would truncate, and it makes no sense for this handler.
        if maxBytes > 0:
            mode = "a+"
        super(CerebrumRotatingHandler, self).__init__(self.filename,
                                                      mode,
                                                      encoding)
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
            self.acquire_lock()

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
                if (os.path.exists(self.baseFilename) and
                        self.backupCount > 0):
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
                    self.open()
                    # Make sure the caller knows that something broke down.
                    raise
        finally:
            self.release_lock()


# IVR 2008-04-09: FIXME: This inheritance tree is completely
# wrong. Substitution should be able to happen without log rotation. This
# class probably ought to be a simple mixin.
class CerebrumSubstituteHandler(CerebrumRotatingHandler):

    """This handler behaves just like CerebrumRotatingHandler, except it
    performs certain preprosessing of each message.

    Specifically, a substitution is performed on each message before the it is
    output. Substution is regexp-based (as defined by the module re). If
    either one is missing (i.e. is an empty string), no substitution will be
    performed (and the logger would behave exactly like its immediate parent).

    Additionally, since this kind of filtering is likely to be used in
    conjuction with confidential data (such as passwords), an additional
    permission parameter controls who has access to logfiles (regardless of
    the client process' umask).

    """

    def __init__(self, logdir, maxBytes, backupCount,
                 permissions, patterns, encoding=None,
                 directory=None, basename=None):
        """
        :param logdir: See L{CerebrumRotatingHandler}
        :param maxBytes: See L{CerebrumRotatingHandler}
        :param backupCount: See L{CerebrumRotatingHandler}
        :param encoding: See L{CerebrumRotatingHandler}
        :param directory: See L{CerebrumRotatingHandler}
        :param basename: See L{CerebrumRotatingHandler}

        :type permissions: int
        :param permissions:
            Numerical permission mode passed to os.chmod()

        :type patterns: sequence of pairs (of basestrings)
        :param patterns:
            A sequence containing pairs (x, y) where x is the regular
            expression, and y is the pattern that used to substitute whatever x
            matches. Whatever re permits is allowed inside x and y.

        """
        super(CerebrumSubstituteHandler, self).__init__(logdir, "a",
                                                        maxBytes,
                                                        backupCount, encoding,
                                                        directory, basename)

        self.patterns = [(re.compile(x), y) for x, y in patterns]
        self.permissions = permissions

    def open(self):
        super(CerebrumSubstituteHandler, self).open()
        # Force our permissions
        os.chmod(self.filename, self.permissions)

    def format(self, record):
        msg = super(CerebrumSubstituteHandler, self).format(record)
        # Note that the regexes are applied in order. Multiple entries may
        # match. Make sure your pattenrs are not overlapping!
        for rex, replacement in self.patterns:
            msg = rex.sub(replacement, msg)
        return msg


# warnings support
import warnings

_warnings_showwarning = None
""" The default warnings.showwarnings function, if overridden. """


def _showwarning(message, category, filename, lineno, file=None, line=None):
    """ cerelog-adapted warnings.showwarning function.

    If cerelog.captureWarnings is enabled, this function will receive warnings.
    The default behaviour is to log warnings with the initialized logger, with
    level WARNING.

    If no logger is initialized, or warnings.showwarnings is called with a
    `file' argument that is not `None', the default warnings.showwarning
    function is called.

    See L{warnings.showwarning} for documentation of the arguments.

    """
    logger = _logger_instance

    # PY25 compability - only include line if it's actually given.
    kw = dict()
    if line is not None:
        kw['line'] = line

    if file is not None and logger is not None:
        if _warnings_showwarning is not None:
            _warnings_showwarning(message, category, filename, lineno,
                                  file, **kw)
    else:
        s = warnings.formatwarning(message, category, filename, lineno, **kw)
        logger.warning("%s", s)


def captureWarnings(capture):
    """ Capture warnings using cerelog.

    :param boolean capture:
        If capture of warnings by logging should be enabled.

    """
    global _warnings_showwarning
    if capture:
        if _warnings_showwarning is None:
            _warnings_showwarning = warnings.showwarning
            warnings.showwarning = _showwarning
    else:
        if _warnings_showwarning is not None:
            warnings.showwarning = _warnings_showwarning
            _warnings_showwarning = None


_cached_filters = None
""" The previous set warnings filter. """


# TODO: Does this belong here?
def setup_warnings(filters=[]):
    """ Re-initialize warning filters without defaults.

    This re-does the warnings initialization without using the python defaults.
    In stead, we initialize the warnings filters with L{sys.warnoptions}, and
    the L{filters} argument. The latter will typically come from a
    configuration file.

    :param list filters:
        A list of filter strings, (as accepted by `python -W' or
        `PYTHONWARNINGS', see L{warnings}).
        The filters are added in reverse priority (the last one takes priority
        of the first) - just like the `python -W' options or `PYTHONWARNINGS'.

    :raise ValueError: If a filter string is invalid.

    """
    global _cached_filters
    filters = list(filters)  # Make a copy
    if _cached_filters is not None and _cached_filters == filters:
        return  # No change
    warnings.resetwarnings()

    # TODO: The default warnings module alters the warnings filter based on
    # these flags. We should look into:
    #   - sys.flags.byteswarning (controls default BytesWarning filter)
    #   - sys.flags.py3k_warning (disables default ignore-filter)
    #   - sys.flags.division_warning (disables default ignore-filter)

    for warnfilter in filters + sys.warnoptions:
        try:
            warnings._setoption(warnfilter)
        except warnings._OptionError, e:
            raise ValueError("Invalid warning filter: '%s'" % e)
    _cached_filters = filters


# Exception hook to log uncaught exceptions

def log_exception_handler(*args):
    """ excepthook function that logs the exception.

    This function is intended for use as L{sys.excepthook}, and will call
    L{sys.__excepthook__} before returning.

    """
    if _logger_instance is not None:
        _logger_instance.critical("Uncaught exception", exc_info=args)
    sys.__excepthook__(*args)


# TODO: Does this belong here?
def set_exception_hook(hook=None):
    """ Set up error handler.

    :type hook: callable or None
    :param hook: A new function to use as sys.excepthook, or None to reset.

    :raise TypeError: If L{hook} is not None or callable

    """
    if hook is None:
        sys.excepthook = sys.__excepthook__
    elif callable(hook):
        sys.excepthook = hook
    else:
        raise TypeError("Bad exception hook %r" % hook)
