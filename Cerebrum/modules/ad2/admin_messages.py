# -*- coding: utf-8 -*-
#
# Copyright 2025 University of Oslo, Norway
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
Module for handling "Admin messages" in the ad sync.

Admin messages are log messages intended for AD administrators.  Admin messages
are typically errors or warnings that needs to be fixed on the Active Directory
side of this integration - e.g. missing permissions.

Note
----
The log handlers defined in this module is probably not *thread safe* - do not
log to the AdAdminMessages.logger from multiple threads.

Also, when using the "file" handler, take care not to re-use the same file in
multiple sync jobs that may run in parallell.


Configuration
-------------
The admin message handling is configured in the AD sync presets, under the
`config['ad_admin_messages']` key.

The value is a list of handlers to use for ad admin messages, and is one of:

noop
    Add ``(None,)`` value as a placeholder - this value has no effect.

log
    Add ``("log",)`` to enable the ad admin logger as a regular logger.  Logs
    are forwarded to the root logger.  This logger doesn't support log level
    filtering - any log messages are filtered according to the root logger
    config.

file
    Add ``("file", <level>, <filename>)`` to write ad admin logs to the given
    file.  Will only write log records of ``level >= <level>``  The
    ``<filename>`` is opened in append-mode, so previous admin log messages are
    kept.  No log rotation or cleanup, so this file should be regularly emptied
    or archived.

mail
    Add ``("mail", <level>, <recipients>)`` to send ad admin logs to the given
    recipient list after the sync has finished.
    Only log records of ``level >= <level>`` are included in the email.  Will
    send one email for each recipient in the ``<recipients>`` list.


Example
-------
Set up admin messages functionality early:
::

    # Set up logger and handlers early:
    admin_logger = logging.getLogger("ad_admin_messages")
    admin_messages = AdminMessages(admin_logger)

    # Apply the ad-sync config:
    admin_messages.apply_config({
        'ad_admin_messages': [
            ("log",),
            ("file", "info", "/var/log/ad-admin-messages.log"),
            ("email", "error", ["ad-errors@example.org"]),
        ],
        'domain': "example.org",
        'sync_type': "example-sync",
    })

    # Log issues as they occur:
    admin_messages.logger.info("Hello world")

    # Before the sync ends, dispatch any buffered/cached messages.  This will
    # e.g. send emails using the "email" handler, if configured and enabled:
    admin_messages.finalize()

"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import logging

from Cerebrum.utils import email as email_utils

logger = logging.getLogger(__name__)


class _AdminMessageFileHandler(logging.FileHandler):
    """ A simple file handler for logging ad admin messages to a file """

    admin_log_format = "%(levelname)s: %(message)s"

    def __init__(self, levelno, filename, fmt=admin_log_format):
        super(_AdminMessageFileHandler, self).__init__(
            filename=filename,
            mode="a",
        )
        self.setFormatter(logging.Formatter(fmt=fmt))
        self.setLevel(levelno)


class _AdminMessageEmailHandler(logging.Handler):
    """ A handler for collecting admin messages to send by email """

    admin_log_sender = "cerebrum@usit.uio.no"
    admin_log_format = "%(levelname)s: %(message)s"

    def __init__(self, levelno, subject, recipients, dryrun,
                 fmt=admin_log_format):
        super(_AdminMessageEmailHandler, self).__init__(level=levelno)
        self.setFormatter(logging.Formatter(fmt=fmt))
        self.setLevel(levelno)
        self.__subject = subject
        self.__recipients = recipients
        self.__dryrun = dryrun
        self.__messages = []

    def emit(self, record):
        try:
            msg = self.format(record)
            self.__messages.append(msg)
        except Exception:
            self.handleError(record)

    def send_messages(self):
        num_messages = len(self.__messages)
        if not num_messages:
            logger.info("No admin messages for %s", self.__recipients)
            return
        logger.debug("Sending %d admin messages to %s",
                     num_messages, self.__recipients)
        message = "\n".join(self.__messages)
        self.__messages = []
        sent = []
        for address in self.__recipients:
            try:
                email_utils.sendmail(
                    address, self.admin_log_sender, self.__subject,
                    message, charset='utf-8', debug=self.__dryrun,
                )
                sent.append(address)
            except Exception as e:
                logger.warning("Error sending AD-messages to %s: %s",
                               address, e)
        logger.info("Sent %d admin messages to %s", num_messages, sent)


class AdminMessages(object):
    """
    Admin messages are special log messages intended for ad-admins.

    They can be logged to our regular logger, logged to a separate file and/or
    sent by email after the sync is complete.
    """
    levels = {
        'debug': logging.DEBUG,
        'info': logging.INFO,
        'warning': logging.WARNING,
        'error': logging.ERROR,
    }

    @classmethod
    def get_level(cls, name):
        level_name = name.lower()
        if level_name in cls.levels:
            return cls.levels[level_name]
        raise ValueError("invalid admin message level: " + repr(name))

    def __init__(self, logger):
        self.logger = logger
        if not self.logger.handlers:
            # Ensure there's at least a NullHandler to ignore any messages when
            # the admin messages logger is disabled
            self.logger.addHandler(logging.NullHandler())
        self.logger.propagate = 0
        self._callbacks = []
        self._configured = False

    def enable_logging(self):
        self.logger.propagate = 1

    def add_admin_file(self, levelno, filename):
        handler = _AdminMessageFileHandler(levelno, filename)
        self.logger.addHandler(handler)
        self._callbacks.append(handler.flush)

    def add_admin_email(self, levelno, subject, addresses, dryrun):
        handler = _AdminMessageEmailHandler(levelno, subject, addresses,
                                            dryrun)
        self.logger.addHandler(handler)
        self._callbacks.append(handler.send_messages)

    def finalize(self):
        for callback in self._callbacks:
            callback()

    @classmethod
    def validate_config(cls, config):
        for config_item in (config.get('ad_admin_messages') or []):
            name, args = config_item[0], config_item[1:]
            if name is None:
                continue
            if name == "log":
                yield (cls.enable_logging, tuple())
                continue
            if name == "file":
                level, filename = args
                levelno = cls.get_level(level)
                if not filename:
                    raise ValueError("missing filename for admin message")
                yield (cls.add_admin_file, (levelno, filename))
                continue
            if name == "email":
                level, addrs = args
                levelno = cls.get_level(level)
                if not isinstance(addrs, (list, set, tuple)):
                    raise ValueError("invalid address list for admin message: "
                                     + repr(addrs))
                for addr in addrs:
                    if not email_utils.is_email(addr):
                        raise ValueError("invalid address for admin message: "
                                         + repr(addr))

                subject = "AD-sync messages for %s at %s" % (
                     config['sync_type'],
                     config['domain'],
                )
                yield (cls.add_admin_email, (levelno, subject, addrs,
                                             config['dryrun']))
                continue
            raise ValueError("unknown admin message handler: " + repr(name))

    def apply_config(self, config):
        """ Add admin message handling from config. """
        if self._configured:
            # safeguard against calling apply_config twice
            raise ValueError("config already applied!")
        to_apply = list(self.validate_config(config))
        for func, args in to_apply:
            logger.info("using admin-messages: %s(%s)",
                        func.__name__, ", ".join(repr(a) for a in args))
            func(self, *args)
