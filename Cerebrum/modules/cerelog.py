# -*- coding: iso-8859-1 -*-

# Copyright 2004 University of Oslo, Norway
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

The idea is based on python2.3's logging module and a few nits of our own.

The logging framework behaviour is controlled by a suitable configuration
file, described here [1]. Although we use the very same format/options as the
standard logging framwork, we still need a special parser for the config
file, for the behaviour sought is quite different from that of
logging.fileConfig. Most noteably:

* Only one logger is initialized. If no name is specified, the root logger
  is used.

* Only the logger explicitely requested is initialized. We do *not* open
  *all* handers, only those attached to the requested logger.

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

* a CerebrumRotatingHandler class, which is a specialization of
  logging.RotatingFileHandler capable of arranging the logfiles based on
  sys.argv[0]

The behaviour of this module can be partially controlled from the command
line, through the following arguments:

--logger-name=<name>    -- specify a particular logger to initialize
--logger-level=<level>  -- specify a particular verbosity setting to use

References:
  [1] <URL: http://www.python.org/peps/pep-0282.html>
  [2] <URL: http://www.red-dove.com/python_logging.html>
"""

from logging import handlers
import ConfigParser
import codecs
import getopt
import inspect
import logging
import os
import os.path
import re
import string
import sys
import time
import types

# IVR 2007-02-08: This is to help logging.findCaller(). The problem is that
# logging.findCaller looks for the first function up the stack that does not
# belong to logging. This is of course some wrapper from cerelog. So, we need
# to modify findCaller to ignore both logging and cerelog.
if string.lower(__file__[-4:]) in ['.pyc', '.pyo']:
    _srcfile = __file__[:-4] + '.py'
else:
    _srcfile = __file__
_srcfile = os.path.normcase(_srcfile)





def debug(*rest):
    for item in rest:
        sys.stderr.write(str(item))
    # od

    sys.stderr.write('\n')
# end debug



def show_hierarchy(logger):
    """Travel up the logger tree and print information about loggers.

    For debugging purposes ONLY.
    """

    l = logger
    while l:
        debug("Logger %s:" % l.name)
        debug("Level: %s, %s" % (l.level, l.getEffectiveLevel())) 
        debug("Handlers: ", [ "%s (%s)" % (x, x.level) for x in l.handlers ]) 
        debug("Propagate: ", l.propagate)
        l = l.parent
    # od
# end show_hierarchy
    


def init_cerebrum_extensions():
    """Load all cerebrum extensions to logging.
    
    This function extends the standard logging module with a few attributes
    specific for Cerebrum.
    """

    # Certain things are evaluated in logging package's context
    setattr(logging, "CerebrumRotatingHandler", CerebrumRotatingHandler)
    setattr(logging, "CerebrumLogger", CerebrumLogger)
        
    # A couple of constants for our debugging levels
    for i in range(1,6):
        name = "DEBUG%d" % i
        value = logging.DEBUG - i
        
        setattr(logging, name, value)
        logging.addLevelName(value, name)
    # od

    logging.setLoggerClass(CerebrumLogger)
# end init_cerebrum_extensions



def fetch_logger_arguments(keys):
    """Extract command line arguments for the cerelog module.
    
    Unfortunately getopt reacts adversely to unknown arguments. Thus we'd have
    to process command-line arguments ourselves.

    KEYS is a set of keys that correspond to cerelog-specific command-line
    arguments. Everything else is ignored by this function.

    IVR 2007-02-08 TBD: Ideally, we need to whip out our own argument parser
    on top of getopt/optparse that is cerelog-aware and that can ignore
    arguments it does not understand. 
    """

    result = dict()
    args = sys.argv[:]
    filter_list = list()

    i = 0
    while i < len(args):
        for key in keys:
            if not args[i].startswith(key):
                continue

            # We have an option. Two cases:
            # Case 1: key=value
            if args[i].find("=") != -1:
                result[key] = string.split(args[i], "=")[1]
                filter_list.append(i)
            # Case 2: key value. In this case we peek into the next argument
            elif i < len(args)-1:
                result[key] = args[i+1]
                filter_list.append(i); filter_list.append(i+1)
                # since we peeked one argument ahead, skip it
                i += 1

        # next argument
        i += 1

    # We must make sure that every references to sys.argv already made
    # remains intact.
    #
    # IVR 2007-01-30 FIXME: This is not thread-safe
    sys.argv[:] = list()
    for i in range(0,len(args)):
        if i not in filter_list:
            sys.argv.append(args[i])
        # fi
    # od

    return result
# end fetch_logger_arguments



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
    """

    result = fetch_logger_arguments(["--logger-name",
                                     "--logger-level"])

    return (result.get("--logger-name", None),
            result.get("--logger-level", None))
