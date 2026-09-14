# -*- coding: utf-8 -*-
#
# Copyright 2017-2026 University of Oslo, Norway
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
Log configuration.

Logging i Cerebrum uses two distinct types of config files: the *logenv* config
and the *preset* config.  This module defines these config file formats and
deals with finding and reading config files.

Logenv
-------
The *logenv* logging environment config should be placed in the cerebrum config
directory (typically <prefix>/etc/cerebrum/config), in a 'logenv.yaml' or
'logenv.json' file.

This is a config file used by all entry points in Cerebrum that uses
logging/logutils, and defines the behaviour of the logutils sub-modules:

- Should unhandled exceptions be logged?
- Should warnings be logged?
- Where are the log presets found?
- Where should log files generally be placed?

Preset
-------
The *preset* configs configures the actual python logger hierarchy, along with
formatters, handlers, and anything else that the standard python logging
configuration allows for.  These log files follows the format of
:mod:`logging.config`.

All scripts define a default preset when configuring loggers, but this can
usually be overridden by cli options (``--logger-name``).  The first matching
preset from the logger preset search path (given in the *logenv* config) is
applied when configuring loggers.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import logging
import logging.config
import os
import sys

import six

import cereconf
from Cerebrum.config import loader
from Cerebrum.config import parsers
from Cerebrum.config.configuration import (ConfigDescriptor,
                                           Configuration,
                                           Namespace)
from Cerebrum.config.settings import String, Boolean, Iterable, Choice


# Make it possible to override sys.prefix for configuration path purposes
_sys_prefix = os.getenv('CEREBRUM_SYSTEM_PREFIX', sys.prefix)

DEFAULT_LOGDIR = os.path.join(
    _sys_prefix,
    'var/log/cerebrum',
)
"""
Default directory for log files.

This is ``<sys.prefix>/var/log/cerebrum/`` by default, but ``sys.prefix`` can
be replaced with the ``$CEREBRUM_SYSTEM_PREFIX`` environment variable.
"""

DEFAULT_PRESET_DIR = os.path.join(
    _sys_prefix,
    'etc/cerebrum/logger-presets',
)
"""
Default location of logger presets.

This is ``<sys.prefix>/etc/cerebrum/logger-presets/`` by default, but
``sys.prefix`` can be replaced with the ``$CEREBRUM_SYSTEM_PREFIX`` environment
variable.
"""

# Make it possible to override DEFAULT_LOGGING_CONFIG
DEFAULT_LOGGING_CONFIG = os.getenv('CEREBRUM_DEFAULT_LOGGING_CONFIG', 'logenv')
"""
Name of the *logenv* config file.

May be overridden by a ``$CEREBRUM_DEFAULT_LOGGING_CONFIG`` environment
variable.
"""

DEFAULT_CAPTURE_EXC = True
""" Default setting for exceptions capture. """

DEFAULT_CAPTURE_WARN = True
""" Default setting for warnings capture. """

DEFAULT_LEVEL_EXC = 'ERROR'
""" Default log level for captured exceptions. """

DEFAULT_LEVEL_WARN = 'WARNING'
""" Default log level for captured warnings. """

DEFAULT_SENTRY_ENABLE = False
""" Default setting for Sentry. """


# Note: This will not include custom levels
if six.PY2:
    LOGLEVELS = {level for level in logging._levelNames
                 if not isinstance(level, int)}
else:
    LOGLEVELS = set(logging._nameToLevel)

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
        ('lineno', lambda v: not v or v.isdigit()),
    )

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
        doc="If the logger should capture warnings",
    )

    level = ConfigDescriptor(
        Choice,
        choices=LOGLEVELS,
        default=DEFAULT_LEVEL_WARN,
        doc="Which log level to log warnings with",
    )

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
        doc="Ordered list of warning filters",
    )


