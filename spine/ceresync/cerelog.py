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

"""
This file is a part of the logging framework (cerelog).

A considerable part of this module has been inspired by the architecture of
python's logging module; you are advised to read that module's documentation
to familiarize yourself with certain logging concepts.


General:
--------

The basic separation of tasks into loggers, handlers and formatters is still
in place. However, the classes have been adapted to Cerebrum's
needs. CerebrumLogger uses five additional DEBUG levels and it can indent
messages. Several new handlers, filters and formatters appear in cerelog that
were not originally in the logging module.

The cerelog module has a configuration file, much akin to that of the logging
module. It uses the same ini-style sections and key-value pairs. However, a
number of items have been removed compared to the logging ini-file (explicit
lists of handlers, loggers and formatters), and a number of keys have been
removed from each section (the parsing code would accept logging-style
ini-files, but it will ignore some of the logging module's keys).

Moreover, no initialization takes place until a specific logger is
requested. In such a case ONLY such a logger and every entity ((parent)
loggers, handlers and formatters) 'reachable' from it are initialized (logging
module initializes everything listed in the configuration file).

Furthermore, no files/sockets/etc. are opened and no directories are created
unless there is a LogRecord that *has* to be written out.

The following parameters are fetched from cereconf:
- DEFAULT_LOGGER, which is the logger name used when nothing else is
  specified.


Multiple instances:
-------------------

Loggers have names, and there is only one logger instance for any given name.

Handlers have names, and there is only one handler instance for any given
name. It is probably a good idea *NOT* to have different loggers share a
handler from within the same process (e.g. for an SMTPHandler that does some
accounting, it would make sense to run process-wide accounting).

Formatters have names, but there can be many instances with the same name. NB!
If this is to change, remember to take care of indentation (same formatter,
receiving the same indent request multiple times).

Filters have names, but there can be many instances with the same name.


eval():
-------

In certain situations eval() is called to process some of the configuration
data for the logging framework. Specifically:

- For a filter section, all values are eval()'ed.
- For a handler section, the value for the key 'args' is eval()'ed.
- For a formatter section, all values are eval()'ed.
- For a logger section, eval() is never called.

Evaluation means among other things that the values can be arbitrary python
expressions, but they have to follow python's syntax rules. I.e. a string must
be enclosed within quotes (python's logging framework does not require this
for formatter sections).


Default configuration:
----------------------

If this module cannot find the configuration file, a 'default' logger is
initialized and returned. Such a logger would spew everything to stdout (it
might not be what one wanted, but it is a sensible default configuration).

Default values are:
for loggers -- CerebrumLogger
for handlers -- StreamHandler
for filters -- Filter (does nothing)
for formatters -- _defaultFormatter (outputs message only).


Backward compatibility:
-----------------------

* [loggers]/[handlers]/[formatters] are simply ignored. Just as well.
* channel/qualname are ignored.
* maxsize/backcount for FileHandler are ignored. They are passed in args key
  to RotatingFileHandler.
* args cannot be a tuple for FileHandler and RotatingFileHandler, use a
  dictionary instead. FileHandler and its subclasses use keyword arguments,
  since they have so many parameters.
* CerebrumSubstituteHandler is no more. It is the formatter's task to typeset
  LogRecords. Therefore, SubstitutingFormatter has taken over. As a bonus,
  this formatter can be used for any logger (and not only those that write to
  files).
* propagate is ignored.

All in all -- the configuration files designed for the logging module (and the
old Cerebrum logging framework) are parseable, but with somewhat different
semantics:

* parent= keys will no longer work (we do not use dotted name semantics in
  cerelog; parent relationships are listed explicitely).
* 


New features compared to python's logging setup/classes:
--------------------------------------------------------

* parent-child relationships are established by supplying a key 'parent' in
  the child logger. If such a key does not exist, it is equivalent to
  propagate being set to 0 in python logging.
* FileHandler behaves a bit different (see its __doc__)
* RotatingFileHandler behaves a bit different.
* All loggers/handlers/filters/formatters are in the same namespace
  (cerelog). As of python logging 2.3, some of the handlers/formatters are in
  their own namespace.
* cerelog's config parsing code interprets 'filter' keys. python's logging
  does not. 
* Only those loggers explicitely requested are initialized. python's logging
  initializes *everything* listed in the [logger] section
* sections starting with [filter_] represent filter configurations.
* 'args' key in handler sections can be any python expression. args being a
  list/tuple means optional arguments; args being a dictionary means keyword
  arguments. Everything else is taken as is.
* More values are eval()'ed than in python's logging. See above.
* Log destinations are opened on demand (i.e. when the first LogRecord is
  output).


Configuration:
--------------

If no configuration file is found, a default logger is returned.

If no section is found for a given logger name, name is set to
cereconf.DEFAULT_LOGGER.

Each of loggers, handlers, formatters and filters have their own sections. All
of these entities are identified by name. Each entity's section is prefixed
with the entity's type (i.e. '[filter_bar]' for a section describing a filter
named 'bar'). Loggers can refer to handlers and filters. Handlers can refer to
formatters and filters. The same name can be used for different entities (this
works because the section prefix will be different).

For loggers one can specify class, level, handlers (comma-separated sequence)
and filters (comma-separated sequence). E.g.:

[logger_foo]
class = fooclass
level = WARN
handlers = A, B
filters = A

If any of the keys is ommitted, a default value is assumed. Any other keys are
ignored.

For handlers, one can specify class, level, formatter, filters, args. E.g:

[handler_A]
class = FileHandler
level = NOTSET
formatter = A
args  = { 'filename'    : '/tmp/a.log',
          'permissions' : 0700, }

The value of 'args' differs from handler to handler (although in all cases it
should be a python expression). If some keys are missing, a default value is
assumed.

For formatters, one can specify anything, since all key=value pairs are given
to the constructor. At least these keys are recognized by all formatters:
class, format, dateformat, prefix, indent. E.g.:

[formatter_A]
patterns  = [ ('foobar', 'zotbar') ]
class     = SubstitutingFormatter
format    = '%(asctime)s %(levelname)s %(message)s'
prefix    = '    '
indent    = 0
dateformat= '%F %T'

(In this example, the key 'patterns' is meaningful for SubstitutingFormatter
class only). NB! The value of format/dateformat must be quoted
(python-style). This is different from the behaviour of python's logging.

For filters, one can specify anything, since all key=value pairs are given to
the constructor. At least these keys are recognized by all filters:
class. E.g.:

[filter_A]
class      = DumbSuppressionFilter
patterns   = [ ('failure', 2),
               ('never', 0), ]

(The key 'patterns' is meaningful for DumbSuppressionFilter only.)


Examples:
---------

The examples presented in the logging.py package apply to this module as well
as to the standard logging package. However, in Cerebrum context this module
is to be used in conjuction with Factory:

import cerebrum_path, cereconf
from Cerebrum.Utils import Factory

l = Factory.get_logger('foo')
l.info('blubb blubb')
"""

