# encoding: utf-8
""" Log configuration.

Note that we are talking about two *types* of configuration here. 'logging' and
'logger'.

Logging
-------
The 'logging' config is defined in the cerebrum config directory (typically
<prefix>/etc/cerebrum/config), in a 'logging' file.

This file defines the behaviour of this logging sub-package. I.e.:

- Should unhandled exceptions be logged?
- Should warnings be logged?
- Where are the 'logger' configs placed?
- Where should log files be placed?

Logger
------
The 'logger' configs configures the logger hierarchy. These log files follows
the formats of `logging.config`.

The idea here is to make it possible to include a series of logger config
files.  Different scripts will have different logging needs, so we want to make
it possible to apply different setups to different scripts.

In addition, devs might want to use their own setups, e.g. log everyting to
stdout/stderr with their own format.

The design here is that we have a config dir with log configs. The name of the
config file corresponds to the logger name (--logger-name argument).

"""
from __future__ import absolute_import, unicode_literals

import logging
import logging.config
import os
import sys
from collections import defaultdict
from Cerebrum.config import loader
from Cerebrum.config.configuration import (ConfigDescriptor,
                                           Configuration,
                                           Namespace)
from Cerebrum.config.settings import String, Boolean, Iterable, Choice


DEFAULT_LOGDIR = os.path.join(sys.prefix, 'var', 'log', 'cerebrum')
DEFAULT_CONFDIR = os.path.join(sys.prefix, 'etc', 'cerebrum', 'logging')
DEFAULT_LOGGING_CONFIG = 'logging'

DEFAULT_CAPTURE_EXC = True
DEFAULT_CAPTURE_WARN = True
DEFAULT_LEVEL_EXC = 'ERROR'
DEFAULT_LEVEL_WARN = 'WARNING'

# Note: This will not include custom levels
LOGLEVELS = {level for level in logging._levelNames
             if not isinstance(level, int)}

logger = logging.getLogger(__name__)


class WarningFilterItem(String):
    """ A warning filter setting.

    Strings must follow the following syntax:

        action[:[message][:[category][:[module][:[lineno]]]]]

    Examples:

        ignore
        once::::
        always::DeprecationWarning:Cerebrum.modules.cerelog:27
        error:Some warning message:Warning:
    """

    FIELDS = (
        ('action', lambda v: v in ["error", "ignore", "always", "default",
                                   "module", "once"]),
        ('message', lambda v: True),
        ('category', lambda v: True),
        ('module', lambda v: True),
        ('lineno', lambda v: not v or v.isdigit()))

    def __init__(self):
        # disallow arguments
        super(WarningFilterItem, self).__init__()

    def validate(self, value):
        fields = value.split(':')

        if len(fields) > len(self.FIELDS):
            # Too many filter fields, e.g. 'once:msg:cat:mod:line:whats this?'
            raise ValueError("Invalid filter format, must be "
                             "'action[:message[:category[:module[:lineno]]]]'")

        # Check each field according to 'checks':
        for i, field in enumerate(fields):
            field_name, field_check = self.FIELDS[i]
            if not field_check(field):
                raise ValueError(
                    "Invalid filter {0} ({1})".format(field_name, repr(field)))


class WarningsConfig(Configuration):
    """ Configuration for the logwarn module. """
    enable = ConfigDescriptor(
        Boolean,
        default=DEFAULT_CAPTURE_WARN,
        doc="If the logger should capture warnings")

    level = ConfigDescriptor(
        Choice,
        choices=LOGLEVELS,
        default=DEFAULT_LEVEL_WARN,
        doc="Which log level to log warnings with")

    filters = ConfigDescriptor(
        Iterable,
        template=WarningFilterItem(),
        default=[
            'always:',
            'once::DeprecationWarning',
            'once::PendingDeprecationWarning',
            'once::ImportWarning',
            'once::BytesWarning',
        ],
        doc="Ordered list of warning filters")


class ExceptionsConfig(Configuration):
    """ Configuration for the logexc module. """
    enable = ConfigDescriptor(
        Boolean,
        default=DEFAULT_CAPTURE_EXC,
        doc="If the logger should capture unhandled exceptions")

    level = ConfigDescriptor(
        Choice,
        choices=LOGLEVELS,
        default=DEFAULT_LEVEL_EXC,
        doc="Which log level to log unhandled exceptions with")


class LoggingEnvironment(Configuration):
    """ Configuration of the logging environment. """

    root_dir = ConfigDescriptor(
        String,
        default=DEFAULT_LOGDIR,
        doc="Root directory for log files")

    conf_dir = ConfigDescriptor(
        String,
        default=DEFAULT_CONFDIR,
        doc="Directory with log configurations")

    exceptions = ConfigDescriptor(
        Namespace,
        config=ExceptionsConfig)

    warnings = ConfigDescriptor(
        Namespace,
        config=WarningsConfig)