class ExceptionsConfig(Configuration):
    """ Configuration for the logexc module. """

    enable = ConfigDescriptor(
        Boolean,
        default=DEFAULT_CAPTURE_EXC,
        doc="If the logger should capture unhandled exceptions",
    )

    level = ConfigDescriptor(
        Choice,
        choices=LOGLEVELS,
        default=DEFAULT_LEVEL_EXC,
        doc="Which log level to log unhandled exceptions with",
    )


class SentryConfig(Configuration):
    """ Configuration for the sentry-sdk logging module. """

    enable = ConfigDescriptor(
        Boolean,
        default=DEFAULT_SENTRY_ENABLE,
        doc="If errors should be sent to sentry",
    )

    dsn = ConfigDescriptor(
        String,
        default="",
        doc=(
            "Which Sentry project to use. "
            "Required if sentry logging is enabled."
        ),
    )

    environment = ConfigDescriptor(
        String,
        default=getattr(cereconf, "ENVIRONMENT", None),
        doc="Override the Cerebrum environment in Sentry",
    )


class LoggerConfig(Configuration):
    """ Configures logger preset processing. """

    logdir = ConfigDescriptor(
        String,
        default=DEFAULT_LOGDIR,
        doc="Root directory for log files (cerebrum handlers only)",
    )

    presets = ConfigDescriptor(
        Iterable,
        template=String(),
        default=[DEFAULT_PRESET_DIR],
        doc="Directories with logger preset configurations",
    )

    merge = ConfigDescriptor(
        Boolean,
        default=False,
        doc=(
            "Merge logger presets before applying"
            " (ini-style configs not supported)"
        ),
    )

    common_preset = ConfigDescriptor(
        String,
        default='',
        doc=(
            "Common logger preset."
            " This named preset will always be applied, if available."
            " Set to an empty string to disable."
        ),
    )

    require_preset = ConfigDescriptor(
        Boolean,
        default=False,
        doc="Fail if the named logger configuration file is missing.",
    )


class LoggingEnvironment(Configuration):
    """ Configuration of the logging environment. """

    logging = ConfigDescriptor(
        Namespace,
        config=LoggerConfig,
    )

    exceptions = ConfigDescriptor(
        Namespace,
        config=ExceptionsConfig,
    )

    warnings = ConfigDescriptor(
        Namespace,
        config=WarningsConfig,
    )

    sentry = ConfigDescriptor(
        Namespace,
        config=SentryConfig,
    )


def get_config(config_file=None, namespace=DEFAULT_LOGGING_CONFIG):
    """ Autoload a LoggingEnvironment config file.

    :param str config_file:
        Read the logging configuration from this file.
    :param str namespace:
        If no `config_file` is given, look for a config with this basename in
        the configuration directory.

    :return LoggingEnvironment:
        Returns a configuration object.
    """
    config = LoggingEnvironment()

    if config_file:
        config.load_dict(loader.read_config(config_file))
    else:
        loader.read(config, root_ns=namespace)
    return config


