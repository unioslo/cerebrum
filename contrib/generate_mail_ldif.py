#!/usr/bin/env python2.2

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

targ2addr = {}
targets = []


def read_addr():
    for row in mail_addr.list_email_addresses():

        id = Cerebrum.pythonify_data(row['address_id'])
        mail_addr.clear()
        mail_addr.find(id)
        targ_id = mail_addr.get_target_id()

        targ2addr.setdefault(int(targ_id), []).append(id)


def read_targ():
    for row in mail_targ.list_email_targets():

        id = Cerebrum.pythonify_data(row['target_id'])
        mail_targ.clear()
        mail_targ.find(id)

        targets.append(id)

def write_misc(t):
    mail_quota = Email.EmailQuota(Cerebrum)
    mail_spam = Email.EmailSpamFilter(Cerebrum)
    mail_virus = Email.EmailVirusScan(Cerebrum)

    # Find quota-info for target:
    try:
        mail_quota.clear()
        mail_quota.find(t)
        print "softQuota: %d" % mail_quota.get_quota_soft()
        print "hardQuota: %d" % mail_quota.get_quota_hard()
    except Errors.NotFoundError:
        pass

    # Find SPAM-info for target:
    try:
        mail_spam.clear()
        mail_spam.find(t)
        print "spamLevel: %d" % mail_spam.get_spam_level()
        print "spamAction: %s" % mail_spam.get_spam_action()
    except Errors.NotFoundError:
        pass

    # Find virus-info for target:
    try:
        mail_virus.clear()
        mail_virus.find(t)
        # TODO: somthing smart, but if .. else for now.
        if mail_virus.get_enable():
            print "virusScanning: True"
        else:
            print "virusScanning: Flase"
        print "virusFound: %s" % mail_virus.get_virus_found_act()
        print "virusRemoved: %s" % mail_virus.get_virus_removed_act()
    except Errors.NotFoundError:
        pass


def write_ldif():
    mail_prim = Email.EmailPrimaryAddress(Cerebrum)

    for t in targets:
        mail_targ.clear()
        mail_targ.find(t)

        target = ""
        uid = ""

        # The structure is decided by what target-type the
        # target is (class EmailConstants in Email.py):
        tt = mail_targ.get_target_type()
        tt = Email._EmailTargetCode(int(tt))

        if tt == co.email_target_account:
            # Target is the local delivery defined for the Account whose
            # account_id == email_target.entity_id.
            ent_type = mail_targ.get_entity_type()
            ent_id = mail_targ.get_entity_id()
            # TODO: Get string "account" out of EmailTarget, not a number.
            if ent_type == co.entity_account:
                try:
                    acc = Account.Account(Cerebrum)
                    acc.clear()
                    acc.find(ent_id)
                    target = acc.account_name
                except Errors.NotFoundError:
                    txt = "Target: %s(account) no user found: %s"% (t,ent_id)
                    sys.stderr.write(txt)
                    continue
            else:
                txt = "Target: %s(account) wrong entity type: %s"% (t,ent_id)
                sys.stderr.write(txt)
                continue
            
        elif tt == co.email_target_pipe or \
             tt == co.email_target_file or \
             tt == co.email_target_Mailman:

            # Target is a shell pipe. The command (and args) to pipe mail
            # into is gathered from email_target.alias_value.  Iff
            # email_target.entity_id is set and belongs to an Account,
            # deliveries to this target will be run as that account.
            #   or
            # Target is a file. The absolute path of the file is gathered
            # from email_target.alias_value.  Iff email_target.entity_id
            # is set and belongs to an Account, deliveries to this target
            # will be run as that account.
            #   or
            # Target is a Mailman mailing list. The command (and args) to
            # pipe mail into is gathered from email_target.alias_value.
            # Iff email_target.entity_id is set and belongs to an
            # Account, deliveries to this target will be run as that
            # account.
            target = mail_targ.get_alias()
            if target == None:
                txt = "Target: %s(%s) needs a value in alias_value\n" % (t, tt)
                sys.stderr.write(txt)
                continue

            ent_type = mail_targ.get_entity_type()
            ent_id = mail_targ.get_entity_id()
            # TODO: Get "account" out of EmailTarget, not a number.
            if ent_type == co.entity_account:
                try:
                    acc = Account.Account(Cerebrum)
                    acc.clear()
                    acc.find(ent_id)
                    uid = acc.account_name
                except Errors.NotFoundError:
                    txt = "Target: %s(%s) no user found: %s" % (t, tt, ent_id)
                    sys.stderr.write(txt)
                    continue
            elif ent_type == None and ent_id == None:
                # Catch valid targets with no user bound to it.
                pass
            else:
                txt = "Target: %s (%s) has invalid entities: %s, %s" \
                      % (t, tt, ent_type, ent_id)
                stderr.write(txt)
                continue

        elif tt == co.email_target_multi:
            # Target is not set; forwardAddress is the set of
            # addresses that should receive mail for this target.
            mail_fwd = Email.EmailForward(Cerebrum)
            try:
                mail_fwd.find(t)
                forwards = [x.forward_to for x in mail_fwd.get_forward()
                            if x.enable <> 'T']
            except Errors.NotFoundError:
                # A 'multi' target with no forwarding; seems odd.
                txt = "Target: %s (%s) no forwarding found." % (t, tt)
                sys.stderr.write(txt)
                continue

        else:
            # The target-type isn't known to this script.
            sys.stderr.write("Wrong target-type in target: %s: %s" % ( t, tt ))
            continue

        print "dn: cn=a%s,ou=mail,dc=uio,dc=no" % t
        print "objectClass: top"
        print "objectClass: mailAddr"
        print "targetType: %s" % tt
        #print "target:: %s" % base64.encodestring(target)
        print "target: %s" % target
        if uid:
            print "uid: %s" % uid
        
        # Find primary mail-address:
        try:
            mail_prim.clear()
            mail_prim.find(t)
            a = mail_prim.get_address_id()
            mail_addr.clear()
            mail_addr.find(a)
            dom_id = mail_addr.get_domain_id()
            mail_dom.clear()
            mail_dom.find(dom_id)
            print "defaultMailAddress: %s@%s" % ( mail_addr.get_localpart(),
                                                  mail_dom.get_domain_name() )
        except Errors.NotFoundError:
            pass

        # Find addresses for target:
        if targ2addr.has_key(t):
            for a in targ2addr[t]:
                mail_addr.clear()
                mail_addr.find(a)
                dom_id = mail_addr.get_domain_id()
                mail_dom.clear()
                mail_dom.find(dom_id)
                print "mail: %s@%s" % ( mail_addr.get_localpart(),
                                        mail_dom.get_domain_name() )


        write_misc(t)
        print "\n"


def main():
    read_addr()
    read_targ()
    write_ldif()


if __name__ == '__main__':
    main()
