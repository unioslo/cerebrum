# encoding: utf-8
""" logging cli arguments.

This module contains utilities to parse command line arguments, and use them to
change logging behaviour in Cerebrum. These options typically sets log levels
(--logger-level) or selects a non-default logging preset (--logger-name).

There are two ways to fetch logger settings from the command line:

- Use an ArgumentParser, and add logger arguments with `install_subparser`.
- Extract arguments directly from `sys.argv`

Both should result in an object that contains attributes with the command line
settings.

"""
from __future__ import absolute_import, print_function, unicode_literals
import argparse
import sys
import threading

# Namespace-attributes
OPTION_CAPTURE_EXC = 'logger_capture_exc'
OPTION_CAPTURE_WARN = 'logger_capture_warn'
OPTION_LOGGER_LEVEL = 'logger_level'
OPTION_LOGGER_NAME = 'logger_name'


def install_subparser(parser):
    """ Add a logging subparser to an existing ArgumentParser. """
    subparser = parser.add_argument_group('Logging',
                                          'Override default log configuration')

    # TODO: Should we have both an enable and a disable here?

    # Enable or disable logger exception hook
    exc_mutex = subparser.add_mutually_exclusive_group()
    exc_mutex.add_argument(
        '--logger-exc',
        dest=OPTION_CAPTURE_EXC,
        default=None,
        action='store_true',
        help="Enable exception capture")
    exc_mutex.add_argument(
        '--logger-no-exc',
        dest=OPTION_CAPTURE_EXC,
        default=None,
        action='store_false',
        help="Disable exception capture")

    # Enable or disable logger warnings "hook"
    warn_mutex = subparser.add_mutually_exclusive_group()
    warn_mutex.add_argument(
        '--logger-warn',
        dest=OPTION_CAPTURE_WARN,
        default=None,
        action='store_true',
        help="Enable warnings capture")
    warn_mutex.add_argument(
        '--logger-no-warn',
        dest=OPTION_CAPTURE_WARN,
        default=None,
        action='store_false',
        help="Disable warnings capture")

    # Select a logger preset
    subparser.add_argument(
        '--logger-name',
        metavar='NAME',
        dest=OPTION_LOGGER_NAME,
        help="Override logger configuration")

    # Select a logger level
    subparser.add_argument(
        '--logger-level',
        metavar='LEVEL',
        dest=OPTION_LOGGER_LEVEL,
        help="Override logger level")
    return subparser


def extract_arguments(arglist, options, flags):
    """Extract command line arguments.

    Unfortunately getopt and other argument parsers reacts adversely to unknown
    arguments. Thus we'd have to process command-line arguments ourselves.

    :type arglist: list
    :param arglist:
        The list of command line arguments to process. This would typically be
        `sys.argv`. Note that this function is DESCTUCTIVE, and will alter this
        list.

    :type options: sequence (of basestrings)
    :param options:
        A list of options to extract from `arglist`. Each option will also
        extract the option value (the next argument).

    :type flags: sequence (of basestrings)
    :param flags:
        A list of flags/switches to look for in sys.argv. If the flag is
        present, we'll return True as its value.

    :rtype: dict (of basestring to basestring)
    :return:
        A dictionary mapping entries from L{options} and L{flags} to the values
        belonging to those arguments.

    NOTE: This method should be called within a thread lock if processing
          sys.argv or any other shared/global value.
    """
    # key to command line parameter value
    result = dict()
    # the copy of the original sys.argv
    args = arglist[:]
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

    # Rebuild arglist with remaining args.
    # We must make sure that every reference to sys.argv already made remains
    # intact.
    arglist[:] = list()
    for i in range(0, len(args)):
        if i not in filter_list:
            arglist.append(args[i])

    return result


process_arguments_lock = threading.Lock()


def process_arguments(**kwargs):
    parser = argparse.ArgumentParser()
    install_subparser(parser)

    # Note: This lock does not really help all that much if something outside
    # this module is accessing sys.argv

    # Note that this may also cause problems if your script also has other
    # options that starts with '--logger-<something>'. Look up 'argparse prefix
    # matching' for more details.
    with process_arguments_lock:
        namespace, rest = parser.parse_known_args(sys.argv)
        sys.argv[:] = rest[:]
        return namespace


# python -m Cerebrum.logutils.options


def main(inargs=None):
    parser = argparse.ArgumentParser()
    install_subparser(parser)
    args = parser.parse_args(inargs)
    print(repr(args))


if __name__ == '__main__':
    main()
