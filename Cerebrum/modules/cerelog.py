#!/usr/bin/env python2.2
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
This file is part of Cerebrum.

This module provides a logging framework for Cerebrum. The idea is based on
python2.3's logging module and a few nits of our own.

The logging framework behaviour is controlled by a suitable configuration
file, described at [1]. Although we use the very same format/options as the
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

--logger-name=<name>	-- specify a particular logger to initialize
--logger-level=<level>	-- specify a particular verbosity setting to use

References:
  [1] <URL: http://www.python.org/peps/pep-0282.html>
  [2] <URL: http://www.red-dove.com/python_logging.html>
"""

import cerebrum_path
import cereconf


import sys
if sys.version_info >= (2, 3):
    # The 'logging' module is bundled with Python 2.3 and newer.
    import logging
else:
    # Even though the 'logging' module might have been installed with
    # this older-than-2.3 Python, we'd rather not deal with troubles
    # from using too old versions of the module; use the version
    # bundled with Cerebrum.
    from Cerebrum.extlib import logging
# fi
import os.path
import os
import getopt
import string
import re





def debug(*rest):
    for item in rest:
        sys.stderr.write(str(item))
    # od

    sys.stderr.write('\n')
# end debug



def show_hierarchy(logger):
    """
    For debugging purposes only -- travel up the logger tree, and print
    information on the loggers
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
    """
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
    """
    Unfortunately getopt reacts adversely to unknown arguments. Thus we'd
    have to process command-line arguments ourselves.

    This is still a hack, though.
    """

    result = dict()
    args = sys.argv[:]
    filter_list = list()

    i = 0
    while i < len(args):
        for key in keys:
            if not args[i].startswith(key):
                continue
            # fi

            # We have an option. Two cases:
            # Case 1: key=value
            if args[i].find("=") != -1:
                result[key] = string.split(args[i], "=")[1]
                filter_list.append(i)
            # Case 2: key value. In this case we peek into the next argument
            elif i < len(args)-1:
                result[key] = args[i+1]
                filter_list.append(i); filter_list.append(i+1)
                i += 1
            # fi
        # od

        i += 1
    # od

    # We must make sure that every references to sys.argv already made
    # remains intact
    sys.argv[:] = list()
    for i in range(0,len(args)):
        if i not in filter_list:
            sys.argv.append(args[i])
        # fi
    # od

    return result
# end 



def process_arguments():
    """
    This function looks through command line arguments for parameters
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
    """
    Process the logging configuration, while respecting the command-line
    arguments.

    We try to mimic logging.fileConfig's behaviour as close as possible.
    """

    import ConfigParser

    parser = ConfigParser.ConfigParser()
    if hasattr(parser, "readfp") and hasattr(fname, "read"):
        parser.readfp(fname)
    else:
        parser.read(fname)
    # fi

    # Register all formatters
    initialize_formatters(parser)

    #
    # Select the specific logger we want 
    logger_list = string.split(parser.get("loggers", "keys"), ",")
    if logger_name not in logger_list:
        # FIXME: WTF do we do here -- a non-existing logger has been
        # specified. Fall back to root?
        debug("Unknown logger specified ", logger_name)
        logger_name = "root"
    # fi

    # From here on we initialize a single logger (and all its ancestors),
    # identified by LOGGER_NAME
    logger = initialize_logger(logger_name, logger_level, parser)

    # Now we *must* create all parents on the way up toward the root logger.
    # The problem with the logging module is that it mixes up parents pretty
    # badly. While creating a new logger, if its parents have not been
    # called getLogger on, then a logger gets the default parent -- logger
    # root. I cannot fathom how this behaviour might be considered correct.
    #
    # 
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
        # od


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
            # fi
        # fi
    # fi

    return logger
# end process_config



