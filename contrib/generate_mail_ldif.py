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

import time
import sys
import base64
import getopt

import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum import Account
from Cerebrum import Group
from Cerebrum.Utils import Factory
from Cerebrum.modules import Email
from time import time as now

db = Factory.get('Database')()
co = Factory.get('Constants')(db)
mail_addr = Email.EmailAddress(db)
mail_dom = Email.EmailDomain(db)
mail_targ = Email.EmailTarget(db)
default_mail_file = "/cerebrum/dumps/LDAP/mail.ldif"

aid2addr = {}
targ2addr = {}
targ2spam = {}
targ2quota = {}
targ2virus = {}
targ2prim = {}
base_dn = "dc=uio,dc=no"

def read_addr():
    counter = 0
    curr = now()
    for row in mail_addr.list_email_addresses_ext():
        counter += 1
        if verbose and (counter % 5000) == 0:
            print "  done %d list_email_addresses_ext(): %d sec." % (
                counter, now() - curr)
        a_id, t_id = [int(row[x]) for x in ('address_id', 'target_id')]
        addr = "%s@%s" % (row['local_part'], row['domain'])
        targ2addr.setdefault(t_id, []).append(addr)
        aid2addr[a_id] = addr
        if verbose > 1:
            print "     Id: %d found targ: %d, address: %s"\
                  % (a_id, t_id, addr)

def read_prim():
    counter = 0
    curr = now()
    mail_prim = Email.EmailPrimaryAddressTarget(db)
    for row in mail_prim.list_email_primary_address_targets():
        counter += 1
        if verbose and (counter % 5000) == 0:
            print "  done %d list_email_primary_address_targets(): %d sec." % (
                counter, now() - curr)
        t_id = db.pythonify_data(row['target_id'])
        a_id = db.pythonify_data(row['address_id'])
        targ2prim[t_id] = a_id

def read_spam():
    counter = 0
    curr = now()
    mail_spam = Email.EmailSpamFilter(db)
    for row in mail_spam.list_email_spam_filters_ext():
        if counter == 0:
            print "  done list_email_spam_filters_ext(): %d sec." % (now() - curr)
            counter = 1
        t_id = db.pythonify_data(row['target_id'])
        grade = db.pythonify_data(row['grade'])
        action = db.pythonify_data(row['action'])
        targ2addr[t_id] = [grade, action]

def read_quota():
    counter = 0
    curr = now()
    mail_quota = Email.EmailQuota(db)
    for row in mail_quota.list_email_quota_ext():
        if counter == 0:
            print "  done list_email_quota_ext(): %d sec." % (now() - curr)
            counter = 1
        t_id = db.pythonify_data(row['target_id'])
        q_s = db.pythonify_data(row['quota_soft'])
        q_h = db.pythonify_data(row['quota_hard'])
        targ2quota[t_id] = [q_s, q_h]
        
def read_virus():
    counter = 0
    curr = now()
    mail_virus = Email.EmailVirusScan(db)
    for row in mail_virus.list_email_virus_ext():
        if counter == 0:
            print "  done list_email_virus_ext(): %d sec." % (now() - curr)
            counter = 1
        t_id = db.pythonify_data(row['target_id'])
        f_act = db.pythonify_data(row['found_action'])
        r_act = db.pythonify_data(row['rem_action'])
        en = db.pythonify_data(row['enable'])
        targ2virus[t_id] = [f_act, r_act, en]