# end process_arguments
    
    

def process_config(fname, logger_name, logger_level):
    """Process the logging configuration, while respecting the command-line
    arguments.

    We try to mimic logging.fileConfig's behaviour as close as possible.
    """

    parser = ConfigParser.ConfigParser()
    if hasattr(parser, "readfp") and hasattr(fname, "read"):
        parser.readfp(fname)
    else:
        parser.read(fname)

    # From here on we initialize a single logger (and all its ancestors),
    # identified by LOGGER_NAME
    logger = initialize_logger(logger_name, logger_level, parser)

    # Now we *must* create all parents on the way up toward the root
    # logger. getLogger()'s behaviour is to create a PlaceHolder object, which
    # is pretty useless for logging purposes.
    if not logger.propagate:
        logger.parent = None
    else:
        name = logger.name
        current = logger
        pos = string.rfind(name, ".")
        while (pos > 0) and current.propagate:
            parent_name = name[:pos]
            # logger_name is a command-line argument. It should not affect
            # the parents
            parent = initialize_logger(parent_name, None, parser)

            # Link child to its parent
            current.parent = parent
            # Move one level higher up the hierarchy
            current = parent
            pos = string.rfind(name, ".", 0, pos-1)

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
# end process_config



def get_level(level):
    "Return a number corresponding to the given severity level name/number."

    try:
        if (isinstance(level, long) or
            isinstance(level, basestring) and level.isdigit()):
            # check that is has been defined
            level = int(level)
            logging._levelNames[level]
            result = level
        else:
            result = logging._levelNames[level]
            assert (isinstance(result, (int, long)),
                    "Wrong logging level: <%s>" % level)

        return int(result)
    except KeyError, obj:
        print "Undefined logging level: %s" % str(level)
        raise
# end get_level