def iter_presets(directory, rootnames, extensions):
    """
    Iterate over matching preset files in directory.

    Iterates over preset files in *directory* that matches one of the given
    *rootnames*, and one of the given *extensions*.

    Files will be returned in the same order as given in *rootnames* and
    *extensions*.  The results are *primarily* sorted by extension, then the
    rootname, then the full filename as a tie-breaker:
    ::

        iter_presets('/tmp', ['console', 'tee', '*'], ['json', 'yaml'])

    would find all files in ``/tmp`` named ``*.json`` or ``*.yaml``.  It
    would prefer files named ``console.*`` over files named ``tee.*`` for each
    of the given extensions.

    .. todo::
       This precedence ordering is probably wrong, as it prefers another
       *preset* (e.g. ``tee.json`` over ``console.yaml``) if a more preferable
       config format is used...  This doesn't really matter, as we usually
       select *one* specific *rootname*.

    :param list rootnames:
        An ordered list of file rootnames, (basename without file extension).
        Additionally, the special value '*' matches all rootnames.

    :param list extensions:
        An ordered list of file extensions, without the dot-prefix.
        Additionally, the special value '*' matches all extensions.

    :return generator:
        Returns a generator that yields matching files in `directory`, ordered
        by preference.
    """
    # File extension priority
    ext_weights = dict((e, i) for i, e in enumerate(extensions))
    base_weights = dict((b, i) for i, b in enumerate(rootnames))

    def split(filename):
        base, ext = os.path.splitext(os.path.basename(filename))
        return base, ext.lstrip('.')

    def get_weight(weights, item):
        return weights.get(item, weights.get('*', len(weights)))

    def file_sort_key(filename):
        base, ext = split(filename)
        return (
            get_weight(ext_weights, ext),
            get_weight(base_weights, base),
            filename,
        )

    def valid_name(filename):
        base, ext = split(filename)
        return ((base in rootnames or '*' in rootnames) and
                (ext in extensions or '*' in extensions))

    try:
        # for filename in sorted(os.listdir(directory), cmp=file_sorter):
        for filename in sorted(os.listdir(directory), key=file_sort_key):
            if valid_name(filename):
                yield os.path.join(directory, filename)
    except OSError:
        # Directory does not exist, no files to iterate over
        return


def find_logging_preset(directories, rootname, extensions=None):
    """ Find the first file in any directory with rootname `rootname`.

    :param list directories:
        A list of directories to look through.

    :param str rootname:
        A file basename without file extension.

    :param list extensions:
        An ordered list of acceptable file extensions, see `iter_config`.

    """
    extensions = extensions or ['*']
    for directory in directories:
        for filename in iter_presets(directory, [rootname, ], extensions):
            return filename
    return None


def merge_dict_config(*dict_configs):
    """ Merge two or more logging dict configs, in a somewhat sane manner.

    This currently does a minimal job of merging. The only actual merged
    configuration is:

    disable_existing_loggers
        If set in *any* of the configs, this will also be set in the merged
        config

    root.handlers
        Handlers from all dict_configs will be applied to the root logger.

    All other config values from latter config_dicts will overwrite the value
    from previous config_dicts.

    Note: any dict objects passed in *will* be mutated.
    """
    merged_config = {}

    # merge 'version'
    versions = set(c.pop('version') for c in dict_configs)
    if len(versions) > 1:
        raise NotImplementedError(
            "merge multiple config versions: {0}".format(', '.join(versions)))
    merged_config['version'] = versions.pop()

    # merge 'disable_existing_loggers'
    merged_config['disable_existing_loggers'] = any(
        c.pop('disable_existing_loggers', False) for c in dict_configs)

    for config in dict_configs:
        # merge root handlers
        merged_h = merged_config.get('root', {}).get('handlers', [])
        if 'root' in config:
            merged_config['root'] = config.pop('root')
            for h in reversed(merged_h):
                merged_config['root'].setdefault('handlers', []).insert(0, h)

        # merge filters, loggers, handlers, formatters
        for k in config:
            merged_config.setdefault(k, {}).update(config[k])

    return merged_config


def configure_logging(filename, disable_existing_loggers=None):
    """ Configure loggers.

    This is a wrapper around :func:`logging.config.fileConfig` and
    :func:`logging.config.dictConfig`.

    :param str filename:
        A logger configuration file to apply.

    :param bool disable_existing_loggers:
        Enforce a `disable_existing_loggers` setting. The default is `None`
        which means:

        - do *not* disable exising loggers if ini-style config (this is the
          opposite of the logging.config.fileConfig() default)
        - use value from config if dict-style config
    """
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


