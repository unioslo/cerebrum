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
mail_dom = Email.EmailDomain(db)
mail_targ = Email.EmailTarget(db)
default_mail_file = "/cerebrum/dumps/LDAP/mail.ldif"

aid2addr = {}
targ2addr = {}
targ2spam = {}
targ2quota = {}
targ2virus = {}
targ2prim = {}
serv_id2server = {}
targ2server_id = {}
targ2forward = {}
targ2vacation = {}
acc2name = {}

base_dn = "dc=uio,dc=no"

def read_addr():
    counter = 0
    curr = now()
    mail_addr = Email.EmailAddress(db)
    for row in mail_addr.list_email_addresses_ext():
        counter += 1
        if verbose and (counter % 10000) == 0:
            print "  done %d list_email_addresses_ext(): %d sec." % (
                counter, now() - curr)
        a_id, t_id = [int(row[x]) for x in ('address_id', 'target_id')]
        addr = "%s@%s" % (row['local_part'], row['domain'])
        targ2addr.setdefault(t_id, []).append(addr)
        aid2addr[a_id] = addr

def read_prim():
    counter = 0
    curr = now()
    mail_prim = Email.EmailPrimaryAddressTarget(db)
    for row in mail_prim.list_email_primary_address_targets():
        counter += 1
        if verbose and (counter % 10000) == 0:
            print "  done %d list_email_primary_address_targets(): %d sec." % (
                counter, now() - curr)
        targ2prim[int(row['target_id'])] = int(row['address_id'])

def read_spam():
    counter = 0
    curr = now()
    mail_spam = Email.EmailSpamFilter(db)
    for row in mail_spam.list_email_spam_filters_ext():
        if counter == 0:
            print "  done list_email_spam_filters_ext(): %d sec." % (now() - curr)
            counter = 1
        targ2spam[int(row['target_id'])] = [row['level'], row['code_str']]

def read_quota():
    counter = 0
    curr = now()
    mail_quota = Email.EmailQuota(db)
    for row in mail_quota.list_email_quota_ext():
        if counter == 0:
            print "  done list_email_quota_ext(): %d sec." % (now() - curr)
            counter = 1
        targ2quota[int(row['target_id'])] = [row['quota_soft'],
                                             row['quota_hard']]
        
def read_virus():
    counter = 0
    curr = now()
    mail_virus = Email.EmailVirusScan(db)
    for row in mail_virus.list_email_virus_ext():
        if counter == 0:
            print "  done list_email_virus_ext(): %d sec." % (now() - curr)
            counter = 1
        targ2virus[int(row['target_id'])] = [row['found_str'],
                                             row['removed_str'],
                                             row['enable']]

def read_IMAP_server():
    mail_serv = Email.EmailServer(db)
    for row in mail_serv.list_email_server_ext():
        serv_id2server[int(row['server_id'])] = [row['server_type'],
                                                 row['name']]
    mail_targ_serv = Email.EmailServerTarget(db)
    for row in mail_targ_serv.list_email_server_targets():
        targ2server_id[int(row['target_id'])] = int(row['server_id'])

def read_forward():
    mail_forw = Email.EmailForward(db)
    for row in mail_forw.list_email_forwards():
        targ2forward.setdefault(int(row['target_id']), []).append([row['forward_to'],
                                                                   row['enable']])

def read_vacation():
    mail_vaca = Email.EmailVacation(db)
    for row in mail_vaca.list_email_vacations():
        targ2vacation[int(row['target_id'])] = [row['vacation_text'],
                                                row['start_date'],
                                                row['end_date'],
                                                row['enable']]

def read_accounts():
    acc = Account.Account(db)
    for row in acc.list_account_names():
        acc2name[int(row['account_id'])] = row['entity_name']