import types, time, os, sys, string, types, cStringIO, traceback, re

try:
    import inspect
except ImportError:
    inspect = None

try:
    import thread
    import threading
except ImportError:
    thread = None


#
#_srcfile is used when walking the stack to check when we've got the first
# caller stack frame.
#
if string.lower(__file__[-4:]) in ['.pyc', '.pyo']:
    _srcfile = __file__[:-4] + '.py'
else:
    _srcfile = __file__
_srcfile = os.path.normcase(_srcfile)

# _srcfile is only used in conjunction with sys._getframe().  To provide
# compatibility with older versions of Python, set _srcfile to None if
# _getframe() is not available; this value will prevent findCaller() from
# being called.
if not hasattr(sys, "_getframe"):
    _srcfile = None



#
# _startTime is used as the base when calculating the relative time of events
#
_startTime = time.time()



######################################################################
# Severity/level related code
#
# Additional levels can be introduced as well (just respect higher numerical
# value => more serious error).
# 
######################################################################

CRITICAL = 50
FATAL = CRITICAL
ERROR = 40
WARNING = 30
WARN = WARNING
INFO = 20
DEBUG = 10
DEBUG1 = 9
DEBUG2 = 8
DEBUG3 = 7
DEBUG4 = 6
DEBUG5 = 5
NOTSET = 0
ALL = NOTSET

_levelNames = {
    CRITICAL  : "CRITICAL",
    ERROR     : "ERROR",
    WARNING   : "WARNING",
    INFO      : "INFO",
    DEBUG     : "DEBUG",
    DEBUG1    : "DEBUG1",
    DEBUG2    : "DEBUG2",
    DEBUG3    : "DEBUG3",
    DEBUG4    : "DEBUG4",
    DEBUG5    : "DEBUG5",     
    NOTSET    : "NOTSET",
}

def getLevelName(level):
    """
    Return the textual representation of logging level 'level'.

    If the level is one of the predefined levels (CRITICAL, ERROR, WARNING,
    INFO, DEBUG) then you get the corresponding string. If you have
    associated levels with names using addLevelName then the name you have
    associated with 'level' is returned.

    If a numeric value corresponding to one of the defined levels is passed
    in, the corresponding string representation is returned.

    Otherwise, the string "Level %s" % level is returned.
    """

    _acquireLock()
    try:
        level = _levelNames.get(level, ("Level %s" % level))
    finally:
        _releaseLock()
    
    return level





######################################################################
# Threading code
#
# _lock is used to serialize access to shared data structures in this module.
# This needs to be an RLock because fileConfig() creates Handlers and so might
# arbitrary user threads. Since Handler.__init__() updates the shared
# dictionary _handlers, it needs to acquire the lock. But if configuring, the
# lock would already have been acquired - so we need an RLock.  The same
# argument applies to Loggers and Manager.loggerDict.
#
######################################################################

_lock = None

def _acquireLock():
    """
    Acquire the module-level lock for serializing access to shared data.

    This should be released with _releaseLock().
    """
    
    global _lock
    if (not _lock) and thread:
        _lock = threading.RLock()
    
    if _lock:
        _lock.acquire()


def _releaseLock():
    """
    Release the module-level lock acquired by calling _acquireLock().
    """
    
    if _lock:
        _lock.release()





######################################################################
# Log records
# 
######################################################################

class LogRecord:
    """
    A LogRecord instance represents an event being logged.

    LogRecord instances are created every time something is logged. They
    contain all the information pertinent to the event being logged. The
    main information passed in is in msg and args, which are combined using
    str(msg) % args to create the message field of the record. The record
    also includes information such as when the record was created, the
    source line where the logging call was made, and any exception
    information to be logged.

    FIXME: Do we need 'name' at all? That crap only clutters the setup file.
    """

    def __init__(self, name, level, pathname, lineno, msg, args, exc_info):
        """
        Initialize a logging record with interesting information.
        """
        
        ct = time.time()
        self.name = name
        self.msg = msg
        self.args = args
        self.levelname = getLevelName(level)
        self.levelno = level
        self.pathname = pathname
        
        try:
            self.filename = os.path.basename(pathname)
            self.module = os.path.splitext(self.filename)[0]
        except:
            self.filename = pathname
            self.module = "Unknown module"
        
        self.exc_info = exc_info
        self.exc_text = None      # used to cache the traceback text
        self.lineno = lineno
        self.created = ct
        self.msecs = (ct - long(ct)) * 1000
        self.relativeCreated = (self.created - _startTime) * 1000

        if thread:
            self.thread = thread.get_ident()
        else:
            self.thread = None
        
        if hasattr(os, 'getpid'):
            self.process = os.getpid()
        else:
            self.process = None


    def __str__(self):
        
        return '<LogRecord: %s, %s, %s, %s, "%s">' % (self.name,
                                                      self.levelno,
                                                      self.pathname,
                                                      self.lineno,
                                                      self.msg)


    def getMessage(self):
        """
        Return the message for this LogRecord.

        Return the message for this LogRecord after merging any
        user-supplied arguments with the message.
        """
        
        if not hasattr(types, "UnicodeType"): #if no unicode support...
            msg = str(self.msg)
        else:
            try:
                msg = str(self.msg)
            except UnicodeError:
                msg = self.msg      #Defer encoding till later
            
        if self.args:
            msg = msg % self.args

        return msg


    def getStateString(self):
        """
        LogRecords returning same state strings are considered to be identical
        for the purpose of message suppresion

        FIXME: Just returning self.msg is probably not enough. Maybe we need a
        finer-grane differentiation (interpolate basename in?)
        """

        return self.msg




def makeLogRecord(dict):
    """
    Make a LogRecord whose attributes are defined by the specified dictionary,
    This function is useful for converting a logging event received over a
    socket connection (which is sent as a dictionary) into a LogRecord
    instance.
    """
    
    rv = LogRecord(None, None, "", 0, "", (), None)
    rv.__dict__.update(dict)
    return rv




    def findCaller(self):
        rv = (None, None)
        frame = inspect.currentframe()
        while frame:
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
                rv = (source, lineno)
                break

            frame = frame.f_back

        return rv
      