def setup_logging(config, preset_name, loglevel, disable_existing=False):
    """
    Configure logging.

    This function finds and applies a *logger preset* (standard Python log
    config).

    :param LoggerConfig config: Logging configuration.
    :param str preset_name: Logger preset to load and use

    :param int loglevel:
        A default loglevel to use with the default (stderr) handler, if no root
        handlers are applied through the logger configuration.

    :param bool disable_existing:
        If any and all existing logger configuration should be disabled.
    """
    extensions = list(e for e in parsers.list_extensions() if e != 'ini')
    if not config.merge:
        extensions.append('ini')

    preset_files = []

    if config.common_preset:
        common_preset = find_logging_preset(config.presets,
                                            config.common_preset,
                                            extensions=extensions)
        if common_preset:
            preset_files.append(common_preset)

    preset = find_logging_preset(config.presets,
                                 preset_name,
                                 extensions=extensions)

    if preset:
        preset_files.append(preset)
    elif config.require_preset:
        raise ValueError(
            "no configuration '{0}' in '{1}'".format(preset_name,
                                                     config.presets))

    if preset_files and config.merge:
        # Merge configs and apply
        config_dict = merge_dict_config(*(loader.read_config(f)
                                          for f in preset_files))
        config_dict['disable_existing_loggers'] |= disable_existing
        logging.config.dictConfig(config_dict)
    elif preset_files:
        # Apply each config in order
        for config_file in preset_files:
            configure_logging(config_file,
                              disable_existing_loggers=disable_existing)
            # The disable_existing is only a default for the first config.
            # Remaining config files should use whatever is specified in the
            # file itself.
            disable_existing = None

    # if no other root handlers have been set up...
    logging.basicConfig(level=loglevel)

    if loglevel:
        logging.getLogger().setLevel(loglevel)

    logger.debug("Logging config {!r}".format(config))
    for c in preset_files:
        logger.debug("Loaded logger config '{0}'".format(c))


def setup_excepthook(exception_config):
    """ Configures handling of uncaught exceptions.

    See :mod:`.logexc` for details.

    :type exception_config: ExceptionsConfig
    :param exception_config: Configuration for exception handling
    """
    from . import logexc
    exchook = logexc.ExceptionLoggerHook(exception_config.level)
    if exception_config.enable:
        logexc.set_exception_hook(exchook)
    logger.debug("Exceptions config {!r}".format(exception_config))


def setup_warnings(warn_config):
    """ Configures warnings capture and filtering.

    See :mod:`.logwarn` for details.

    :type warn_config: WarningsConfig
    :param warn_config: Configuration for warning capture
    """
    from . import logwarn
    # TODO: The filters aren't really log-related. Should this be elsewhere? If
    # so, we need some global init for Cerebrum.
    logwarn.filters.set_filters(warn_config.filters)
    showwarning = logwarn.WarningsLogger(warn_config.level)
    if warn_config.enable:
        logwarn.set_showwarning(showwarning)
    logger.debug("Warnings config {!r}".format(warn_config))


def setup_sentry_sdk(sentry_config):
    """ Configures sentry integration.

    See :mod:`.sentry` for details.

    :type sentry_config: SentryConfig
    :param sentry_config: Sentry configuration
    """
    if sentry_config.enable:
        if not sentry_config.dsn:
            raise ValueError("Missing sentry sdk dsn")
        from . import sentry
        sentry.sentry_init(
            dsn=sentry_config.dsn,
            environment=sentry_config.environment,
        )
    logger.debug("Sentry %s",
                 "enabled" if sentry_config.enable else "disabled")


def configure(config, logger_name, logger_level=None):
    """
    Configure logging and log-related behaviour.

    This function configures the full logging environment.  This includes
    logging and log handlers, logging of unhandled exceptions, logging of
    warnings, and sentry integration.

    :type config: LoggingEnvironment
    :param config: Log environment config to apply

    :param str logger_name: Logger preset to load and apply
    :param int logger_level: Set a minimum log level
    """
    logger_level = logger_level or logging.NOTSET
    setup_logging(config.logging, logger_name, logger_level)
    setup_excepthook(config.exceptions)
    setup_warnings(config.warnings)
    setup_sentry_sdk(config.sentry)


if __name__ == '__main__':
    try:
        from pprintpp import pprint
    except ImportError:
        from pprint import pprint
    config = get_config()
    pprint(config.dump_dict())