def write_ldif():
    counter = 0
    curr = now()

    for row in mail_targ.list_email_targets_ext():
        t = int(row['target_id'])
        tt = int(row['target_type'])
        if row['entity_type']:
            et = int(row['entity_type'])
        if row['entity_id']:
            ei = int(row['entity_id'])
        alias = row['alias_value']
        
        counter += 1
        if verbose and (counter % 5000) == 0:
            print "  done %d list_email_targets(): %d sec." % (
                counter, now() - curr)
            
        target = ""
        uid = ""
        rest = ""

        # The structure is decided by what target-type the
        # target is (class EmailConstants in Email.py):
        tt = Email._EmailTargetCode(int(tt))

        if tt == co.email_target_account:
            # Target is the local delivery defined for the Account whose
            # account_id == email_target.entity_id.
            if et == co.entity_account:
                if acc2name.has_key(ei):
                    target = acc2name[ei]
                else:
                    txt = "Target: %s(account) no user found: %s\n"% (t,ei)
                    sys.stderr.write(txt)
                    continue
            else:
                txt = "Target: %s(account) wrong entity type: %s\n"% (t,ei)
                sys.stderr.write(txt)
                continue
            
            # Find quota-settings:
            if targ2quota.has_key(t):
                soft, hard = targ2quota[t]
                rest += "softQuota: %s\n" % soft
                rest += "hardQuota: %s\n" % hard

            # Find vacations-settings:
            if targ2vacation.has_key(t):
                txt, start, end, enable = targ2vacation[t]
                if enable == 'T':
                    cur = db.DateFromTicks(time.time())
                    if start and end and start <= cur and end >= cur:
                        rest += "tripnote:: %s\n" %  base64.encodestring(txt)

            # Find spam-settings:
            if targ2spam.has_key(t):
                level, action = targ2spam[t]
                rest += "spamLevel: %s\n" % level
                rest += "spamAction: %s\n" % action

            # Find virus-setting:
            if targ2virus.has_key(t):
                found, rem, enable = targ2virus[t]
                rest += "virusFound: %s\n" % found
                rest += "virusRemoved: %s\n" % rem
                if enable == 'T':
                    rest += "virusScanning: TRUE\n"
                else:
                    rest += "virusScanning: FALSE\n"

        elif tt == co.email_target_deleted:
            # Target type for addresses that are no longer working, but
            # for which it is useful to include of a short custom text in
            # the error message returned to the sender.  The text
            # is taken from email_target.alias_value
            if et == co.entity_account:
                if acc2name.has_key(ei):
                    target = acc2name[ei]
            if alias:
                rest += "forwardDestination: :fail: %s\n" % alias

        
        elif tt == co.email_target_forward:
            # Target is a pure forwarding mechanism; local deliveries will
            # only occur as indirect deliveries to the addresses forwarded
            # to.  Both email_target.entity_id and email_target.alias_value
            # should be NULL, as they are ignored.  The email address(es)
            # to forward to is taken from table email_forward.
            pass
        
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

            if alias == None:
                txt = "Target: %s(%s) needs a value in alias_value\n" % (t, tt)
                sys.stderr.write(txt)
                continue

            rest += "target: %s\n" % alias

            if et == co.entity_account:
                if acc2name.has_key(ei):
                    uid = acc2name[ei]
                else:
                    txt = "Target: %s(%s) no user found: %s\n" % (t, tt, ei)
                    sys.stderr.write(txt)
                    continue
            elif et == None and ei == None:
                # Catch valid targets with no user bound to it.
                pass
            else:
                txt = "Target: %s (%s) has invalid entities: %s, %s\n" \
                      % (t, tt, et, ei)
                sys.stderr.write(txt)
                continue

        elif tt == co.email_target_multi:
            # Target is the set of `account`-type targets corresponding to
            # the Accounts that are first-level members of the Group that
            # has group_id == email_target.entity_id.
            if targ2forward.has_key(t):
                for forw, enable in targ2forward[t]:
                    if enable == 'T':
                        rest += "forwardDestination: %s\n" % targ2addr[int(forw)]
            else:
                # A 'multi' target with no forwarding; seems odd.
                txt = "Target: %s (%s) no forwarding found.\n" % (t, tt)
                sys.stderr.write(txt)
                continue 

        else:
            # The target-type isn't known to this script.
            sys.stderr.write("Wrong target-type in target: %s: %s\n" % ( t, tt ))
            continue

        f.write("dn: cn=d%s,ou=mail,%s\n" % (t, base_dn))
        f.write("objectClass: top\n")
        f.write("objectClass: mailAddr\n")
        f.write("cn: d%s\n" % t)
        f.write("targetType: %s\n" % tt)
        if target:
            f.write("target: %s\n" % target)
        if uid:
            f.write("uid: %s\n" % uid)
        if rest:
            f.write(rest)
        
        # Find primary mail-address:
        if targ2prim.has_key(t):
            f.write("defaultMailAddress: %s\n" % aid2addr[targ2prim[t]])
            
        # Find addresses for target:
        if targ2addr.has_key(t):
            for a in targ2addr[t]:
                f.write("mail: %s\n" % a)

        # Find mail-server settings:
        if targ2server_id.has_key(t):
            type, name = serv_id2server[int(targ2server_id[t])]
            if type == co.email_server_type_nfsmbox:
                f.write("spoolInfo: %s\n" % name)
            elif type == co.email_server_type_cyrus:
                f.write("IMAPserver: %s\n" % name)

        # Find forward-settings:
        if targ2forward.has_key(t):
            for addr,enable in targ2forward[t]:
                if enable == 'T':
                    f.write("forwardDestination: %s\n" % addr)
                
        f.write("\n")

def usage():
    print """
generate_mail_ldif.py [-v|--verbose]+ [-m|--mail-file <file>]
  -v|--verbose: Shows some statistics.
  -m|--mail-file <file>: Specify file to write to."""
    sys.exit(0)

def main():
    global verbose, f
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'vm:', ['verbose', 'mail-file'])
    except getopt.GetoptError:
        usage()

    verbose = 0
    mail_file = default_mail_file
        
    for opt, val in opts:
        if opt in ('-v', '--verbose'):
            verbose += 1
        elif opt in ('-m', '--mail-file'):
            mail_file = val
        elif opt in ('-h', '--help'):
            usage()
    f = file(mail_file,'w')
    start = now()

    if verbose:
        print "Starting read_prim()..."
        curr = now()
    read_prim()
    if verbose:
        print "  done in %d sec." % (now() - curr)       
        print "Starting read_virus()..."
        curr = now()
    read_virus()
    if verbose:
        print "  done in %d sec." % (now() - curr)
        print "Starting read_spam()..."
        curr = now()
    read_spam()
    if verbose:
        print "  done in %d sec." % (now() - curr)
        print "Starting read_quota()..."
        curr = now()
    read_quota()
    if verbose:
        print "  done in %d sec." % (now() - curr)
        print "Starting read_addr()..."
        curr = now()
    read_addr()
    if verbose:
        print "  done in %d sec." % (now() - curr)
        print "Starting read_IMAP_server()..."
        curr = now()    
    read_IMAP_server()
    if verbose:
        print "  done in %d sec." % (now() - curr)
        print "Starting read_vacation()..."
        curr = now()    
    read_vacation()
    if verbose:
        print "  done in %d sec." % (now() - curr)
        print "Starting read_forward()..."
        curr = now()    
    read_forward()
    if verbose:
        print "  done in %d sec." % (now() - curr)
        print "Starting read_account()..."
        curr = now()    
    read_accounts()
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