######################################################################
# Formatter code
######################################################################

class Formatter(object):
    """
    Formatter instances are used to convert a LogRecord to text.

    Formatters need to know how a LogRecord is constructed. They are
    responsible for converting a LogRecord to (usually) a string which can
    be interpreted by either a human or an external system. The base Formatter
    allows a formatting string to be specified. If none is supplied, the
    default value of "%s(message)\\n" is used.

    The Formatter can be initialized with a format string which makes use of
    knowledge of the LogRecord attributes - e.g. the default value mentioned
    above makes use of the fact that the user's message and arguments are pre-
    formatted into a LogRecord's message attribute. Currently, the useful
    attributes in a LogRecord are described by:

    %(name)s            Name of the logger (logging channel)
    %(levelno)s         Numeric logging level for the message (DEBUG, INFO,
                        WARNING, ERROR, CRITICAL)
    %(levelname)s       Text logging level for the message ("DEBUG", "INFO",
                        "WARNING", "ERROR", "CRITICAL")
    %(pathname)s        Full pathname of the source file where the logging
                        call was issued (if available)
    %(filename)s        Filename portion of pathname
    %(module)s          Module (name portion of filename)
    %(lineno)d          Source line number where the logging call was issued
                        (if available)
    %(created)f         Time when the LogRecord was created (time.time()
                        return value)
    %(asctime)s         Textual time when the LogRecord was created
    %(msecs)d           Millisecond portion of the creation time
    %(relativeCreated)d Time in milliseconds when the LogRecord was created,
                        relative to the time the logging module was loaded
                        (typically at application startup time)
    %(thread)d          Thread ID (if available)
    %(process)d         Process ID (if available)
    %(message)s         The result of record.getMessage(), computed just as
                        the record is emitted.
    """

    converter = time.localtime

    def __init__(self, **keys):
        """
        Initialize the formatter with specified format strings.

        The following keys are recognized:

        format          Message format (or %(message)s if none given)
        dateformat      Date format (or ISO8601 if none given)
        prefix          Prefix to use for indentation (or ' '*4 if none given)
        indent          Initial indent value (i.e. messages will be prepended
                        with prefix*indent)

        Initialize the formatter either with the specified format string, or a
        default as described above. Allow for specialized date formatting with
        the optional dateformat argument (if omitted, you get the ISO8601 format).
        """

        self._fmt = keys.get("format", "%(message)s")
        self.dateformat = keys.get("dateformat")
        self.prefix = keys.get("prefix", ' '*4)
        # We start with no indent
        self.indent = keys.get("indent", 0)
        self.initial_indent = self.indent
        

    def set_indent(self):
        self.indent = self.indent + 1


    def set_dedent(self):
        self.indent = max(self.indent - 1, self.initial_indent)


    def reset_indent(self):
        self.indent = self.initial_indent
    

    def formatTime(self, record, dateformat = None):
        """
        Return the creation time of the specified LogRecord as formatted text.

        This method should be called from format() by a formatter which
        wants to make use of a formatted time. This method can be overridden
        in formatters to provide for any specific requirement, but the
        basic behaviour is as follows: if dateformat (a string) is specified,
        it is used with time.strftime() to format the creation time of the
        record. Otherwise, the ISO8601 format is used. The resulting
        string is returned. This function uses a user-configurable function
        to convert the creation time to a tuple. By default, time.localtime()
        is used; to change this for a particular formatter instance, set the
        'converter' attribute to a function with the same signature as
        time.localtime() or time.gmtime(). To change it for all formatters,
        for example if you want all logging times to be shown in GMT,
        set the 'converter' attribute in the Formatter class.
        """
        
        ct = self.converter(record.created)
        if dateformat:
            s = time.strftime(dateformat, ct)
        else:
            t = time.strftime("%Y-%m-%d %H:%M:%S", ct)
            s = "%s,%03d" % (t, record.msecs)
        
        return s


    def formatException(self, ei):
        """
        Format and return the specified exception information as a string.

        FIXME: We *must* respect self.indent and self.prefix. tracebacks are
        usually multiline.
        """

        sio = cStringIO.StringIO()
        traceback.print_exception(ei[0], ei[1], ei[2], None, sio)
        s = sio.getvalue()
        sio.close()
        if s[-1] == "\n":
            s = s[:-1]
        return s


    def format(self, record):
        """
        Format the specified record as text.

        The record's attribute dictionary is used as the operand to a string
        formatting operation which yields the returned string.  Before
        formatting the dictionary, a couple of preparatory steps are carried
        out. The message attribute of the record is computed using
        LogRecord.getMessage(). If the formatting string contains
        "%(asctime)", formatTime() is called to format the event time.  If
        there is exception information, it is formatted using
        formatException() and appended to the message.
        """
        
        record.message = record.getMessage()
        
        if string.find(self._fmt, "%(asctime)") >= 0:
            record.asctime = self.formatTime(record, self.dateformat)
        
        s = self._fmt % record.__dict__
        
        if record.exc_info:
            # Cache the traceback text to avoid converting it multiple times
            # (it's constant anyway)
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
        
        if record.exc_text:
            if s[-1] != "\n":
                s = s + "\n"
            
            s = s + record.exc_text

        # If we need to indent, paste inn the right number of prefixes after
        # each \n
        if self.indent:
            s = s.replace('\n', "\n%s" % (self.prefix*self.indent))
            # Prepend the very first line
            s = (self.prefix*self.indent) + s
        
        return s



class SubstitutingFormatter(Formatter):
    """
    This formatter behaves similar to Formatter, except that it can perform
    a number of substitutions on every message before the latter is output.
    """

    def __init__(self, **keys):
        """
        KEYS has among other things a set of patterns to apply to each
        message. The key for the pattern list is 'patterns'.

        The pattern list looks like this:

        [ (pattern1, substitution1),
          (pattern2, substitution2),
          (pattern3, substitution3),
          ...
          (patternN, substitutionN),
        ]

        Each pattern and substitution is a regex. substitution can use
        backreferences. It is probably a good idea to:

        1. Not make this list too long, since each pattern is applied to
           *each* message.
        2. Be careful that substitution_{i-1} does not match pattern_{i} by
           accident. 
        """

        super(SubstitutingFormatter, self).__init__(**keys)

        self.patterns = keys.get("patterns", list())
        compiled_patterns = list()
        for (pattern, substitution) in self.patterns:
            compiled_patterns.append((re.compile(pattern), substitution))

        self.patterns = compiled_patterns


    def format(self, record):
        """
        Perform all the substitutions on RECORD.

        First we typeset the message and then perform all substitutions _in
        order_.
        """

        # This gives us a 'typeset' message.
        message = super(SubstitutingFormatter, self).format(record)

        # Now we can apply substitutions:
        for (matchobj, substitution) in self.patterns:
            message = matchobj.sub(substitution, message)

        return message
    