def initialize_logger(name, level, config):
    """
    This function creates and initializes a new logger NAME with config
    information specified in CONFIG.

    LEVEL overrides whatever level CONFIG specifies.

    Furthermore, this function registers the new logger inside the logging
    framework (we need this to keep track of parent-child relationships).

    This function returns the new logger
    """

    section_name = "logger_" + name
    qualname = config.get(section_name, "qualname")
    options = config.options(section_name)
    if "propagate" in options:
        propagate = config.getint(section_name, "propagate")
    else:
        propagate = 1
    # fi

    # logging.getLogger does a number of fancy things. If a name does not
    # exist, a suitable logger instance is created anew.
    logger = logging.getLogger(qualname)

    # FIXME: we need to clarify the domain of LEVEL (especially
    # command-line)
    # 
    # if there is a command line level override, use it
    if level is not None:
        logger.setLevel(logging.getLevelName(level))
    # ... otherwise use the level specified in the config file, it it exists
    elif "level" in options:
        logger_level = config.get(section_name, "level")
        logger.setLevel(logging.getLevelName(logger_level))
    # fi

    # FIXME: is this really necessary? (stolen from logging)
    for handler in logger.handlers:
        logger.removeHandler(handler)
    # od

    logger.propagate = propagate
    logger.disabled = 0
    handler_names = config.get(section_name, "handlers")
    if handler_names:
        for handler_name in string.split(handler_names, ","):
            logger.addHandler(initialize_handler(handler_name,
                                                 config))
        # od
    else:
        debug("No handlers specified for %s. Does this make sense?" %
              logger.name)
    # fi

    # Force propagate to 0 for root loggers
    if logger.name == "root":
        logger.propagate = 0
    # fi

    return logger
# end initialize_logger



__handlers = dict()
def initialize_handler(name, config):
    """
    This function creates and initializes a handler NAME from an ini-file
    represented by CONFIG.

    If a handler NAME already exists, it is returned without any
    re-initialization.
    """

    if __handlers.has_key(name):
        return __handlers[name]
    # fi

    section_name = "handler_" + name
    klass = config.get(section_name, "class")
    options = config.options(section_name)
    if "formatter" in options:
        formatter = config.get(section_name, "formatter")
    else:
        formatter = ""
    # fi

    # KLASS *must* be an attribute in the logging module.
    # It's a bit safer doing a [], rather than eval
    namespace = logging.__dict__.copy()
    namespace.update(globals())
    klass = namespace[klass]
    arguments = config.get(section_name, "args")
    arguments = eval(arguments, namespace)

    handler = apply(klass, arguments)

    # If there is a level specification in the ini-file, use it. 
    if "level" in options:
        level = config.get(section_name, "level")
    # ... otherwise, we get a handler than never logs.
    else:
        level = None
    # fi

    handler.setLevel(logging.getLevelName(level))

    if formatter:
        handler.setFormatter(__formatters[formatter])
    # fi

    # logging brain damage :(
    if klass == logging.FileHandler:
        maxsize = 0
        if "maxsize" in options:
            maxsize = config.getint(section_name, "maxsize")
        # fi
        if maxsize:
            backcount = 0
            if "backcount" in options:
                backcount = config.getint(section_name, "backcount")
            # fi

            handler.setRollover(maxsize, backcount)
        # fi
        
    elif klass == logging.MemoryHandler:
        raise ValueError, "Aiee! MemoryHandlers not supported yet"
    # fi

    __handlers[name] = handler
    return handler
# end initialize_handler



__formatters = dict()
def initialize_formatters(config):
    """
    This function initializes all formatters specified in CONFIG
    (initialization of useless formatters is harmless)
    """
    global __formatters

    formatter_keys = config.get("formatters", "keys")
    if formatter_keys:
        formatter_keys = string.split(formatter_keys, ",")
        for name in formatter_keys:
            section_name = "formatter_" + name
            options = config.options(section_name)

            format = datefmt = None
            if "format" in options:
                format = config.get(section_name, "format", 1)
            # fi
            if "datefmt" in options:
                datefmt = config.get(section_name, "datefmt", 1)
            # fi

            f = logging.Formatter(format, datefmt)
            __formatters[name] = f
        # od
    # fi
# end initialize_formatters



