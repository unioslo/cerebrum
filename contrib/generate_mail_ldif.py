#!/usr/bin/env python2.2
# -*- coding: iso-8859-1 -*-

# Copyright 2003, 2004 University of Oslo, Norway
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

import re
import sys
import base64
import getopt

import cerebrum_path
import cereconf
from Cerebrum.Utils import Factory, SimilarSizeWriter
from Cerebrum.modules import Email
from Cerebrum.modules.bofhd.utils import BofhdRequests
from Cerebrum.modules.LDIFutils import container_entry_string
from Cerebrum.Constants import _SpreadCode
from time import time as now

default_mail_file = "/cerebrum/dumps/LDAP/mail-db.ldif"
default_spam_level = 9999
default_spam_action = 0
mail_dn = cereconf.LDAP_MAIL_DN


def write_ldif():
    mail_targ = Email.EmailTarget(db)
    counter = 0
    curr = now()
    ldap.read_pending_moves()

    f.write(container_entry_string('MAIL'))

    for row in mail_targ.list_email_targets_ext():
        t = int(row['target_id'])
        if verbose > 1:
            print "Target_id: %d" % t
        if not ldap.targ2addr.has_key(t):
            # There are no addresses for this target; hence, no mail
            # can reach it.  Move on.
            if verbose > 1:
                print "No addresses for target. Moving on."
            continue

        tt = int(row['target_type'])
        et = row['entity_type']
        if et is not None:
            et = int(et)
        ei = row['entity_id']
        if ei is not None:
            ei = int(ei)
        alias = row['alias_value']
        run_as_id = row['using_uid']
        if run_as_id is not None:
            run_as_id = int(run_as_id)

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
            if verbose > 1:
                print "Target is co.email_target_account"
            target = ""
            home = ""
            if et == co.entity_account:
                if ldap.acc2name.has_key(ei):
                    target,home,path = ldap.acc2name[ei]
                    if not home:
                        home = "%s/%s" % (path, target)
                else:
                    txt = "Target: %s(account) no user found: %s\n"% (t,ei)
                    sys.stderr.write(txt)
                    continue
            else:
                txt = "Target: %s(account) wrong entity type: %s\n"% (t,ei)
                sys.stderr.write(txt)
                continue
            
            # Find quota-settings:
            if ldap.targ2quota.has_key(t):
                soft, hard = ldap.targ2quota[t]
                rest += "softQuota: %s\n" % soft
                rest += "hardQuota: %s\n" % hard

            # Find vacations-settings:
            if ldap.targ2vacation.has_key(t):
                txt, start, end, enable = ldap.targ2vacation[t]
                tmp = re.sub('\n', '', base64.encodestring(txt))
                rest += "tripnote:: %s\n" % tmp
                if enable:
                    rest += "tripnoteActive: TRUE\n"

            # See if e-mail delivery should be suspended
            if ei in ldap.pending:
                rest += "mailPause: TRUE\n"

            # Get server-attributes if any.
            rest += ldap.get_server_info(t, ei, home, path)

        elif tt == co.email_target_deleted:
            # Target type for addresses that are no longer working, but
            # for which it is useful to include of a short custom text in
            # the error message returned to the sender.  The text
            # is taken from email_target.alias_value
            if verbose > 1:
                print "Target is co.email_target_deleted"
            if et == co.entity_account:
                if ldap.acc2name.has_key(ei):
                    target = ldap.acc2name[ei][0]
            if alias:
                rest += "forwardDestination: %s\n" % alias

        
        elif tt == co.email_target_forward:
            # Target is a pure forwarding mechanism; local deliveries will
            # only occur as indirect deliveries to the addresses forwarded
            # to.  Both email_target.entity_id and email_target.alias_value
            # should be NULL, as they are ignored.  The email address(es)
            # to forward to is taken from table email_forward.
            if verbose > 1:
                print "Target is co.email_target_forward"
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
            
            if verbose > 1:
                print "Target is co.email_target_(pipe,file,Mailman)"
                
            if alias == None:
                txt = "Target: %s(%s) needs a value in alias_value\n" % (t, tt)
                sys.stderr.write(txt)
                continue

            rest += "target: %s\n" % alias

            if run_as_id is not None:
                if ldap.acc2name.has_key(run_as_id):
                    uid = ldap.acc2name[run_as_id][0]
                else:
                    txt = "Target: %s(%s) no user found: %s\n" % (t, tt, ei)
                    sys.stderr.write(txt)
                    continue

        elif tt == co.email_target_multi:
            # Target is the set of `account`-type targets corresponding to
            # the Accounts that are first-level members of the Group that
            # has group_id == email_target.entity_id.
            
            if verbose > 1:
                print "Target is co.email_target_multi"
                
            if et == co.entity_group:
                try:
                    addrs = ldap.read_multi_target(ei)
                except ValueError, exc:
                    txt = "Target: %s (%s) %s\n" % (t, tt, exc)
                    sys.stderr.write(txt)
                    continue
                for addr in addrs:
                    rest += "forwardDestination: %s\n" % addr
            else:
                # A 'multi' target with no forwarding; seems odd.
                txt = "Target: %s (%s) no forwarding found.\n" % (t, tt)
                sys.stderr.write(txt)
                continue 

        else:
            # The target-type isn't known to this script.
            sys.stderr.write("Wrong target-type in target: %s: %s\n" % ( t, tt ))
            continue

        f.write("dn: cn=d%s,%s\n" % (t, mail_dn))
        f.write("objectClass: mailAddr\n")
        f.write("cn: d%s\n" % t)
        f.write("targetType: %s\n" % ldap.get_targettype(tt))
        if target:
            # You may want to change the way targets appear.
            # Hence the call to ldap.get_target()
            f.write("target: %s\n" % ldap.get_target(ei,t))
        if uid:
            f.write("uid: %s\n" % uid)
        if rest:
            f.write(rest)
        
        # Find primary mail-address:
        if ldap.targ2prim.has_key(t):
            if ldap.aid2addr.has_key(ldap.targ2prim[t]):
                f.write("defaultMailAddress: %s\n" % ldap.aid2addr[ldap.targ2prim[t]])
            else:
                print "Strange: t: %d, targ2prim[t]: %d, but no aid2addr" % (
                    t, ldap.targ2prim[t])
            
        # Find addresses for target:
        for a in ldap.targ2addr[t]:
            f.write("mail: %s\n" % a)

        # Find forward-settings:
        if ldap.targ2forward.has_key(t):
            for addr,enable in ldap.targ2forward[t]:
                if enable == 'T':
                    f.write("forwardDestination: %s\n" % addr)

        if tt in (co.email_target_account, co.email_target_Mailman):
            # Find spam-settings:
            if ldap.targ2spam.has_key(t):
                level, action = ldap.targ2spam[t]
                f.write("spamLevel: %s\n" % level)
                f.write("spamAction: %s\n" % action)
            else:
                # Set default-settings.
                f.write("spamLevel: %s\n" % default_spam_level)
                f.write("spamAction: %s\n" % default_spam_action)

            # Find virus-setting:
            if ldap.targ2virus.has_key(t):
                found, rem, enable = ldap.targ2virus[t]
                f.write("virusFound: %s\n" % found)
                f.write("virusRemoved: %s\n" % rem)
                if enable == 'T':
                    f.write("virusScanning: TRUE\n")
                else:
                    f.write("virusScanning: FALSE\n")
            else:
                # Set default-settings.
                f.write("virusScanning: TRUE\n")
                f.write("virusFound: 1\n")
                f.write("virusRemoved: 1\n")        

        misc = ldap.get_misc(ei, t, tt)
        if misc:
            f.write("%s\n" % misc)
        f.write("\n")