_defaultFormatter = Formatter()





######################################################################
# Filter code
######################################################################

 
class Filter(object):
    """
    Filter instances are used to perform arbitrary filtering of LogRecords.
    """

    def __init__(self):
        super(Filter, self).__init__()


    def filter(self, record):
        """
        Determine if the specified record is to be logged.

        Is the specified record to be logged? Returns 0 for no, nonzero for
        yes. If deemed appropriate, the record may be modified in-place.

        By default, we let everything through.
        """

        return 1



class DumbSuppressionFilter(Filter):
    """
    This filter suppresses the messages that had been repeated more than a
    given number of times.

    This is just a proof-of-concept implementation, and it SHOULD NOT be
    used for any important tasks.
    """

    def __init__(self, **keys):
        """
        KEYS contains a pattern list under the key 'pattern'. It is a
        sequence of tuples (pattern, count), where COUNT determines how many
        times a message matching PATTERN can be sent before it gets dropped.
        """

        super(DumbSuppressionFilter, self).__init__()

        # A dictionary that maps patterns to occurrance counts. Each entry
        # looks like:
        # pattern -> current
        # ... where current is the number of occurances seen so far
        
        self.state = dict()

        # We need this list to preserve the order in which patterns are
        # searched (it should be the same as in the config file. Had it not
        # been for this in-order processing, we could have used state.keys()

        self.patterns = list()
        
        for pattern, count in keys.get("patterns", list()):
            match_object = re.compile(pattern)
            self.patterns.append((match_object, count))
            self.state[match_object] = 0


    def filter(self, record):
        """
        Look at the RECORD's tag and compare it to all patterns.
        
        Each record has a printable 'tag' that is independent of its
        arguments. This is allows us to track 'same' (in the sense of
        suppression) messages even though their exact printable
        representation differs. E.g. we might want to:

        logger.warn('Aiee: failed entity %s', something)
        logger.warn('Aiee: failed entity %s', somethingelse)

        to count twice toward the pattern 'Aiee: failed'.
        """

        tag = record.getStateString()

        for (match_object, limit) in self.patterns:
            if match_object.search(tag) is not None:
                self.state[match_object] += 1

                if self.state[match_object] > limit:
                    # suppress the message
                    return 0

        return 1
    



class Filterer(object):
    """
    A base class for loggers and handlers which allows them to share
    common code.
    """

    def __init__(self):
        """
        Initialize the list of filters to be an empty list.
        """

        super(Filterer, self).__init__()

        self.filters = []


    def addFilter(self, filter_obj):
        """
        Add the specified filter to this handler.
        """

        if filter_obj not in self.filters:
            self.filters.append(filter_obj)
    

    def removeFilter(self, filter_obj):
        """
        Remove the specified filter from this handler.
        """
        if filter_obj in self.filters:
            self.filters.remove(filter_obj)


    def filter(self, record):
        """
        Determine if a record is loggable by consulting all the filters.

        The default is to allow the record to be logged; any filter can veto
        this and the record is then dropped. Returns a zero value if a record
        is to be dropped, else non-zero.
        """

        for f in self.filters:
            if not f.filter(record):
                return 0
        
        return 1
    





######################################################################
# Handler code
######################################################################

class Handler(Filterer):
    """
    Handler instances dispatch logging events to specific destinations.

    The base handler class. Acts as a placeholder which defines the Handler
    interface. Handlers can optionally use Formatter instances to format
    records as desired. By default, no formatter is specified; in this case,
    the 'raw' message as determined by record.message is logged.
    """

    def __init__(self, level=NOTSET):
        """
        Initializes the instance - basically setting the formatter to None
        and the filter list to empty.
        """

        super(Handler, self).__init__()
        
        self.level = level
        self.formatter = None
        self.createLock()
        self._opened = False


    def open(self):
        raise NotImplementedError, \
              'open must be implemented by Handler subclasses'


    def createLock(self):
        """
        Acquire a thread lock for serializing access to the underlying I/O.
        """
        if thread and not hasattr(self, "lock"):
            self.lock = thread.allocate_lock()
        else:
            self.lock = None
    

    def acquire(self):
        """
        Acquire the I/O thread lock.
        """
        if self.lock: self.lock.acquire()


    def release(self):
        """
        Release the I/O thread lock.
        """

        if self.lock: self.lock.release()
    

    def setLevel(self, level):
        """
        Set the logging level of this handler.
        """

        self.level = level
    

    def format(self, record):
        """
        Format the specified record.

        If a formatter is set, use it. Otherwise, use the default formatter
        for the module.
        """

        if self.formatter:
            fmt = self.formatter
        else:
            fmt = _defaultFormatter
        
        return fmt.format(record)
    

    def emit(self, record):
        """
        Do whatever it takes to actually log the specified logging record.

        This version is intended to be implemented by subclasses and so
        raises a NotImplementedError.
        """

        raise NotImplementedError, \
              'emit must be implemented by Handler subclasses'
    

    def handle(self, record):
        """
        Conditionally emit the specified logging record.

        Emission depends on filters which may have been added to the handler.
        Wrap the actual emission of the record with acquisition/release of
        the I/O thread lock. Returns whether the filter passed the record for
        emission.
        """
        rv = self.filter(record)
        if rv:
            if not self._opened:
                self.open()

            self.acquire()
            try:
                self.emit(record)
            finally:
                self.release()
        
        return rv
    

    def setFormatter(self, fmt):
        """
        Set the formatter for this handler.
        """
        self.formatter = fmt


    def flush(self):
        """
        Ensure all logging output has been flushed.

        This version does nothing and is intended to be implemented by
        subclasses.
        """
        pass


    def close(self):
        """
        Tidy up any resources used by the handler.

        This version does nothing and is intended to be implemented by
        subclasses.
        """
        pass
    

    def handleError(self, record):
        """
        Handle errors which occur during an emit() call.

        This method should be called from handlers when an exception is
        encountered during an emit() call. NB! This will output something to
        the stderr, but the logging system should never fail, so this is
        probably sensible behaviour.
        """

        ei = sys.exc_info()
        traceback.print_exception(ei[0], ei[1], ei[2], None, sys.stderr)


    def set_indent(self):
        if self.formatter is not None:
            self.formatter.set_indent()


    def set_dedent(self):
        if self.formatter is not None:
            self.formatter.set_dedent()


    def reset_indent(self):
        if self.formatter is not None:
            self.formatter.reset_indent()



