# -*- coding: utf-8 -*-

"""
Log configuration.

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

from Cerebrum.config import loader
from Cerebrum.config import parsers
from Cerebrum.config.configuration import (ConfigDescriptor,
                                           Configuration,
                                           Namespace)
from Cerebrum.config.settings import String, Boolean, Iterable, Choice


# Make it possible to override sys.prefix for configuration path purposes
sys_prefix = os.getenv('CEREBRUM_SYSTEM_PREFIX', sys.prefix)

DEFAULT_LOGDIR = os.path.join(sys_prefix, 'var', 'log', 'cerebrum')
DEFAULT_PRESET_DIR = os.path.join(sys_prefix, 'etc', 'cerebrum',
                                  'logger-presets')

# Make it possible to override DEFAULT_LOGGING_CONFIG
DEFAULT_LOGGING_CONFIG = os.getenv('CEREBRUM_DEFAULT_LOGGING_CONFIG', 'logenv')

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


class LoggerConfig(Configuration):
    """ Configures how to process named logging setup. """

    logdir = ConfigDescriptor(
        String,
        default=DEFAULT_LOGDIR,
        doc="Root directory for log files (cerebrum handlers only)")

    presets = ConfigDescriptor(
        Iterable,
        template=String(),
        default=[DEFAULT_PRESET_DIR, ],
        doc="Directories with logger preset configurations")

    merge = ConfigDescriptor(
        Boolean,
        default=False,
        doc="Merge logger presets before applying"
            " (ini-style configs not supported)")

    common_preset = ConfigDescriptor(
        String,
        default='',
        doc="Common logger preset."
            " This named preset will always be applied, if available."
            " Set to an empty string to disable.")

    require_preset = ConfigDescriptor(
        Boolean,
        default=False,
        doc="Fail if the named logger configuration file is missing.")


class LoggingEnvironment(Configuration):
    """ Configuration of the logging environment. """

    logging = ConfigDescriptor(
        Namespace,
        config=LoggerConfig)

    exceptions = ConfigDescriptor(
        Namespace,
        config=ExceptionsConfig)

    warnings = ConfigDescriptor(
        Namespace,
        config=WarningsConfig)


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
    """ Iterate over matching rootnames in directory.

    Iterates over files in `directory` that matches one of the given
    `rootnames`, and one of the given `extensions`.

    Matching files will also be ordered by `rootnames` and `extensions`:

        iter_presets('/tmp', ['*', 'foo'], ['*', 'bar'])

    would yield all files in '/tmp', but a file named 'foo.z' would be sorted
    after any other file '*.z', and a file named 'z.bar' would be
    ordered after any other file 'z.*'.

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

    def file_sorter(a, b):
        base_a, ext_a = split(a)
        base_b, ext_b = split(b)
        return (
            cmp(get_weight(ext_weights, ext_a),
                get_weight(ext_weights, ext_b)) or
            cmp(get_weight(base_weights, base_a),
                get_weight(base_weights, base_b)) or
            cmp(a, b))

    def valid_name(filename):
        base, ext = split(filename)
        return ((base in rootnames or '*' in rootnames) and
                (ext in extensions or '*' in extensions))

    try:
        for filename in sorted(os.listdir(directory), cmp=file_sorter):
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

    This is a wrapper around logging.config.fileConfig and
    logging.config.dictConfig.

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
    """ (re)configures logging.

    :param LoggerConfig config:
        A configuration that controls the loading of logger configuration.

    :param str preset_name:
        Which logger configuration to set up.

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


def configure(config, logger_name, logger_level=None):
    logger_level = logger_level or logging.NOTSET
    setup_logging(config.logging, logger_name, logger_level)
    setup_excepthook(config.exceptions)
    setup_warnings(config.warnings)


if __name__ == '__main__':
    try:
        from pprintpp import pprint
    except ImportError:
        from pprint import pprint
    config = get_config()
    pprint(config.dump_dict())