def get_config(config_file=None, namespace=DEFAULT_LOGGING_CONFIG):
    """ Autoload a config.

    :param str config_file:
        Read the logging configuration from this file.
    :param str namespace:
        If no `config_file` is given, look for a config with this basename in
        the configuration directory.
    """
    config = LoggingEnvironment()

    if config_file:
        config.load_dict(loader.read_config(config_file))
    else:
        loader.read(config, root_ns=namespace)
    return config


def iter_logging_configs(directory, *basenames):
    """ Iterate over matching basenames in directory. """
    # TODO: This is horrible. We really only want two configs: one common
    # (typically logging.ini or logging.<whatever> and one custom
    # (--logger-name)
    sort_pri = defaultdict(
        lambda: len(basenames),
        ((b, i) for i, b in enumerate(basenames)))

    def _file_sorter(a, b):
        base_a, ext_a = os.path.splitext(os.path.basename(a))
        base_b, ext_b = os.path.splitext(os.path.basename(b))
        return (
            # desired basename before other basenames
            cmp(sort_pri[base_a], sort_pri[base_b]) or
            # or if same basename, put .ini-files last
            #   int(base_a == base_b and ext_a == '.ini') * 1 or
            #   int(base_a == base_b and ext_b == '.ini') * -1 or
            # or just sort by filename
            cmp(a, b))

    # A set of loaded config basenames
    # Iterate over matching files in the config directory
    try:
        for filename in sorted(os.listdir(directory),
                               cmp=_file_sorter):
            if os.path.splitext(os.path.basename(filename))[0] in basenames:
                yield os.path.join(directory, filename)
    except OSError:
        # Directory does not exist, no files to iterate over
        return


def configure_logging(filename, disable_existing_loggers=None):
    """ Configure loggers. """
    base, ext = os.path.splitext(filename)
    if ext == '.ini':
        # TODO: Should we even allow using fileConfig
        logging.config.fileConfig(
            filename,
            disable_existing_loggers=bool(disable_existing_loggers))
    else:
        conf_dict = loader.read_config(filename)
        conf_dict.setdefault('version', 1)
        if disable_existing_loggers is None:
            disable_existing_loggers = conf_dict.setdefault(
                'disable_existing_loggers',
                bool(disable_existing_loggers))
        else:
            conf_dict['disable_existing_loggers'] = disable_existing_loggers
        logging.config.dictConfig(conf_dict)


def setup_logging(config, config_name, loglevel, disable_existing=False):
    """ (re)configures logging. """
    # TODO: this needs some improvements
    config_files = []
    # TODO: Should we do something drastic if config_name does not exist?
    for filename in iter_logging_configs(config.conf_dir,
                                         'logging',
                                         config_name):
        # TODO: Should we try to join the configs *before* we apply them?
        #       That would allow one config to refer to common elements in
        #       another config... We should probably disallow *.ini fileConfig
        #       then, since it's not compatible with dictConfig...
        configure_logging(filename, disable_existing_loggers=disable_existing)
        # When loading multiple configs, we should only disable existing on the
        # first one. There's still a chance of configs to override this
        # behaviour though.
        disable_existing = None

        config_files.append(filename)

    if not config_files:
        if loglevel is None:
            logging.basicConfig()
        else:
            logging.basicConfig(level=loglevel)
        logger.warn(
            "No logger config '{0}' in config dir {1}".format(config_name,
                                                              config.conf_dir))
    else:
        for c in config_files:
            logger.debug("Loaded logger config '{0}'".format(c))


def setup_excepthook(exception_config):
    """ Configures exception capture.

    :param ExceptionsConfig exception_config: configuration.
    """
    from . import logexc
    exchook = logexc.ExceptionLoggerHook(exception_config.level)
    if exception_config.enable:
        logexc.set_exception_hook(exchook)
    logger.debug("Exceptions config {!r}".format(exception_config))


def setup_warnings(warn_config):
    """ Configures warnings capture and filter.

    :param WarningsConfig warn_config: configuration.
    """
    from . import logwarn
    # TODO: The filters aren't really log-related. Should this be elsewhere? If
    # so, we need some global init for Cerebrum.
    logwarn.filters.set_filters(warn_config.filters)
    showwarning = logwarn.WarningsLogger(warn_config.level)
    if warn_config.enable:
        logwarn.set_showwarning(showwarning)
    logger.debug("Warnings config {!r}".format(warn_config))


def configure(config,
              logger_name,
              logger_level=None):

    setup_logging(config, logger_name, logger_level)
    setup_excepthook(config.exceptions)
    setup_warnings(config.warnings)
    logger.debug("Config logs={0.root_dir!s} loggers={0.conf_dir!s}".format(
        config))


if __name__ == '__main__':
    try:
        from pprintpp import pprint
    except ImportError:
        from pprint import pprint
    config = get_config()
    pprint(config.dump_dict())