class StreamHandler(Handler):
    """
    A handler class which writes logging records, appropriately formatted, to
    a stream. Note that this class does not close the stream, as sys.stdout or
    sys.stderr may be used.
    """

    def __init__(self, strm=None):
        """
        Initialize the handler.

        If strm is not specified, sys.stderr is used.
        """

        super(StreamHandler, self).__init__()

        # We do not really need this, but this behaviour is compatible with
        # logging (and it makes for shorter config files).
        if not strm:
            strm = sys.stderr
        
        self.stream = strm
        self.formatter = None


    def open(self):
        self._opened = True
    

    def flush(self):
        """
        Flushes the stream.
        """
        self.stream.flush()
    

    def emit(self, record):
        """
        Emit a record.

        If a formatter is specified, it is used to format the record.
        The record is then written to the stream with a trailing newline
        [N.B. this may be removed depending on feedback]. If exception
        information is present, it is formatted using
        traceback.print_exception and appended to the stream.
        """

        try:
            msg = self.format(record)
            if not hasattr(types, "UnicodeType"): #if no unicode support...
                self.stream.write("%s\n" % msg)
            else:
                try:
                    self.stream.write("%s\n" % msg)
                except UnicodeError:
                    self.stream.write("%s\n" % msg.encode("UTF-8"))
            self.flush()
        except:
            self.handleError(record)
            # FIXME: re-raise?
    



class FileHandler(StreamHandler):
    """
    A handler class which writes formatted logging records to disk files.
    """

    def __init__(self, **keys):
        """
        Open the specified file and use it as the stream for
        logging. Available keyword arguments are:

        filename	filename
        mode		open mode (write, append)
        permissions     permissions on FILENAME (can be written as an octal
                        constant).
        group           group ownership by group name (if available).
        gid             group ownership by gid (if available).
        """

        filename = keys.get("filename")
        mode = keys.get("mode", "a+")
        permissions = keys.get("permissions")
        group = keys.get("group")
        gid = keys.get("gid")

        super(FileHandler, self).__init__(None)
        
        self.filename = filename
        self.mode = mode
        self.permissions = permissions
        self.group = None
        self.gid = None


    def open(self):
        if self._opened:
            return

        # FIXME: This is ugly, as we hack around the base class'
        # initialization routines. Basically, anything inheriting from
        # StreamHandler would have to do it this way (StreamHandler needs an
        # already open stream, which we cannot provide until there is a call
        # to output a LogRecord).
        
        assert isinstance(self.filename, str), \
               "Missing filename for %s instance" % self.__class__.__name__
        
        self.stream = open(self.filename, self.mode)

        if hasattr(os, "chmod") and self.permissions is not None:
            os.chmod(self.filename, self.permissions)

        if self.group: self.__setGroup(self.group)

        if self.gid: self.__setGID(self.gid)

        super(FileHandler, self).open()


    def __setGID(self, gid):
        """
        Force a given GID, if such a service is available.
        """

        if hasattr(os, "chown") and gid is not None:
            os.chown(self.filename, -1, gid)
            self.gid = gid
            self.group = self.__getGroup(gid=gid)


    def __setGroup(self, group):
        """
        Force a given GROUP (we have to look up the gid first).
        """

        self.__setGID(self.__getGroup(group=group))


    def __getGroup(self, **keys):
        """
        Return group name for GID (and GID for group name), if available. Valid
        keyword arguments are 'gid' and 'group'.
        """

        try:
            import grp
        except ImportError:
            return None

        if keys.get("gid") is not None:
            return grp.getgrgid(keys["gid"])[2]
        elif keys.get("group") is not None:
            return grp.getgrnam(keys["group"])[2]

        return None
        

    def close(self):
        """
        Closes the stream.
        """
        self.stream.close()
        self._opened = False



class RotatingFileHandler(FileHandler):
    """
    Cerebrum's rotating handler.

    The handler rotates its output file every so often.
    """

    def __init__(self, **keys):
        """
        The following keys are recognized in addition to FileHandler's keys:

        maxBytes       - maximum size before rollover (default: unlimited)
        backupCount    - number of rollovers (default: no rollover)
        logDir         - directory where all the log files are rotated.
        dirPermissions - directory permissions for directories that might be
                         created.
        ageSeconds     - how old a file can become before rollover (NOT
                         implemented)

        The rollover occurs when one of the following is true:

        * The log file is nearly MAXBYTES in length
        * The log file is at least AGESECONDS old (NOT implemented)

        """

        # LOGDIR is where _all_ the processes rotate their logs
        # DIRECTORY is where *this* process rotates its logs
        # BASENAME is the name of the file (or 'log', if none given)
        #
        # So, an instance of this class would write to the file
        #     os.path.join(self.logdir, self.directory, self.basename)
        # 
        self.logdir = keys.get("logDir", "")
        self.directory = os.path.basename(sys.argv[0])
        self.basename = keys.get("filename", "log")
        self.dirpermissions = keys.get("dirPermissions", 0770)
        self.maxBytes = keys.get("maxBytes", 0)
        self.backupCount = keys.get("backupCount", 0)
        if maxBytes > 0:
            self.mode = "a"

        keys["filename"] = os.path.join(self.logdir,
                                        self.directory, self.basename)
        super(RotatingFileHandler, self).__init__(**keys)


    def open(self):

        if self._opened:
            return

        # If the destination directory does not exist -- create it
        directory = os.path.join(self.logdir, self.directory)
        if not os.path.exists(directory):
            try:
                os.makedirs(directory, self.dirpermissions)
            except OSError, e:
                if not os.path.exists(directory):
                    # This error is NOT 'file exists', which we ignore, but
                    # something else.
                    raise e

        super(RotatingFileHandler, self).open()

        
    def emit(self, record):
        """
        Emit a record.

        Output the record to the file, catering for rollover as described in
        setRollover().
        """

        if self.maxBytes > 0:
            msg = "%s\n" % self.format(record)
            self.stream.seek(0, 2)  #due to non-posix-compliant Windows feature
            if self.stream.tell() + len(msg) >= self.maxBytes:
                self.doRollover()
        
        super(RotatingFileHandler, self).emit(self, record)
        self._opened = True


    def doRollover(self):
        """
        Do a rollover, as described in __init__().
        """

        self.stream.close()
        if self.backupCount > 0:
            for i in range(self.backupCount - 1, 0, -1):
                sfn = "%s.%d" % (self.filename, i)
                dfn = "%s.%d" % (self.filename, i + 1)
                if os.path.exists(sfn):
                    #print "%s -> %s" % (sfn, dfn)
                    if os.path.exists(dfn):
                        os.remove(dfn)
                    
                    os.rename(sfn, dfn)
            
            dfn = self.filename + ".1"
            if os.path.exists(dfn):
                os.remove(dfn)
            
            os.rename(self.filename, dfn)
        self.stream = open(self.baseFilename, "w")