def initialize_logger(name, level, config):
    """This function creates and initializes a new logger NAME with config
    information specified in CONFIG.

    LEVEL overrides whatever level CONFIG specifies.

    Furthermore, this function registers the new logger inside the logging
    framework (we need this to keep track of parent-child relationships).

    This function returns the new logger.
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
        for handler_name in string.split(handler_names, ","):
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
# end initialize_logger



_handlers = dict()
def initialize_handler(name, config):
    """
    This function creates and initializes a handler NAME from an ini-file
    represented by CONFIG.

    If a handler NAME already exists, it is returned without any
    re-initialization.
    """

    if _handlers.has_key(name):
        return _handlers[name]
    # fi

    section_name = "handler_" + name
    klass = config.get(section_name, "class")
    options = config.options(section_name)
    if "formatter" in options:
        formatter = config.get(section_name, "formatter")
    else:
        formatter = ""
    # fi

    # Look up KLASS in the logging module + this file.
    namespace = logging.__dict__.copy()
    namespace.update(globals())
    klass = namespace[klass]

    #
    # We want all of our handlers to understand indentation directives
    klass = type("_dynamic_" + name, (klass, IndentingHandler), {})

    arguments = config.get(section_name, "args")
    arguments = eval(arguments, namespace)

    handler = apply(klass, arguments)

    # If there is a level specification in the ini-file, use it. 
    if "level" in options:
        level = config.get(section_name, "level")
        handler.setLevel(get_level(level))

    # formatters are initialized as needed.
    if formatter:
        handler.setFormatter(initialize_formatter(formatter, config))

    # The ctor does not accept maxsize/backcount, so we have to do a bit of
    # postprocessing.
    if klass == logging.FileHandler:
        maxsize = 0
        if "maxsize" in options:
            maxsize = config.getint(section_name, "maxsize")

        if maxsize:
            backcount = 0
            if "backcount" in options:
                backcount = config.getint(section_name, "backcount")

            handler.setRollover(maxsize, backcount)

    # IVR 2007-02-13 TBD: Why am I doing this?
    elif klass == handlers.MemoryHandler:
        raise ValueError, "Aiee! MemoryHandlers not supported yet"

    _handlers[name] = handler
    return handler
# end initialize_handler



_formatters = dict()
def initialize_formatter(formatter_name, config):
    """Initializes if necessary and returns a specific formatter."""

    # we have seen this one before...
    if formatter_name in _formatters:
        return _formatters[formatter_name]
    
    section_name = "formatter_" + formatter_name
    if not config.has_section(section_name):
        raise ConfigParser.NoSectionError("no formatter section " +
                                          section_name)

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
    f = IndentingFormatter(format, datefmt, indent)
    _formatters[formatter_name] = f
    return f
# end initialize_formatter



_logger_instance = None
def get_logger(config_file, logger_name = None):
    """
    Initialize (if necessary) and return the logger
    
    NB! get_logger will actually initialize anything only once. All
    subsequent calls from the same process (thread?) will return a reference
    to the same logger *regardless* of the LOGGER_NAME specified (this
    behavior is intentional).
    """
    global _logger_instance

    if _logger_instance is None:
        _logger_instance = cerelog_init(config_file, logger_name)
    # fi

    return _logger_instance
# end get_logger



def cerelog_init(config_file, name):
    "Run-once method for initializing everything in cerelog."

    # Load our constants
    init_cerebrum_extensions()

    # Load command-line controls
    logger_name, level = process_arguments()

    # If no command-line name was specified, use the one supplied
    if logger_name is None:
        logger_name = name
    # fi

    # Fall back to root as last resort
    if logger_name is None:
        logger_name = "root"
    # fi

    # Parse the config file. Do *NOT* ever call this more than once.
    return process_config(config_file, logger_name, level)
# end cerelog_init



class CerelogStreamWriter(codecs.StreamWriter):
    """Convert all input to specified charsets.

    The purpose of this class is to allow:

    stream.write('foo')
    stream.write('foo æøå')
    stream.write(unicode('foo'))
    stream.write(unicode('foo æøå', 'latin1'))

    ... so that the client code does not have to care about the
    encodings, regardless of the encodings specified in logging.ini.
    """

    def write(self, obj):
        """Force conversion to self.encoding."""

        # We force strings to unicode. Strings are assumed to be in latin1,
        # although this should be parametrised. 
        if self.encoding and isinstance(obj, str):
            obj = obj.decode("latin1")

        data, consumed = self.encode(obj, self.errors)
        self.stream.write(data)
    # end write

    def writelines(self, lines):

        self.write(''.join(lines))
    # end writelines
# end CerelogStreamWriter



class CerebrumLogger(logging.Logger, object):
    """
    This is the logger class used by the Cerebrum framework.
    """

    def __init__(self, name, level=logging.NOTSET):
        logging.Logger.__init__(self, name, level)
    # end __init__


    def findCaller(self):
        # Python versions prior to 2.4 want a 2-tuple in return from
        # this function, while later versions want a 3-tuple.
        if sys.version_info < (2, 4):
            rv = (None, None)
        else:
            rv = (None, None, None)
            
        frame = inspect.currentframe()
        while frame:
            # psyco replaces frame objects with proxies
            if type(frame) is not types.FrameType:
                return rv
        
            source = inspect.getsourcefile(frame)
            if source:
                source = os.path.normcase(source)
            #
            # We should test that source is neither *this* file, nor
            # anything else within the logging framework (be it 2.2 (extlib)
            # og 2.3 version).
            #
            if ((source != _srcfile) and
                (source and
                 (source.find("logging/__init__.py") == -1) and
                 (source.find("logging.py") == -1))):
                lineno = inspect.getlineno(frame)
                if sys.version_info < (2, 4):
                    rv = (source, lineno)
                else:
                    co = frame.f_code
                    rv = (source, lineno, co)
                break

            frame = frame.f_back

        return rv
      

    def __cerebrum_debug(self, level, msg, *args, **kwargs):
        if self.manager.disable >= level:
            return
        # fi

        if self.isEnabledFor(level):
            apply(self._log, (level, msg, args), kwargs)
        # fi
    # end __cerebrum_debug

    def callHandlers(self, record):
        super(CerebrumLogger, self).callHandlers(record)
    # end callHandlers


    def debug1(self, msg, *args, **kwargs):
        self.__cerebrum_debug(logging.DEBUG1, msg, *args, **kwargs)
    # end debug1

    def debug2(self, msg, *args, **kwargs):
        self.__cerebrum_debug(logging.DEBUG2, msg, *args, **kwargs)
    # end debug1

    def debug3(self, msg, *args, **kwargs):
        self.__cerebrum_debug(logging.DEBUG3, msg, *args, **kwargs)
    # end debug1

    def debug4(self, msg, *args, **kwargs):
        self.__cerebrum_debug(logging.DEBUG4, msg, *args, **kwargs)
    # end debug1

    def debug5(self, msg, *args, **kwargs):
        self.__cerebrum_debug(logging.DEBUG5, msg, *args, **kwargs)
    # end debug1

    def set_indent(self, indent=0):
        for handle in self.handlers:
            if hasattr(handle, "set_indent"):
                handle.set_indent(indent)
    # end set_indent
# end CerebrumLogger



class IndentingFormatter(logging.Formatter, object):
    """Mixin to extend the interface of our formatters.

    This class will be 'merged' into all formatters instantiated in
    cerelog. It cannot be used as a stand-alone class.
    """

    def __init__(self, fmt=None, datefmt=None, indent=0):
        super(IndentingFormatter, self).__init__(fmt, datefmt)
        self._indent = indent
    # end __init__

    def formatIndent(self, record):
        #
        # IVR 2007-02-13 FIXME: This should be parametrized (logging.ini)
        return " " * self._indent
    # end formatIndent

    def set_indent(self, indent=0):
        assert isinstance(indent, (int, long))
        self._indent = indent
    # end set_indent

    # Make sure this method is the first format() seen in MRO. Otherwise a
    # default would be used (which ignores the indent directive)
    def format(self, record):
        # IVR 2007-02-08 FIXME: This is a bit of hack, actually. formatTime is
        # similar, though.
        if string.find(self._fmt, "%(indent)") >= 0:
            record.indent = self.formatIndent(record)

        return super(IndentingFormatter, self).format(record)
    # end format
# end IndentingFormatter



class IndentingHandler(logging.Handler, object):
    """Mixin to extend the interface of out handlers.

    This class will be 'merged' into all handlers instantiated in cerelog. It
    cannot be used as a stand-alone class.
    """

    def set_indent(self, indent=0):
        if self.formatter:
            self.formatter.set_indent(indent)
    # end set_indent
# end IndentingHandler



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
    # end __init__


    def flush(self):
        if self.stream:
            self.stream.flush()
    # end flush


    def close(self):
        if self.stream:
            super(DelayedFileHandler, self).close()
    # end close


    def emit(self, record):
        if self.stream is None:
            self.open()

        super(DelayedFileHandler, self).emit(record)
    # end emit
    
    
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
        # but breaks down when we pass a string with øæå to a stream that
        # assumes the input is in UTF-8.
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
    # end open
# end DelayedFileHandler



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
    # end __init__
# end OneRunHandler        



class CerebrumRotatingHandler(DelayedFileHandler, object):
    "Cerebrum's own rotating handler."

    def __init__(self, logdir, mode="a", maxBytes=0, backupCount=0,
                 encoding=None):
        """
        Open a file somewhere[*] in LOGDIR and use it as the stream for
        logging.
        
        By default, the file grows indefinitely. You can specify particular
        values of MAXBYTES and BACKUPCOUNT to allow the file to rollover at
        a predetermined size.

        Rollover occurs whenever the current log file is nearly MAXBYTES in
        length. If BACKUPCOUNT is >= 1, the system will successively create
        new files with the same pathname as the base file, but with
        extensions ".1", ".2" etc. appended to it. For example, with a
        BACKUPCOUNT of 5 and a base file name of "app.log", you would get
        "app.log", "app.log.1", "app.log.2", ... through to "app.log.5". The
        file being written to is always "app.log" - when it gets filled up,
        it is closed and renamed to "app.log.1", and if files "app.log.1",
        "app.log.2" etc.  exist, then they are renamed to "app.log.2",
        "app.log.3" etc.  respectively.

        If MAXBYTES is zero, rollover never occurs.

        [*] The file naming scheme is a bit different from standard logging
        practice. LOGDIR indicates the base directory where *all* Cerebrum
        logs live. Each application gets its own directory. This is
        calculated dynamically from sys.argv[0]. Within such a directory,
        this handler would create a log file named 'log'. This log file's
        rotation is controlled by MAXBYTES/BACKUPCOUNT.
        """

        # All log files would be named "log", but this should not really be
        # a problem.

        self.logdir = logdir
        self.directory = os.path.basename(sys.argv[0])
        self.basename = "log"
        directory = os.path.join(self.logdir, self.directory)
        if not os.path.exists(directory):
            try:
                os.makedirs(directory, 0770)
            except OSError, e:    
                if not os.path.exists(directory):
                    # the error is not 'file exists', which we ignore
                    raise e
        # fi

        self.filename = os.path.join(self.logdir,
                                     self.directory,
                                     self.basename)
        super(CerebrumRotatingHandler, self).__init__(self.filename,
                                                      mode,
                                                      encoding)
        self.maxBytes = maxBytes
        self.backupCount = backupCount

        # FIXME: This can't be right -- changing mode *after* it has been set?
        self.mode = mode
        if maxBytes > 0:
            self.mode = "a+"
        # fi
    # end __init__

    
    def emit(self, record):
        """
        Emit a record.

        Output the record to the file, catering for rollover as described
        in doRollover().
        """
        try:
            if self.shouldRollover(record):
                self.doRollover()
            super(CerebrumRotatingHandler, self).emit(record)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)
    # end emit


    def shouldRollover(self, record):
        """Should we rotate the log files?"""

        # IVR 2007-02-13 TBD: There is a slight problem with delayed file
        # opening here: the stream is not open until the first write. So,
        # technically, we can cross a rollover limit :(
        
        # maxBytes == 0 => no rollover. Ever
        if self.maxBytes > 0:
            msg = self.format(record)
            if (self.stream and
                self.stream.tell() + len(msg) >= self.maxBytes):
                return True

        return False
    # end shouldRollover


    def doRollover(self):
        """This is a copy of logging.RotatingFileHandler."""

        self.stream.close()
        if self.backupCount > 0:
            for i in range(self.backupCount - 1, 0, -1):
                sfn = "%s.%d" % (self.baseFilename, i)
                dfn = "%s.%d" % (self.baseFilename, i + 1)
                if os.path.exists(sfn):
                    #print "%s -> %s" % (sfn, dfn)
                    if os.path.exists(dfn):
                        os.remove(dfn)
                    os.rename(sfn, dfn)
            dfn = self.baseFilename + ".1"
            if os.path.exists(dfn):
                os.remove(dfn)
            os.rename(self.baseFilename, dfn)
            #print "%s -> %s" % (self.baseFilename, dfn)

        # delayed opening. The superclass will take care of everything
        self.stream = None
    # end doRollover
# end CerebrumRotatingHandler



class CerebrumSubstituteHandler(CerebrumRotatingHandler):
    """
    This handler behaves just like CerebrumRotatingHandler, except it
    performs certain preprosessing of each message.

    Specifically, a substitution is performed on each message before the it
    is output. Substution is regexp-based (as defined by the module re). If
    either one is missing (i.e. is an empty string), no substitution will be
    performed (and the logger would behave exactly like its immediate
    parent).

    Additionally, since this kind of filtering is likely to be used in
    conjuction with confidential data (such as passwords), an additional
    permission parameter controls who has access to logfiles (regardless of
    the client process' umask).
    """


    def __init__(self, logdir, maxBytes, backupCount,
                 permissions, substitute, replacement, encoding=None):
        """
        LOGDIR       -- which directory the log goes to
        MAXBYTES     -- maximum file size before it is rotated (0 means no
                        rotation)
        BACKUPCOUNTS -- number of rotated files
        PERMISSIONS  -- UNIX-style permission number for the log file
        SUBSTITUTE   -- regular expression to perform substitution on
        REPLACEMENT  -- ... what to replace SUBSTITUTE with.
        """

        super(CerebrumSubstituteHandler, self).__init__(logdir, "a",
                                                        maxBytes,
                                                        backupCount, encoding)

        self.substitution = re.compile(substitute)
        self.replacement = replacement
        self.permissions = permissions
    # end __init__



    def open(self):
        super(CerebrumSubstituteHandler, self).open()
        # Force our permissions
        os.chmod(self.filename, self.permissions)
    # end open



    def format(self, record):
        msg = super(CerebrumSubstituteHandler, self).format(record)
        return self.substitution.sub(self.replacement, msg)
    # end format
# end CerebrumSubstituteHandler

# arch-tag: 9a057867-6fab-4b01-acdb-e515b600d225