def write_ldif():
    counter = 0
    curr = now()

    for row in mail_targ.list_email_targets():
        counter += 1
        if verbose and (counter % 1000) == 0:
            print "  done %d list_email_targets(): %d sec." % (
                counter, now() - curr)
            
        t = db.pythonify_data(row['target_id'])
        mail_targ.clear()
        mail_targ.find(t)

        target = ""
        uid = ""

        # The structure is decided by what target-type the
        # target is (class EmailConstants in Email.py):
        tt = mail_targ.get_target_type()
        tt = Email._EmailTargetCode(int(tt))
        tt_name = mail_targ.get_target_type_name()
        
        if tt == co.email_target_account:
            # Target is the local delivery defined for the Account whose
            # account_id == email_target.entity_id.
            ent_type = mail_targ.get_entity_type()
            ent_id = mail_targ.get_entity_id()

            if ent_type == co.entity_account:
                try:
                    acc = Account.Account(db)
                    acc.clear()
                    acc.find(ent_id)
                    target = acc.account_name
                except Errors.NotFoundError:
                    txt = "Target: %s(account) no user found: %s\n"% (t,ent_id)
                    sys.stderr.write(txt)
                    continue
            else:
                txt = "Target: %s(account) wrong entity type: %s\n"% (t,ent_id)
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
                    acc = Account.Account(db)
                    acc.clear()
                    acc.find(ent_id)
                    uid = acc.account_name
                except Errors.NotFoundError:
                    txt = "Target: %s(%s) no user found: %s\n" % (t, tt, ent_id)
                    sys.stderr.write(txt)
                    continue
            elif ent_type == None and ent_id == None:
                # Catch valid targets with no user bound to it.
                pass
            else:
                txt = "Target: %s (%s) has invalid entities: %s, %s\n" \
                      % (t, tt, ent_type, ent_id)
                sys.stderr.write(txt)
                continue

        elif tt == co.email_target_multi:
            # Target is not set; forwardAddress is the set of
            # addresses that should receive mail for this target.
            mail_fwd = Email.EmailForward(db)
            try:
                mail_fwd.find(t)
                forwards = [x.forward_to for x in mail_fwd.get_forward()
                            if x.enable <> 'T']
            except Errors.NotFoundError:
                # A 'multi' target with no forwarding; seems odd.
                txt = "Target: %s (%s) no forwarding found.\n" % (t, tt)
                sys.stderr.write(txt)
                continue

        else:
            # The target-type isn't known to this script.
            sys.stderr.write("Wrong target-type in target: %s: %s\n" % ( t, tt ))
            continue

        f.write("dn: cn=%s,ou=mail,%s\n" % (t, base_dn))
        f.write("objectClass: top\n")
        f.write("objectClass: mailAddr\n")
        f.write("cn: %s\n" % t)
        f.write("targetType: %s\n" % tt_name)
        #f.write("target:: %s" % base64.encodestring(target)
        f.write("target: %s\n" % target)
        if uid:
            f.write("uid: %s\n" % uid)
        
        # Find primary mail-address:
        if targ2prim.has_key(t):
            f.write("defaultMailAddress: %s\n" % aid2addr[targ2prim[t]])

        # Find addresses for target:
        if targ2addr.has_key(t):
            for a in targ2addr[t]:
                f.write("mail: %s\n" % a)

        # Find spam-settings:
        if targ2spam.has_key(t):
            pass

        # Find quota-settings:
        if targ2quota.has_key(t):
            pass

        # Find virus-setting:
        if targ2virus.has_key(t):
            pass

        #write_misc(t)
        f.write("\n")


def main():
    global verbose, f
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'vm:', ['verbose', 'mail-file'])
    except getopt.GetoptError:
        usage(1)

    verbose = 0
    mail_file = default_mail_file
        
    for opt, val in opts:
        if opt in ('-v', '--verbose'):
            verbose += 1
        elif opt in ('-m', '--mail-file'):
             mail_file = val

    f = file(mail_file,'w')
    start = now()

    if verbose:
        print "Starting read_prim()..."
        curr = now()
    read_prim()
    if verbose:
        print "  done in %d sec." % (now() - curr)       
        print "Starting read_addr()..."
        curr = now()
    read_addr()
    if verbose:
        print "  done in %d sec." % (now() - curr)
        print "Starting read_spam()..."
        curr = now()
#    read_spam()
    if verbose:
        print "  done in %d sec." % (now() - curr)
        print "Starting read_quota()..."
        curr = now()
#    read_quota()
    if verbose:
        print "  done in %d sec." % (now() - curr)
        print "Starting read_virus()..."
        curr = now()
#    read_virus()
    if verbose:
        print "  done in %d sec." % (now() - curr)
        print "Starting write_ldif()..."
        curr = now()
    write_ldif()
    if verbose:
        print "  done in %d sec." % (now() - curr)
        print "Total time: %d" % (now() - start)

if __name__ == '__main__':
    main()