######################################################################
# Logger code
######################################################################

class CerebrumLogger(Filterer):
    """
    Logger class used by the Cerebrum framework .
    """

    def __init__(self, name, level = NOTSET):
        Filterer.__init__(self)

        self.name = name
        self.level = level
        self.parent = None
        self.handlers = list()
        self.disabled = 0


    def setLevel(self, level):
        """
        Set the logging level of this logger.
        """
        self.level = level

                                                               
    def _log(self, level, msg, args, exc_info=None):                                   
        """                                                                            
        Low-level logging routine which creates a LogRecord and then calls             
        all the handlers of this logger to handle the record.                          
        """                                                                            

        # Do we need to handle this one?
        if self.getEffectiveLevel() > level:
            return

        if _srcfile:
            fn, lno = self.findCaller()
        else:
            fn, lno = "<unknown file>", 0
        
        if exc_info:
            if type(exc_info) != types.TupleType:
                exc_info = sys.exc_info()

        record = self.makeRecord(self.name, level, fn, lno, msg, args, exc_info)
        self.handle(record)
    
    
    def debug(self, msg, *args, **kwargs):
        """
        Log 'msg % args' with severity 'DEBUG'.

        To pass exception information, use the keyword argument exc_info with
        a true value, e.g.

        logger.debug('Houston, we have a %s', 'thorny problem', exc_info=1)
        """
        
        self._log(DEBUG, msg, args, **kwargs)


    def debug1(self, msg, *args, **kwargs):
        self._log(DEBUG1, msg, args, **kwargs)

    def debug2(self, msg, *args, **kwargs):
        self._log(DEBUG2, msg, args, **kwargs)

    def debug3(self, msg, *args, **kwargs):
        self._log(DEBUG3, msg, args, **kwargs)

    def debug4(self, msg, *args, **kwargs):
        self._log(DEBUG4, msg, args, **kwargs)

    def debug5(self, msg, *args, **kwargs):
        self._log(DEBUG5, msg, args, **kwargs)

    def info(self, msg, *args, **kwargs):
        """
        INFO-level shortcut
        """

        self._log(INFO, msg, args, **kwargs)


    def warning(self, msg, *args, **kwargs):
        """
        WARNING-level shortcut
        """

        self._log(WARNING, msg, args, **kwargs)

    warn = warning


    def error(self, msg, *args, **kwargs):
        """
        INFO-level shortcut
        """

        self._log(ERROR, msg, args, **kwargs)


    def exception(self, msg, *args):
        """
        Convenience method for logging an ERROR with exception information.
        """

        # I feel pretty, la la la la la-laaaa...
        self.error(msg, *args, **{'exc_info': 1})

                                                                                       
    def critical(self, msg, *args, **kwargs):                                          
        """                                                                            
        CRITICAL-level shortcut
        """                                                                            

        self._log(CRITICAL, msg, args, kwargs)
                                                                                       
    fatal = critical


    def log(self, level, msg, *args, **kwargs):
        """
        Log 'msg % args' with the integer severity 'level'.

        To pass exception information, use the keyword argument exc_info with
        a true value, e.g.

        logger.log(level, 'We have a %s', 'mysterious problem', exc_info=1)
        """

        if type(level) != types.IntType:
            raise TypeError, "level must be an integer"

        self._log(level, msg, args, **kwargs)


    def findCaller(self):
        """
        Find the stack frame of the caller so that we can note the source
        file name and line number.
        """

        if inspect is None:
            return None, None

        frame = inspect.currentframe()
        while 1:
            co = frame.f_code
            filename = os.path.normcase(co.co_filename)
            if filename == _srcfile:
                frame = frame.f_back
                continue
            
            return filename, frame.f_lineno


    def makeRecord(self, name, level, fn, lno, msg, args, exc_info):
        """
        A factory method which can be overridden in subclasses to create
        specialized LogRecords.
        """

        return LogRecord(name, level, fn, lno, msg, args, exc_info)


    def handle(self, record):
        """
        Call the handlers for the specified record.

        This method is used for unpickled records received from a socket, as
        well as those created locally. Logger-level filtering is applied.
        """

        if (not self.disabled) and self.filter(record):
            self.callHandlers(record)


    def addHandler(self, hdlr):
        """
        Add the specified handler to this logger.
        """

        if not (hdlr in self.handlers):
            self.handlers.append(hdlr)


    def removeHandler(self, hdlr):
        """
        Remove the specified handler from this logger.
        """

        if hdlr in self.handlers:
            # hdlr.close()
            self.handlers.remove(hdlr)


    def callHandlers(self, record):
        """
        Pass a record to all relevant handlers.

        Loop through all handlers for this logger and its parents in the
        logger hierarchy. If no handler was found, output a one-off error
        message to sys.stderr. Stop searching up the hierarchy whenever a
        logger with parent that evaluates to False is found - that will be the
        last logger whose handlers are called.
        """

        c = self
        found = 0
        while c:
            for hdlr in c.handlers:
                found = found + 1
                if record.levelno >= hdlr.level:
                    hdlr.handle(record)

            c = c.parent

        if (found == 0):
            sys.stderr.write("No handlers could be found for logger"
                             " \"%s\"\n" % self.name)


    def getEffectiveLevel(self):
        """
        Get the effective level for this logger.

        Loop through this logger and its parents in the logger hierarchy,
        looking for a non-zero logging level. Return the first one found.
        """

        logger = self
        while logger:
            if logger.level:
                return logger.level
            logger = logger.parent
        return NOTSET


    def isEnabledFor(self, level):
        """
        Is this logger enabled for level 'level'?
        """

        return level >= self.getEffectiveLevel()


    def set_indent(self):
        for h in self.handlers:
            h.set_indent()
        

    def set_dedent(self):
        for h in self.handlers:
            h.set_dedent()


    def reset_indent(self):
        for h in self.handlers:
            h.reset_indent()





