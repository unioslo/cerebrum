# encoding: utf-8
#
# Copyright 2016-2023 University of Oslo, Norway
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
""" Util functions for building a BofhdCommandAPI/BofhdExtension. """
import datetime
import warnings

import six

from Cerebrum.utils import date_compat
from Cerebrum.utils.sorting import make_priority_lookup


def copy_func(src_cls, methods=[]):
    """ This wrapper copies functions and methods from other classes.

    In short, it copies the specified commands and command implementations from
    the `source` class into the wrapped class.

    Example usage:

        @copy_func(Source,
                   commands=['_some_helper', 'group_info', ])
        class Dest(object):
            # Will copy the unbound methods '_some_helper' and 'group_info'
            # from `Source` to `Dest`
            pass

    :param list methods:
        A list of method names to copy.

    :return callable:
        returns a wrapper function to wrap a class.

    :raise RuntimeError: If unable to copy a method.
    """
    def wrapper(dest_cls):
        u""" Actual class wrapper. """
        for method_name in methods:
            if hasattr(dest_cls, method_name):
                raise RuntimeError(
                    '{!r}.{!s} already exists'.format(
                        dest_cls, method_name))

            unbound = src_cls.__dict__.get(method_name)
            if (not callable(unbound)
                    and not isinstance(unbound,
                                       (classmethod, staticmethod))):
                raise RuntimeError(
                    '{!r}.{!s} is not callable'.format(
                        src_cls, method_name))

            setattr(dest_cls, method_name, unbound)
        return dest_cls
    return wrapper


def copy_command(src_cls, src_attr, dest_attr, commands=[]):
    """ This wrapper copies Command objects from other class attributes.

    NOTE: A method with the command name *must* exist in the wrapped class.

    Example usage:

        @copy_cmds(SourceExt,
                   'all_commands',
                   'hidden_commands',
                   commands=['user_info', 'group_info', ])
        class BofhdExtension(BofhdCommonMethods):
            # Will copy the 'user_info' and 'group_info' commands from
            # `SourceExt.all_commands` to `BofhdExtension.hidden_commands`
            pass

    :param type src_cls:
        The class to copy commands from.

    :param str src_attr:
        The attribute in `src_cls` to copy commands from.

    :param str dest_attr:
        The attribute in the wrapped class to assign commands to.

    :param list commands:
        A list of command commands to copy. If empty, all commands from
        `getattr(src_cls, src_attr)` will be copied (this is the default).

    :return callable:
        returns a wrapper function to wrap a `BofhdCommonMethods` class.
    """
    def wrapper(dest_cls):
        u""" Actual class wrapper. """

        # Assert that the dest_cls.dest_attr (dest) dict exists
        if not hasattr(dest_cls, dest_attr):
            setattr(dest_cls, dest_attr, dict())
        dest = getattr(dest_cls, dest_attr)
        source = getattr(src_cls, src_attr, dict())

        # Copy commands from source attribute
        for command_name in commands:
            if command_name not in source:
                raise RuntimeError(
                    'No command {!r} in {!r}.{!s}'.format(
                        command_name, src_cls, src_attr))
            if dest.get(command_name, None) is not None:
                raise RuntimeError(
                    'Command {!r} already defined in {!r}.{!s}'.format(
                        command_name, dest_cls, dest_attr))
                # Already exists
                continue

            implementation = getattr(dest_cls, command_name, None)
            if (not callable(implementation)
                    and not isinstance(implementation,
                                       (classmethod, staticmethod))):
                raise RuntimeError(
                    '{!r}.{!s} is not callable'.format(
                        dest_cls, command_name))
                continue

            # A-ok, ready to copy
            dest[command_name] = source[command_name]
        return dest_cls
    return wrapper


def copy(src_cls, src_attr, dest_attr, commands=[]):
    """ This wrapper allows us to copy everything from other BofhdExtensions.

    In short, it copies the specified commands and command implementations from
    the `src_cls`.`src_attr` into the wrapped class.

    It's really only useful for copying 'hidden_commands' from uio.

    :param type src_cls:
        The class to copy commands from.

    :param str src_attr:
        The attribute in `src_cls` to copy commands from.

    :param str dest_attr:
        The attribute in the wrapped class to assign commands to.

    :param list commands:
        A list of command commands to copy. If empty, all commands from
        `getattr(src_cls, src_attr)` will be copied (this is the default).

    :return callable:
        returns a wrapper function to wrap a `BofhdCommonMethods` class.
    """
    def wrapper(dest_cls):
        u""" Actual class wrapper. """

        # Assert that the dest_cls.dest_attr (dest) dict exists
        if not hasattr(dest_cls, dest_attr):
            setattr(dest_cls, dest_attr, dict())
        source = getattr(src_cls, src_attr, dict())

        if not commands:
            commands.extend(source.keys())

        return copy_command(
            src_cls, src_attr, dest_attr, commands=commands)(
                copy_func(src_cls, methods=commands)(dest_cls))
    return wrapper


def date_to_string(date):
    """
    Takes a date-like object and formats as string.
    """
    date = date_compat.get_date(date)
    if date:
        return date.isoformat()
    return "<not set>"


def exc_to_text(e):
    """ Get an error text from an exception. """
    try:
        text = six.text_type(e)
    except UnicodeError:
        text = bytes(e).decode('utf-8', 'replace')
        warnings.warn("Non-unicode data in exception {!r}".format(e),
                      UnicodeWarning)
    return text


def get_dt_formatter(name='date', fmt='yyyy-MM-dd'):
    return lambda field: u':'.join((field, name, fmt))


default_format_day = get_dt_formatter()


def format_time(field):
    """
    Build a FormatSuggestion field for xmlrpc datetime objects.

    Note: The client should format a 16 char long datetime string.
    """
    fmt = "yyyy-MM-dd HH:mm"            # 16 characters wide
    return ':'.join((field, "date", fmt))


def get_quarantine_status(entity, _today=None):
    """
    Get quarantine status for an entity.

    This function returns a single, human readable value that shows whether an
    entity is quarantined, and if that quarantine is active.

    :returns:
        Returns the most relevant ("most locked"?) quarantine status, if any:

         - "active" - entity has a quarantine that currently applies
         - "disabled" - entity has a quarantine that is temporarily disabled
         - "pending" - entity has a quarantine that hasn't started yet
         - "expired" - entity has a quarantine that has ended
         - None - entity has no quarantines at all
    """
    today = _today or datetime.date.today()
    # Sort key to prioritize the most relevant quarantine status:
    #   active > disabled > pending > expired
    key = make_priority_lookup(('active', 'disabled', 'pending', 'expired'))
    statuses = set()
    for row in entity.get_entity_quarantine():
        start_date = date_compat.get_date(row['start_date'])
        end_date = date_compat.get_date(row['end_date'])
        disable_until = date_compat.get_date(row['disable_until'])
        if end_date and end_date < today:
            statuses.add('expired')
            continue
        if start_date and start_date > today:
            statuses.add('pending')
            continue
        if disable_until and disable_until > today:
            statuses.add('disabled')
            continue
        statuses.add('active')
    ordered = tuple(sorted(statuses, key=key))
    if ordered:
        return ordered[0]
    return None