def get_data(spread):
    start = now()

    if verbose:
        print "Starting read_prim()..."
        curr = now()
    ldap.read_prim()
    if verbose:
        print "  done in %d sec." % (now() - curr)       
        print "Starting read_virus()..."
        curr = now()
    ldap.read_virus()
    if verbose:
        print "  done in %d sec." % (now() - curr)
        print "Starting read_spam()..."
        curr = now()
    ldap.read_spam()
    if verbose:
        print "  done in %d sec." % (now() - curr)
        print "Starting read_quota()..."
        curr = now()
    ldap.read_quota()
    if verbose:
        print "  done in %d sec." % (now() - curr)
        print "Starting read_addr()..."
        curr = now()
    ldap.read_addr()
    if verbose:
        print "  done in %d sec." % (now() - curr)
        print "Starting read_server()..."
        curr = now()    
    ldap.read_server(spread)
    if verbose:
        print "  done in %d sec." % (now() - curr)
        print "Starting read_vacation()..."
        curr = now()    
    ldap.read_vacation()
    if verbose:
        print "  done in %d sec." % (now() - curr)
        print "Starting read_forward()..."
        curr = now()    
    ldap.read_forward()
    if verbose:
        print "  done in %d sec." % (now() - curr)
        print "Starting read_account()..."
        curr = now()    
    ldap.read_accounts(spread)
    if verbose:
        print "  done in %d sec." % (now() - curr)
        print "Starting read_misc()..."
        curr = now()
    ldap.read_misc_target()
    if verbose:
        print "  done in %d sec." % (now() - curr)
        print "Starting write_ldif()..."
        curr = now()
    write_ldif()
    if verbose:
        print "  done in %d sec." % (now() - curr)
        print "Total time: %d" % (now() - start)

    
def map_spread(id):
    try:
        return int(_SpreadCode(id))
    except Errors.NotFoundError:
        print "Error mapping %s" % id
        raise

def usage():
    print """
generate_mail_ldif.py -s|--spread <spread> [-h] [-v|--verbose]+ [-m|--mail-file <file>]
  -s|--spread <spread>: Targets printed found in spread.
  -v|--verbose: Shows some statistics.
  -m|--mail-file <file>: Specify file to write to.
  -i|--ignore-size: Use file class instead of SimilarSizeWriter.
  -h|--help: This message."""
    sys.exit(0)


def main():
    global verbose, f, db, co, ldap
    
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'vm:s:ih',
                                   ['verbose', 'mail-file=', 'spread=',
                                    'ignore-size', 'help'])
    except getopt.GetoptError:
        usage()

    db = Factory.get('Database')()
    _SpreadCode.sql = db   # TODO: provide a map-spread in Util.py
    co = Factory.get('Constants')(db)
    #ldap = EmailLDAP(db)
    ldap = Factory.get('EmailLDAP')(db)

    verbose = 0
    mail_file = default_mail_file
    spread = None
    ignore = False
    
    for opt, val in opts:
        if opt in ('-v', '--verbose'):
            verbose += 1
        elif opt in ('-m', '--mail-file'):
            mail_file = val
        elif opt in ('-s', '--spread'):
            spread = map_spread(val)
        elif opt in ('-i', '--ignore-size'):
            ignore = True
        elif opt in ('-h', '--help'):
            usage()

    if spread is None:
        raise ValueError, "Must set spread"
    if ignore:
        f = file(mail_file, 'w')
    else:
        f = SimilarSizeWriter(mail_file, 'w')	
	f.set_size_change_limit(10)
    get_data(spread)
    f.close()

if __name__ == '__main__':
    main()