class AutoStudLogger(CerebrumLogger):
    """
    We need a special logger for UiO-related needs.

    This logger works with one FileHandler only.
    """

    def _help_constraints(self):
        assert len(self.handlers) == 1, \
               "%s must have exactly one FileHandler" % self.__class__.__name__
        assert isinstance(self.handlers[0], FileHandler), \
               "%s must have one *FileHandler*" % self.__class__.__name__

    def addHandler(self, hdlr):
        super(AutoStudLogger, self).addHandler(hdlr)

        self._help_constraints()

    def _log(self, level, msg, args, exc_info=None):
        """
        This is just an insurance policy -- we *must* make sure that before
        logging, a destination is set.
        """
        self._help_constraints()

        super(AutoStudLogger, self)._log(level, msg, args, exc_info)

    def set_destination(self, filename):
        self._help_constraints()

        h = self.handlers[0]
        assert (h.filename is None), \
               "Log destination may be set only once"

        h.filename = filename






######################################################################
# Initialization code
######################################################################
#
logger_long_options = ("logger-name", "logger-level")

def fetch_logger_arguments():
    """
    Logger must be capable of extracting program arguments controlling its
    behaviour without the knowledge of other arguments that might be
    present.

    It is a bit of a hack though (ideally, we would want to use getopt).
    """

    result = dict()
    options = [ "--" + x for x in logger_long_options ]
    args = sys.argv
    i = 0
    while i < len(args) and args[i] != "--":
        arg = args[i].split('=', 2)[0]

        # 1) we require an exact match
        # 2) we ignore everything but the logger options (getopt cannot do
        #    that)
        if arg in options:

            # If we see a logger argument, we must have a value following it
            if (i == len(args) - 1) or args[i+1].startswith("-"):
                raise RuntimeError("Missing argument for option: %s" % arg)

            # Two cases:
            # Case 1: --key=value
            if args[i].find("=") != -1:
                argument, value = args[i].split("=", 2)
            # Case 2: --key value
            else:
                argument, value = args[i], args[i+1]
                i += 1
        
            argument = argument.lstrip("-")
            result[argument] = value

        i += 1

    return result



#
# A dictionary mapping logger names to initialized logger objects
__loggers = dict()
__primary = 0

def get_logger(config_file, name = None, fallback = None):
    """
    This is the only interface of client code to this module.

    The rules are thus:

    * It is an error to supply both name and fallback.
    * The first call with fallback == None will set __primary to the name of
      the logger that is constructed.
    * If no name is given, use primary logger. If it does not exist, use
      cereconf.DEFAULT_LOGGER.
    * If name is given, always use that name (unless overridden by command
      line args).
    * get_logger(fallback='foo') will log to __primary, if it has been set,
      or to 'foo' otherwise.
    """
    global __primary

    # It's an error to supply both
    assert name is None or fallback is None, \
           "Either name or fallback must be None"

    # Let's see if there are command-line overrides
    clargs = fetch_logger_arguments()
    name = clargs.get("logger-name", name)

    # If no name is given (directly or via --logger-name), then
    if name is None:
        # ... if there is a primary logger, take it
        if __primary != 0:
            name = __primary
        # ... if there is no primary logger, use fallback
        else:
            name = fallback

    # No name is specified, no fallback is given and no primary has been
    # registered. Use default.
    if name is None:
        import cereconf
        name = cereconf.DEFAULT_LOGGER

    if __loggers.has_key(name):
        logger = __loggers[name]
    else:
        logger = initialize_logger(config_file, name)

    # The first call with fallback set to None sets the primary logger.
    if fallback is None and __primary == 0:
        __primary = name

    if "logger_level" in clargs:
        logger.setLevel(clargs["logger_level"])

    if name not in __loggers:
        __loggers[name] = logger
    
    return logger


def initialize_logger(config_file, name):
    if name not in __loggers:
        logger = parse_config(config_file, name)
        __loggers[ name ] = logger

    return __loggers[ name ]


def parse_config(filename, name):
    """
    Construct a logger called NAME from a configuration file FILENAME and
    return it.
    
    cerelog's configuration files are pretty close to that of the standard
    python logging module (i.e. the format is the same but the semantics of a
    few attributes have changed).

    We instantiate only the parts that are actually necessary (i.e. starting
    from a logger name, we instantiate every handler/formatter/parent
    'reachable' from the logger, but nothing more (logging.fileConfig
    initializes everything).
    """
    import ConfigParser

    parser = ConfigParser.ConfigParser()

    try:
        config_file = None
        config_file = open(filename, "r")
    except IOError, e:
        # If the file cannot be opened, you get a standard log
        pass

    try:
        if config_file:
            parser.readfp(config_file)

        #
        # Create the logger itself and everything that can be "reached" from
        # it.
        logger = _make_logger(parser, name)
    finally:
        if config_file: config_file.close()

    return logger


def _make_logger(parser, name):
    """
    Initialize the logger itself
    """

    section = "logger_" + name

    if not parser.has_section(section):
        print "No section found for logger", name

    logger_class = CerebrumLogger
    if parser.has_option(section, "class"):
        logger_class = locate_class(parser.get(section, "class"))

        # TBD: Check whether logger_class has inherited from CerebrumLogger?

    logger_level = _get_level(parser, section)

    logger_name = name
    # TBD: Do we allow a logger to have a different name than its section?
    # if parser.has_option(section, "name"):
    #    logger_name = parser.get(section, "name")

    logger = logger_class(logger_name, logger_level)

    # Now initialize all the necessary entities connected to LOGGER:
    #
    # Attach all (LOGGER's own) filters
    _make_filters(parser, section, logger)
 
    #
    # Attach all (LOGGER's own) handlers
    _make_handlers(parser, section, logger)

    #
    # Create all parents recursively
    _make_parents(parser, section, logger)

    return logger


