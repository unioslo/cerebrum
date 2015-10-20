#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2004-2010 University of Oslo, Norway
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
from Cerebrum.Utils import Factory
from Cerebrum.modules.pwcheck.history import PasswordHistory
import mx.DateTime as dt

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
        super(UiaPasswordNotifier, self).__init__(db, logger, dryrun, *rest, **kw)       
        self.reminded_users = list()
        if not hasattr(self.config, 'employee_maxage'):
            self.config.employee_maxage = dt.DateTimeDelta(3*30)

    # end __init__
                
    def inc_num_notifications(self, account):
        """
        Increases the number for trait by one, and sets other interesting fields.
        """
        traits = account.get_trait(self.config.trait)
        if traits is not None:
            self.reminded_users.append(account.account_name)
        super(UiaPasswordNotifier, self).inc_num_notifications(account)
    # end inc_num_notifications

    def process_accounts(self):
        super(UiaPasswordNotifier, self).process_accounts()
        if (not self.dryrun and hasattr(self.config, 'list_to') and self.config.list_to 
                and self.config.summary_from):
            self.splatted_users.sort()
            self.reminded_users.sort()
            body = """Splatted users:
%s

Reminded users:
%s
""" % ("\n".join(self.splatted_users), "\n".join(self.reminded_users))
            _send_mail(self.config.list_to, self.config.summary_from,
                    "List from password notifier", body, self.logger)
            
    # end process_accounts

    def get_old_account_ids(self):
        """
        Returns a set of account_id's for candidates.

        SSØ demands that UiA primary users change passwords every 4 months.
        We set self.config.employee_maxage to three months above, and grace_period
        accounts for the fourth.
        """
        # Get som ids from super()
        old_ids = super(UiaPasswordNotifier, self).get_old_account_ids()
        person = Factory.get("Person")(self.db)
        account = Factory.get("Account")(self.db)
        ph = PasswordHistory(self.db)
        personids = set()

        # Find all employees. This might return the same person more than once,
        # so we cache the used ones in personids.
        for row in person.list_affiliations(
                affiliation=(self.constants.affiliation_ansatt,
                    self.constants.affiliation_tilknyttet)):
            perid = row['person_id']
            if not perid in personids:
                self.logger.debug("Checking employee %s", perid)
                personids.add(perid)
                person.clear()
                person.find(perid)

                # find primary account
                accid = person.get_primary_account()
                if accid:
                    self.logger.debug("Checking acc %s", accid)
                    account.clear()
                    account.find(accid)
                    quara = account.get_entity_quarantine(self.constants.quarantine_autopassord)
                    if quara:
                        self.logger.debug("User has autopassord")
                        continue
                    # get last password date
                    history = [x['set_at'] for x in ph.get_history(accid)]
                    if history:
                        datum = max(history)
                        # if password is too old
                        if self.today - datum > self.config.employee_maxage:
                            self.logger.debug("Adding employee %s", accid)
                            old_ids.add(accid)
        return old_ids
    # end get_old_account_ids

