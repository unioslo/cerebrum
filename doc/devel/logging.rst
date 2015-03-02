==============================
Logging framework in Cerebrum
==============================

.. contents:: Table of contents
.. section-numbering::


Introduction
-------------
This documents describes the logging framework used in the Cerebrum project
[#cerebrum]_.

The logging framework is based on python's ``logging`` module
[#python-logging]_ that appeared in python 2.3. Partially for historical
reasons (Cerebrum is older than python 2.3), partially for functional reasons
(more on this later), a custom-made logger has been chosen for Cerebrum. Most
of the ``logging`` module's interface has been kept as well as the overall
architecture. However, some of the semantics have been altered.

Presently, there are no less than 3 different loggers in use in UiO "branch"
of Cerebrum, which is clearly unacceptable. The ideal goal is to converge to a
single logger which would suit all of our needs. The loggers are:

  * ``Cerebrum/modules/cerelog.py:CerebrumLogger``. We will focus on extending
    this logger to merge the needed functionality from elsewhere.
  * ``Cerebrum/modules/no/uio/AutoStud/Utils.py:ProgressReporter``. The
    primary "raison d'être" for this logger is to support a different
    initialization mode (one logfile per job run, regardless of the log
    size/time span) and indentation support.
  * ``Cerebrum/modules/no/uio/printer_quota/bofhd_pq_utils.py:SimpleLogger``. 
    This logger is a work-around for the fact that there can be one instance
    of ``CerebrumLogger`` per process only. 


Rationale
----------
The goal for the Cerebrum logging framework was to make a logger available to
an "average" job with a minimal setup required. In the general case, only two
statements are necessary to fetch a ready-to-use logger. The idea is for the
scripts never to meddle with logger settings, but to simply use the logger and
rely on a set of predefined loggers in the configuration file. 

So, why is there a custom framework for logging, when python offers a logging
module?

  * Only one logger type is initialized. It is a subclass of
    ``CerebrumLogger``. We may have to relax this restriction at some point,
    given certain provisions. Python's ``logging`` does not allow specifying a
    custom logger class (or Formatter class, for that matter).
  * Only the loggers/handlers/formatters explicitly asked for are
    initialized. ``logging.py`` instantiates *all* loggers/handlers/formatters
    found in the configuration file. It is a bit of a chore, given cerebrum's
    ``logging.ini`` configuration.
  * Python's ``logging`` makes a few peculiar decisions regarding logger
    classes in the logger hierarchy. This basically forces us to initialize
    the logger hierarchy our way to force proper child-parent relations
    between loggers.
  * Our loggers understand indentation commands. Although this kind of
    communication is against "the spirit" of the logging framework, it has
    been deemed necessary to improve log readability for humans.
  * Cerebrum logger framework understands certain command line arguments. The
    arguments are processed destructively (i.e. calling ``cerelog_init`` will
    process the arguments in ``sys.argv`` destructively)


Issues
-------
There arequite a few issues outstanding with regard to the logging
framework. In no particular order:

  * Lazy file opening. Opening log files needs to be delayed until there is an
    actual message that is to be issued. The rationale for this is that if the
    user running the script lacks the permission to write to a log file, the
    user is greeted with a traceback even when using options like ``--help``.

    We cannot easily hook onto the existing ``FileHandler`` and force it to
    delay file opening. It is easiest to write our own handler,
    ``DelayedFileHandler``, which would behave just like a ``FileHandler``,
    except that the file will not be opened unless there is a message that
    must be output there.

  * Unicode treatment. It should be possible to pass unicode objects directly
    to any logger and it should be possible to write it out as is. The
    rationale for this is that the unicode objects occur quite often in
    Cerebrum and we should be able to print them out without having to think
    about conversions and what not. The problem is that unicode code points
    have to be encoded before they can be written out.

    The solution: 

      * ``StreamHandler`` already handles ``UnicodeError`` internally, so
        nothing needs be done.
      * ``FileHandler`` and all its subclasses have an extra argument
        ``encoding`` which determines the charset to which unicodes should be
        converted. The conversion happens via the ``codecs`` python module. 
      * We do not care about all the other handlers. 

    It's probably easiest to encode all unicode objects to utf-8 (this is
    guaranteed not to fail). The ``encoding`` is specified along with other
    arguments in ``logging.ini``.

  * Indentation. Occasionally it may be desirable to indent some of the
    messages to structure the logs in a manner more suitable for human
    consumption (specifically, ``process_students``). One solution has been
    presented by runefro in an e-mail to ``cerebrum-developers``
    "IndentingFormatter for cerelog".

    An ``IndentingFormatter`` and ``IndentingHandler`` have been incorporated
    into ``cerelog.py`` 1.21. All formatters are instances of
    ``IndentingFormatter`` and can typeset the ``"%(indent)s"`` formatting
    directive (this is an extension of [#python-logging]_). Our loggers simply
    pass the ``set_indent`` down to handlers and they, in turn, to
    formatters. For now the indentation prefix is one space character (this
    will be configurable in later versions). I.e. ``set_indent(4)`` will
    indent the messages by four spaces. The ``"%(indent)s"`` formatting
    directive decides where the indent is merged. Thus, a formatter section
    like this: ::

      [formatter_form_indent]
      format=%(asctime)s %(indent)s%(level)s%(message)s
      datefmt=%F %T
   
    ... would yield a log file that looks like this: ::

      2007-02-14 15:15:14 INFO hello
      2007-02-14 15:21:26     DEBUG indented
      2007-02-14 15:21:49          DEBUG even more indented

    All handlers initialized through cerelog are extended with a
    ``IndentingHandler`` mixin and accept ``set_indent()`` calls. All this
    happens transparently and does not affect the existing code base that
    makes no use of the indenting features.

    It should be noted that Vinay Sajip (creator of python's ``logging``
    framework) expressed his concerns regarding this approach to
    indentation. Also, as of python 2.5, there is a possibility of passing
    *any* number of extra arguments to logger calls. Therefore, we could
    implement indentation in python 2.5 like this: ::

      logger.debug("foo")
      logger.debug("this is indented", extra = {"indent": " "*4})
      logger.debug("this is NOT indented")

In addition to the issues above (which have been solved), the following issues
have been discussed but remain unresolved:

  * User-friendliness in case of various failures within the cerelog
    framework. E.g. opening a file for writing where a user does not have
    write access should perhaps not result in throwing an ``IOError`` in
    user's face, but rather hidden behind a single line like "could not open
    log file <something>". This has been discussed in an e-mail thread
    "cerelog og --opsjoner" sent to ``cerebrum-developers``.

  * Non-destructive argument processing. Right now, fetching a logger through
    Cerebrum changes the argument list (``sys.argv``) destructively. This
    means that essentially only the first logger can process its command-line
    arguments without further caching voodoo. This is a shame. (The argument
    mangling happens in a non thread-safe manner too).

    The overall nicest solution is to process command line arguments
    differently than ``getopt/optparse`` do, but this requires a huge code
    change (every file using logging and ``getopt/optparse``).

  * Inter-module cooperation. Several modules within one script may request
    their own loggers. This has interesting side-effects (modules may request
    loggers before the ``main()``  script and may instantiate a wrong kind of
    logger wrt the ``main()`` script). kjetilho, ivr and hmeland have
    discussed a possible remedy, but the suggestion have not been realized as
    of yet (2007-02-19).

  * ``cerelog.py`` is not threadsafe. There are a number of places within the
    initialization code that make thread unsafe global structure updates. This
    should be fixed before we can safely used cerelog in multithreaded
    environment.

All these issues have been acknowledged, but the resolving them has not been a
prioritized task.


Files
------
The files of consequence for the logging framework are:

  =====================================	=====================================
  ``Cerebrum/modules/cerelog.py``       Cerebrum-specific extensions to the
                                        logging framework.
  ``spine/ceresync/cerelog.py``		NTNU's own extensions
  ``Cerebrum/Utils.py``			``Factory`` interface to logging. This
					is the interface that the typical user
					would see.
  ``Cerebrum/design/cereconf.py``	``cereconf.LOGGING_CONFIGFILE`` tells
					where the configuration file is to be
					found.
  ``logging.ini``			Configuration file.
  =====================================	=====================================


Configuration
--------------
The behaviour of the Cerebrum logger is controlled by a configuration
file. The configuration filename is registered in
``cereconf.LOGGING_CONFIGFILE``. ``Factory.get_logger`` uses this variable to
get hold of the configuration file. ``Factory.get_logger`` is also *the only*
interface to obtaining logger objects within Cerebrum.

The overall format of the config file itself is described in
[#logging-config]_. The simplest useful configuration would be one logger, one
handler and one formatter that spit everything to the console: ::

   [logger_root]
   level=WARN
   qualname=root
   handlers=hand_root_warn

   [handler_hand_root_warn]
   class=StreamHandler
   level=NOTSET
   formatter=form_console
   args=(sys.stdout,)

   [formatter_form_console]
   format=%(levelname)s %(message)s

Python's ``logging`` module requires additional sections with ``keys=``
specifying all loggers, handlers and formatters. We do not. Also, the
arguments (e.g. in handler sections) are passed to ``eval()``, so be careful
what you put there, since the code will be executed with the privileges of the
process that asks for a logger.


For the impatient
------------------
One of the first statements of your program: ::

    from Cerebrum.Utils import Factory
    logger = Factory.get_logger("console")
    logger.debug("hi!")

Since ``get_logger()`` modifies ``sys.argv`` destructively, you should
probably instantiate a logger *before* parsing the program arguments yourself,
unless your argument parsing code is prepared to deal with logger-related
options.


Migrating existing code base
-----------------------------
Migrating the existing code base would have to happen in several steps: 

  #. Stop job_runner (bofhd can continue functioning, but it'd have to be
     restarted later)
  #. Upgrade ``Cerebrum/modules/cerelog.py``,
     ``Cerebrum/modules/no/uio/AutoStud/Util.py``, ``Cerebrum/Utils.py``,
     ``contrib/no/uio/process_students.py``.
  #. Fix configuration files ``cereconf.py`` and ``logging.ini``. 
  #. kill bofhd, restart job_runner.

The pq-bofhd logger cannot be removed right now, since moving to several
loggers per process idea has not been fully explored yet. To implement the
changes, ``bofhd`` would need a restart. ``job_runner`` should also be paused
right before the new ``logging.ini``, ``cerelog.py`` and other files are
installed.

``process_students`` will log a bit differently now:
"/cerebrum/var/log/cerebrum/" + "log" + timestamp (this way process_student's
logs will share the directory with all other loggers; we won't have to hunt
around for them). There is exactly one log file per job run.

Incidentally, ``cereconf.AUTOADMIN_LOG_DIR`` cannot be removed yet. pq-bofhd
logger uses it, as well as ``process_student.py`` for some temporary
file info.


References
-----------
.. [#logging-pep] PEP 282 "A logging system". 
                  <http://www.python.org/dev/peps/pep-0282/>
.. [#vinay-doc] Vinay Sajip's logging documentation 
                  <http://www.red-dove.com/python_logging.html>
.. [#cerebrum] Cerebrum project. <http://cerebrum.sf.net/>.
.. [#python-logging] <http://docs.python.org/lib/module-logging.html>.
.. [#logging-config] <http://docs.python.org/lib/logging-config-fileformat.html>.
