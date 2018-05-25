#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2004-2018 University of Oslo, Norway
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

from __future__ import unicode_literals
from Cerebrum.modules.password_notifier.notifier import EmailPasswordNotifier
from Cerebrum.modules.password_notifier.notifier import _send_mail


class UiaPasswordNotifier(EmailPasswordNotifier):
    """
    Mixin for passwordnotifier to record reminded users
    """

    # Additional default settings for this class
    defaults = {
        'list_to': None,
    }

    def __init__(self, db=None, logger=None, dryrun=None, *rest, **kw):
        """
        Constructs a UiaPasswordNotifier.

        @type db: Cerebrum.database.Database or NoneType
        @keyword db: Database object (default use Factory)

        @type logger: logging.logger
        @keyword logger: logger object (default Factory.get_logger('crontab'))

        @type dryrun: boolean
        @keyword dryrun: Refrain from side effects?
        """
        super(UiaPasswordNotifier, self).__init__(db, logger, dryrun,
                                                  *rest, **kw)
        self.reminded_users = list()

    def inc_num_notifications(self, account):
        """
        Increases the number for trait by one, and sets other interesting
        fields.
        """
        traits = account.get_trait(self.constants.EntityTrait(
            self.config.trait))
        if traits is not None:
            self.reminded_users.append(account.account_name)
        super(UiaPasswordNotifier, self).inc_num_notifications(account)

    def process_accounts(self):
        super(UiaPasswordNotifier, self).process_accounts()
        if (not self.dryrun and
                self.config.summary_to and
                self.config.summary_from):
            self.splatted_users.sort()
            self.reminded_users.sort()
            body = "Splatted users:\n{}\n\nReminded users:\n{}\n".format(
                "\n".join(self.splatted_users),
                "\n".join(self.reminded_users))
            _send_mail(
                mail_to=', '.join(self.config.summary_to),
                mail_from=self.config.summary_from,
                subject="List from password notifier",
                body=body)