__logger_instance = None
def get_logger(config_file, logger_name = None):
    """
    Initialize (if necessary) and return the logger
    
    NB! get_logger will actually initialize anything only once. All
    subsequent calls from the same process (thread?) will return a reference
    to the same logger *regardless* of the LOGGER_NAME specified (this
    behavior is intentional).
    """
    global __logger_instance

    if __logger_instance is None:
        __logger_instance = cerelog_init(config_file, logger_name)
    # fi

    return __logger_instance
# end get_logger



def cerelog_init(config_file, name):
    """
    Run-once method for initializing everything in cerelog
    """

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



class CerebrumLogger(logging.Logger):
    """
    This is the logger class used by the Cerebrum framework.
    """

    def __init__(self, name, level=logging.ALL):
        logging.Logger.__init__(self, name, level)
    # end __init__


    def __cerebrum_debug(self, level, msg, *args, **kwargs):
        if self.manager.disable >= level:
            return
        # fi

        if self.isEnabledFor(level):
            apply(self._log, (level, msg, args), kwargs)
        # fi
    # end __cerebrum_debug


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
    
# end CerebrumLogger





class CerebrumRotatingHandler(logging.FileHandler, object):
    """
    Cerebrum's own rotating handler. 
    """

    def __init__(self, logdir, mode="a", maxBytes=0, backupCount=0):
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
                if e.errno != 17:
                    # the error is not 'file exists', which we ignore
                    raise e
        # fi

        self.filename = os.path.join(self.logdir,
                                     self.directory,
                                     self.basename)
        super(CerebrumRotatingHandler, self).__init__(self.filename, mode)

        self.maxBytes = maxBytes
        self.backupCount = backupCount

        # FIXME: This can't be right -- changing mode *after* it has been set?
        self.mode = mode
        if maxBytes > 0:
            self.mode = "a+"
        # fi
    # end __init__



    def prepareMessage(self, record):
        """
        This method makes writing subclasses doing something with messages
        easier.
        """

        # Standard processing
        return self.format(record)
    # end prepareMessage



    def emit(self, record):
        """
        Emit a record.

        Output the record to the file, catering for rollover as described
        in setRollover().
        """

        msg = self.prepareMessage(record)
        if self.maxBytes > 0:                   # are we rolling over?
            self.stream.seek(0, 2)  #due to non-posix-compliant Windows feature
            if self.stream.tell() + len(msg) >= self.maxBytes:
                self.doRollover()
            # fi
        # fi

        try:
            self.stream.write(msg)
            self.stream.write("\n")
            self.stream.flush()
        except IOError:
            # Let us not make the same mistake as python's logging.py - they
            # call handleError in every case, and the default action in
            # handleError is to ignore everything. 
            self.handleError()
        # yrt
    # end emit
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
                 permissions, substitute, replacement):
        """
        LOGDIR       -- which directory the log goes to
        MAXBYTES     -- maximum file size before it is rotated (0 means no
                        rotation)
        BACKUPCOUNTS -- number of rotated files
        PERMISSIONS  -- UNIX-style permission number for the log file
        SUBSTITUTE   -- regular expression to perform substitution on
        REPLACEMENT  -- ... what to replace SUBSTITUTE with.
        """

        super(self.__class__, self).__init__(logdir, "a",
                                             maxBytes, backupCount)

        self.substitution = re.compile(substitute)
        self.replacement = replacement
        self.permissions = permissions

        print "maxBytes: ", maxBytes
        print "backup: ", backupCount

        # Force our permissions
        os.chmod(self.filename, permissions)
    # end __init__



    def doRollover(self):
        super(self.__class__, self).doRollover()
        os.chmod(self.filename, self.permissions)
    # end doRollover



    def prepareMessage(self, record):
        """
        We make our regexp substitution in this method.
        """

        # First, we apply all the formatters (time, date and the like)
        # FIXME: perhaps we should not touch anything else than the message
        # and the arguments? regexps could change the information that
        # formatters merge in.
        msg = self.format(record)
        return self.substitution.sub(self.replacement, msg)
    # end prepareMessage

# end CerebrumSubstituteHandler
        
    
