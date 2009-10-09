#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2004-2009 University of Oslo, Norway
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

import cerebrum_path
from Cerebrum.modules.PasswordNotifier import PasswordNotifier, _send_mail

class UiaPasswordNotifier(PasswordNotifier):
    """
    Mixin for passwordnotifier to record reminded users
    """

    def __init__(self, db=None, logger=None, dryrun=None, *rest, **kw):
        """
        Constructs a UiaPasswordNotifier.

        @type db: Cerebrum.Database or NoneType
        @keyword db: Database object (default use Factory)

        @type logger: logging.logger
        @keyword logger: logger object (default Factory.get_logger('crontab'))

        @type dryrun: boolean
        @keyword dryrun: Refrain from side effects?
        """
        super(PasswordNotifier, self).__init__(db, logger, dryrun, *rest, **kw)       
        self.reminded_users = list()

    # end __init__
                
    def inc_num_notifications(self, account):
        """
        Increases the number for trait by one, and sets other interesting fields.
        """
        traits = account.get_trait(self.config.trait)
        if traits is not None:
            self.reminded_users.append(account.account_name)
        super(PasswordNotifier, self).inc_num_notifications(account)
    # end inc_num_notifications

    def process_accounts(self):
        super(PasswordNotifier, self).process_accounts()
        if not self.dryrun and self.config.summary_to and self.config.summary_from:
            self.splatted_users.sort()
            self.reminded_users.sort()
            body = """Splatted users:
%s

Reminded users:
%s
""" % ("\n".join(self.splatted_users), "\n".join(self.reminded_users))
            _send_mail(self.config.summary_to, self.config.summary_from,
                    "List from password notifier", body, self.logger,
                    self.config.summary_cc)
            
    # end process_accounts