def _make_filters(parser, owner_section, owner):
    """
    Attach all filters mentioned in the config file PARSER to OWNER. The
    filter names are extracted from the section OWNER_SECTION.
    """

    # By default, we pass a non-existing name
    filter_names = list(("",))
    if parser.has_option(owner_section, "filters"):
        raw = parser.get(owner_section, "filters")
        filter_names = [ name.strip() for name in string.split(raw, ",") ]

    for filter_name in filter_names:
        filter_obj = _make_filter(parser, filter_name)
        owner.addFilter(filter_obj)


def _make_filter(parser, filter_name):
    """
    Initialize handler HANDLER_NAME from the config file PARSER.
    """

    section = "filter_" + filter_name

    # Locate the class itself
    # 
    # Default filter does *nothing*
    filter_class = Filter
    if parser.has_option(section, "class"):
        filter_class = locate_class(parser.get(section, "class"))

    # A filter section is a usual collection of key=value pairs. Instead of
    # hammering a preset amount of keys, we pass the entire section as keyword
    # arguments to the filter in question. Some of the keys might be
    # superfluous, but that's ok, as long as the filter class does not insist
    # on interpreting every single key. It should just interpret the ones it
    # actually understands.
    #
    # NB! All the values are eval()'ed!
    if parser.has_section(section):
        arguments = dict([ (key, eval(parser.get(section, key, 1)))
                           for key in parser.options(section) ])
    else:
        arguments = dict()
    
    filter_obj = filter_class(**arguments)
    
    return filter_obj


__handlers = dict()

def _make_handlers(parser, section, owner):
    """
    Attach all handlers mentioned in the config file PARSER to LOGGER.
    """

    # By default, we pass a non-existing name
    handler_names = list(("",))
    if parser.has_option(section, "handlers"):
        raw = parser.get(section, "handlers")
        handler_names = [ name.strip() for name in string.split(raw, ",") ]

    for handler_name in handler_names:
        handler = _make_handler(parser, handler_name)
        owner.addHandler(handler)


def _make_handler(parser, handler_name):
    """
    Initialize handler HANDLER_NAME from the config file PARSER.
    """

    # TBD: Is this really a good idea? 
    if __handlers.has_key( handler_name ):
        return __handlers[ handler_name ]

    section = "handler_" + handler_name

    # Locate the class itself
    # 
    # TDB: This should perhaps be moved to a DEFAULT section, containing the
    # bare minimum that the logging framework can be initialized with.
    handler_class = StreamHandler
    if parser.has_option(section, "class"):
        handler_class = locate_class(parser.get(section, "class"))

    handler_level = _get_level(parser, section)

    formatter = _make_formatter(parser, section)

    # 
    # Now, we need to fetch the arguments to the handler. We try to allow as
    # many possible notations as possible. Unfortunately, this means that we
    # have to guess a bit when fetching the arguments. If no argument is
    # given, assume that the class' ctor is capable of processing an empty
    # argument list:

    arguments = list()
    if parser.has_option(section, "args"):
        raw = parser.get(section, "args")
        arguments = eval(raw)

    # We can allow either a single value, a sequence or a
    # dictionary. Those cases need to be tested separately
    if type(arguments) in (types.TupleType, types.ListType):
        handler = handler_class(*arguments)
    elif type(arguments) is types.DictType:
        handler = handler_class(**arguments)
    else:
        handler = handler_class(arguments)

    handler.setFormatter(formatter)
    handler.setLevel(handler_level)

    #
    # All filters for this handler
    _make_filters(parser, section, handler)

    __handlers[ handler_name ] = handler
    return __handlers[ handler_name ]
    

# __formatters = dict()

def _make_formatter(parser, handler_section):
    """
    Find (or create, if necessary) a formatter from the config file PARSER and
    section HANDLER_SECTION (it contains the formatter's name).
    """

    if not parser.has_option(handler_section, "formatter"):
        return None
    else:
        formatter_name = parser.get(handler_section, "formatter")

    # TBD: Do we really want singleton-like formatters?
    # if formatter_name in __formatters:
    #    return __formatters[ formatter_name ]

    section = "formatter_" + formatter_name

    #
    # It's a brand new formatter, we need to initialize it.
    # Locate the class itself
    formatter_class = Formatter
    if parser.has_option(section, "class"):
        formatter_class = locate_class(parser.get(section, "class"))

    #
    # FIXME: In 2.3, there is items()
    # FIXME: Do we really want an eval() here?
    #
    if parser.has_section(section):
        arguments = dict([ (key, eval(parser.get(section, key, 1)))
                           for key in parser.options(section) ])
    else:
        arguments = dict()
    
    formatter = formatter_class(**arguments)

    # __formatters[ formatter_name ] = formatter
    # return __formatters[ formatter_name ]
    return formatter
        


def _make_parents(parser, section, logger):
    """
    Create parents for LOGGER (information about the hierarchy is fetched from
    SECTION/PARSER)
    """

    if not parser.has_option(section, "parent"):
        return

    parent_name = string.strip(parser.get(section, "parent"))

    # Create the parent and establish parent-child link.
    parent = _make_logger(parser, parent_name)

    logger.parent = parent



def _get_level(parser, section):
    """
    This is a convenience function.
    """
    
    level = NOTSET
    if parser.has_option(section, "level"):
        level = globals()[(parser.get(section, "level"))]
        if type(level) is not types.IntType:
            raise TypeError, "level must be an integer"

    return level


def locate_class(class_name, *module_list):
    """
    Locate a class CLASS_NAME somewhere among modules MODULE_NAMES.
    
    This is a support function to help us write easier config files. We want
    this module to be able to look up classes in several plases (consider
    splitting the logging package into several 'submodules', without changing
    the config files).
    """

    import imp, sys

    # 
    # The simplest case -- the entity is in *THIS* file
    if class_name in globals():
        return globals()[class_name]

    for mnext in module_list:
        module = None

        if type(mnext) is types.ModuleType:
            module = mnext
        elif type(mnext) is types.StringType:
            if mnext in sys.modules:
                module = sys.modules[mnext]
            else:
                fp, pathname, description = imp.find_module(mnext)
                
                try:
                    module = imp.load_module(mnext, fp, pathname, description)
                finally:
                    if fp:
                        fp.close()
                        fp = None

        if hasattr(module, class_name):
            return getattr(module, class_name)

    raise ImportError, "Cannot locate class %s" % str(class_name)





# arch-tag: 9a057867-6fab-4b01-acdb-e515b600d225
