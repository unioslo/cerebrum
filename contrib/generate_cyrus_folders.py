#!/usr/bin/env python2.2
# -*- coding: iso-8859-1 -*-

# Copyright 2003 University of Oslo, Norway
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

#

import time
import sys
import base64

import cerebrum_path
from Cerebrum import Errors
from Cerebrum import Account
from Cerebrum import Group
from Cerebrum.Utils import Factory
from Cerebrum.modules import Email

Cerebrum = Factory.get('Database')()
co = Factory.get('Constants')(Cerebrum)
mail_addr = Email.EmailAddress(Cerebrum)
mail_dom = Email.EmailDomain(Cerebrum)
mail_targ = Email.EmailTarget(Cerebrum)

targets = []

def read_targ():
    """Make a list of all targets which are of type account"""
    
    account_type = int(Email.EmailConstants.email_target_account)
    
    for row in mail_targ.list_email_targets():
        id = Cerebrum.pythonify_data(row['target_id'])
        mail_targ.clear()
        mail_targ.find(id)

        if mail_targ.get_target_type() == account_type:
	    targets.append(id)

def get_quota(t):
    """Look up email quota for target t."""
    mail_quota = Email.EmailQuota(Cerebrum)
    q = 0
    # Find quota-info for target:
    try:
        mail_quota.clear()
        mail_quota.find(t)
        q = mail_quota.get_quota_soft()
    except Errors.NotFoundError:
        pass
    return q

def create_inboxes():
    """Loop through list initialised by read_targ() and emit instructions
    for Cyrus on stdout."""
    acc = Account.Account(Cerebrum)
    
    for t in targets:
        mail_targ.clear()
        mail_targ.find(t)

        # Target is the local delivery defined for the Account whose
        # account_id == email_target.entity_id.
        ent_type = mail_targ.get_entity_type()
        ent_id = mail_targ.get_entity_id()
        # TODO: Get string "account" out of EmailTarget, not a number.
        if ent_type == co.entity_account:
            try:
                acc.clear()
                acc.find(ent_id)
                target = acc.account_name
                print "createmailbox user.%s\n" % target
                q = get_quota(target)
                if q > 0:
                    print "setquota user.%s %d" % (uname, q)
            except Errors.NotFoundError:
                txt = "Target: %s(account) no user found: %s"% (t,ent_id)
                sys.stderr.write(txt)
                continue
            else:
                txt = "Target: %s(account) wrong entity type: %s"% (t,ent_id)
                sys.stderr.write(txt)
                continue


def main():
    read_targ()
    create_inboxes()

if __name__ == '__main__':
    main()
