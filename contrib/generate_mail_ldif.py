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

import re
import os
import time
import sys
import base64
import getopt
import string

import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum import Account
from Cerebrum import Disk
from Cerebrum import Group
from Cerebrum.Utils import Factory
from Cerebrum.modules import Email
from Cerebrum.modules.bofhd.utils import BofhdRequests
from time import time as now

db = Factory.get('Database')()
co = Factory.get('Constants')(db)
mail_dom = Email.EmailDomain(db)
mail_targ = Email.EmailTarget(db)
default_mail_file = "/cerebrum/dumps/LDAP/mail-db.ldif"

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
home2spool = {}
local_uio_domain = {}
base_dn = "dc=uio,dc=no"
db_tt2ldif_tt = {'account': 'user',
                 'forward': 'forwardAddress'}
spam_act2dig = {'noaction': 0,
                'spamfolder': 1,
                'dropspam':2}

def validate_primary(dom, prim):
    if prim in ['pat', 'mons', 'goggins', 'miss', 'smtp', 'mail-mx1',
                'mail-mx2', 'mail-mx3']:
        if local_uio_domain.has_key(dom):
            if verbose > 1:
                print "Domain '%s' has already been declared local " \
                      "-- strange..." % dom
        local_uio_domain[dom] = prim
    elif verbose > 1:
        print "Domain '%s' handles it's own email at '%s'." % (dom,prim)

def list_machines():
    disk = Disk.Disk(db)
    res = []
    pat = r'/([^/]+)/([^/]+)/'
    for d in disk.list():
        path = d['path']
        r = re.search(pat, path)
        res.append([r.group(1), r.group(2)])
    return res

def make_home2spool():
    spoolhost = {}
    cname_cache = {}
    curdom, lowpri, primary = "", "", ""
    no_uio = r'\.uio\.no'
    
    # Define domains in zone uio.no whose primary MX is one of our
    # mail servers as "local domains".
    cmd = "/local/bin/host -t mx -l uio.no. nissen.uio.no"
    out = os.popen(cmd)
    res = out.readlines()
    err = out.close()
    if err:
        raise RuntimeError, '%s: failed with exit code %d' % (cmd, err)

    pat = r'^(\S+) mail is handled by (\d+) (\S+)\.\n$'
    for line in res:
        m = re.search(pat, line)
        if m:
            dom = string.lower(m.group(1))
            pri = int(m.group(2))
            mx = string.lower(m.group(3))
            dom = re.sub(no_uio, '', dom)
            mx = re.sub(no_uio, '', mx)
            if not curdom:
                curdom = dom
            if curdom and curdom != dom:
                validate_primary(curdom, primary)
                curdom = dom
                lowpri, primary = "", ""
            if (not lowpri) or (pri < lowpri):
                lowpri, primary = pri, mx
            if int(pri) == 33:
                spoolhost[dom] = mx

    if curdom and primary:
        validate_primary(curdom, primary)

    # We have now defined all "proper" local domains (i.e. ones that
    # have explicit MX records).  We also want to accept mail for any
    # CNAME in the uio.no zone pointing to any of these local domains.

    cmd = "/local/bin/host -t cname -l uio.no. nissen.uio.no"
    out = os.popen(cmd)
    res = out.readlines()
    err = out.close()
    if err:
        raise RuntimeError, '%s: failed with exit code %d' % (cmd, err)

    pat = r'^(\S+) is an alias for (\S+)\.\n$'
    for line in res:
        m = re.search(pat, line)
        if m:
            alias, real = string.lower(m.group(1)), string.lower(m.group(2))
            alias = re.sub(no_uio, '', alias)
            real = re.sub(no_uio, '', real)
            if local_uio_domain.has_key(real):
                local_uio_domain[alias] = local_uio_domain[real]
            if spoolhost.has_key(real):
                spoolhost[alias] = spoolhost[real]

    # Define domains in zone ifi.uio.no whose primary MX is one of our
    # mail servers as "local domains".  Cache CNAMEs at the same time.

    cmd = "/local/bin/dig @bestemor.ifi.uio.no ifi.uio.no. axfr"
    out = os.popen(cmd)
    res = out.readlines()
    err = out.close()
    if err:
        raise RuntimeError, '%s: failed with exit code %d' % (cmd, err)

    pat = r'^(\S+)\.\s+\d+\s+IN\s+MX\s+(\d+)\s+(\S+)\.'
    pat2 = r'^(\S+)\.\s+\d+\s+IN\s+CNAME\s+(\S+)\.'
    for line in res:
        m = re.search(pat, line)
        if m:
            dom = string.lower(m.group(1))
            pri = int(m.group(2))
            mx = string.lower(m.group(3))
            dom = re.sub(no_uio, '', dom)
            mx = re.sub(no_uio, '', mx)
            if not curdom:
                curdom = dom
            if curdom and curdom != dom:
                validate_primary(curdom, primary)
                curdom = dom
                lowpri, primary = "", ""
            if (not lowpri) or (pri < lowpri):
                lowpri, primary = pri, mx
            if pri == 33:
                spoolhost[dom] = mx
        else:
            m = re.search(pat2, line)
            if m:
                alias = string.lower(m.group(1))
                real = string.lower(m.group(2))
                alias = re.sub(no_uio, '', alias)
                real = re.sub(no_uio, '', real)
                cname_cache[alias] = real

    if curdom and primary:
        validate_primary(curdom, primary)

    # Define CNAMEs for domains whose primary MX is one of our mail
    # servers as "local domains".

    for alias in cname_cache.keys():
        real = cname_cache[alias]
        if local_uio_domain.has_key(real):
            local_uio_domain[alias] = local_uio_domain[real]
        if spoolhost.has_key(real):
            spoolhost[alias] = spoolhost[real]

    for faculty, host in list_machines():
        host = string.lower(host)
        if host == '*':
            continue
        if faculty == "ifi":
            if verbose > 1 and spoolhost.has_key(host):
                print "MX 33 of host %s.ifi implies spoolhost %s, ignoring." % (
                    host, spoolhost[host])
            spoolhost[host] = "ulrik"
            continue
        elif not spoolhost.has_key(host):
            if verbose > 1:
                print "Host '%s' defined in UREG2000, but has no MX" \
                      "-- skipping..." % host
            continue
        if spoolhost[host] == "ulrik":
            continue
        home2spool["/%s/%s" % (faculty, host)] = "/%s/%s/mail" % (
            faculty, spoolhost[host])

_translate_domains = {'UIO_HOST': 'ulrik.uio.no',
                      }
def _build_addr(local_part, domain):
    domain = _translate_domains.get(domain, domain)
    return '@'.join((local_part, domain))

def read_addr():
    counter = 0
    curr = now()
    mail_addr = Email.EmailAddress(db)
    # Handle "magic" domains.
    #   local_part@magic_domain
    # defines
    #   local_part@[all domains with category magic_domains],
    # overriding any entry for that local_part in any of those
    # domains.
    glob_addr = {}
    for dom_catg in (co.email_domain_category_uio_globals,):
        domain = str(dom_catg)
        lp_dict = {}
        glob_addr[domain] = lp_dict
        # Fill glob_addr[magic domain][local_part]
        for row in mail_addr.list_email_addresses_ext(domain):
            lp_dict[row['local_part']] = row
        for row in mail_dom.list_email_domains_with_category(dom_catg):
            # Alias glob_addr[domain name] to glob_addr[magic domain],
            # for later "was local_part@domain overridden" check.
            glob_addr[row['domain']] = lp_dict
            # Update dicts 'targ2addr' and 'aid2addr' with the
            # override addresses.
            for lp, row2 in lp_dict.items():
                # Use 'row', and not 'row2', for domain.  Using 'dom2'
                # would give us 'UIO_GLOBALS'.
                addr = _build_addr(lp, row['domain'])
                t_id = int(row2['target_id'])
                targ2addr.setdefault(t_id, []).append(addr)
                # Note: We don't need to update aid2addr here, as
                # addresses @UIO_GLOBALS aren't allowed to be primary
                # addresses.
    for row in mail_addr.list_email_addresses_ext():
        lp, dom = row['local_part'], row['domain']
        # If this address is in a domain that is subject to overrides
        # from "magic" domains, and the local_part was overridden, skip
        # this row.
        if glob_addr.has_key(dom) and glob_addr[dom].has_key(lp):
            continue
        counter += 1
        if verbose and (counter % 10000) == 0:
            print "  done %d list_email_addresses_ext(): %d sec." % (
                counter, now() - curr)
        addr = _build_addr(lp, dom)
        a_id, t_id = [int(row[x]) for x in ('address_id', 'target_id')]
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
        counter += 1
        if  verbose and (counter % 10000) == 0:
            print "  done %d list_email_spam_filters_ext(): %d sec." % (
                counter, now() - curr)
        targ2spam[int(row['target_id'])] = [row['level'],
                                            spam_act2dig.get(row['code_str'], 0)]

def read_quota():
    counter = 0
    curr = now()
    mail_quota = Email.EmailQuota(db)
    for row in mail_quota.list_email_quota_ext():
        counter += 1
        if  verbose and (counter % 10000) == 0:
            print "  done %d list_email_quota_ext(): %d sec." % (
                counter, now() - curr)
        targ2quota[int(row['target_id'])] = [row['quota_soft'],
                                             row['quota_hard']]
        
def read_virus():
    counter = 0
    curr = now()
    mail_virus = Email.EmailVirusScan(db)
    for row in mail_virus.list_email_virus_ext():
        counter += 1
        if  verbose and (counter % 10000) == 0:
            print "  done %d list_email_virus_ext(): %d sec." % (
                counter, now() - curr)
        targ2virus[int(row['target_id'])] = [row['found_str'],
                                             row['removed_str'],
                                             row['enable']]

def read_server():
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
        targ2forward.setdefault(int(row['target_id']),
                                []).append([row['forward_to'],
                                            row['enable']])

def read_vacation():
    mail_vaca = Email.EmailVacation(db)
    cur = db.DateFromTicks(time.time())
    def prefer_row(row, oldval):
        o_txt, o_sdate, o_edate, o_enable = oldval
        txt, sdate, edate, enable = [row[x]
                                     for x in ('vacation_text', 'start_date',
                                               'end_date', 'enable')]
        spans_now = (sdate <= cur and (edate is None or edate >= cur))
        o_spans_now = (o_sdate <= cur and (o_edate is None or o_edate >= cur))
        row_is_newer = sdate > o_sdate
        if spans_now:
            if enable == 'T' and o_enable == 'F': return True
            elif enable == 'T' and o_enable == 'T':
                if o_spans_now:
                    return row_is_newer
                else: return True
            elif enable == 'F' and o_enable == 'T':
                if o_spans_now: return False
                else: return True
            else:
                if o_spans_now: return row_is_newer
                else: return True
        else:
            if o_spans_now: return False
            else: return row_is_newer

    for row in mail_vaca.list_email_vacations():
        t_id = int(row['target_id'])
        insert = False
        if targ2vacation.has_key(t_id):
            if prefer_row(row, targ2vacation[t_id]):
                insert = True
        else:
            insert = True
        if insert:
            # Make sure vacations that doesn't span now aren't marked
            # as active, even though they might be registered as
            # 'enabled' in the database.
            enable = False
            if row['start_date'] <= cur and (row['end_date'] is None
                                             or row['end_date'] >= cur):
                enable = (row['enable'] == 'T')
            targ2vacation[t_id] = (row['vacation_text'],
                                   row['start_date'],
                                   row['end_date'],
                                   enable)

def read_accounts():
    acc = Account.Account(db)
    for row in acc.list_account_name_home():
        acc2name[int(row['account_id'])] = [row['entity_name'],
                                            row['home'],
                                            row['path']]

def read_pending_moves():
    br = BofhdRequests(db, co)
    pending = {}
    for r in br.get_requests(operation=co.bofh_email_will_move):
        pending[int(r['entity_id'])] = True
    for r in br.get_requests(operation=co.bofh_email_move):
        pending[int(r['entity_id'])] = True
    return pending

def read_multi_target(group_id):
    grp = Factory.get('Group')(db)
    grp.clear()
    try:
        grp.find(group_id)
    except Errors.NotFoundError:
        raise ValueError, "no group found: %d" % group_id
    u, i, d = grp.list_members()
    if i or d:
        raise ValueError, "group has non-union members: %d" % group_id
    # Iterate over group's union members
    member_addrs = []
    for member_type, member_id in u:
        if member_type <> co.entity_account:
            continue
        # Verify that the user has its own email target.
        mail_targ.clear()
        try:
            mail_targ.find_by_email_target_attrs(
                target_type = co.email_target_account,
                entity_id = member_id)
        except Errors.NotFoundError:
            raise ValueError, "no target for group member: %d" % member_id
        targ_id = int(mail_targ.email_target_id)
        if not targ2addr.has_key(targ_id):
            continue
        addrs = targ2addr[targ_id][:]
        addrs.sort()
        member_addrs.append(addrs[0])
    return member_addrs

def write_ldif():
    counter = 0
    curr = now()
    pending_move = read_pending_moves()

    f.write("""
dn: ou=mail,%s
objectClass: top
objectClass: norOrganizationalUnit
ou: mail
description: mail-config ved UiO.\n
""" % base_dn)

    for row in mail_targ.list_email_targets_ext():
        t = int(row['target_id'])

        if not targ2addr.has_key(t):
            # There are no addresses for this target; hence, no mail
            # can reach it.  Move on.
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
            target = ""
            home = ""
            if et == co.entity_account:
                if acc2name.has_key(ei):
                    target,home,path = acc2name[ei]
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
            if targ2quota.has_key(t):
                soft, hard = targ2quota[t]
                rest += "softQuota: %s\n" % soft
                rest += "hardQuota: %s\n" % hard

            # Find vacations-settings:
            if targ2vacation.has_key(t):
                txt, start, end, enable = targ2vacation[t]
                tmp = re.sub('\n', '', base64.encodestring(txt))
                rest += "tripnote:: %s\n" % tmp
                if enable:
                    rest += "tripnoteActive: TRUE\n"

            # See if e-mail delivery should be suspended
            if ei in pending_move:
                rest += "mailPause: TRUE\n"

            # Find mail-server settings:
            if targ2server_id.has_key(t):
                type, name = serv_id2server[int(targ2server_id[t])]
                if type == co.email_server_type_nfsmbox:
                    maildrop = "/uio/mailspool/mail"
                    tmphome = "/hom/%s" % target
                    r = re.search(r'^(/[^/]+/[^/]+)/', home)
                    if r:
                        tmphome = r.group(1)
                        if home2spool.has_key(tmphome):
                            maildrop = home2spool[tmphome]
                    rest += "spoolInfo: home=%s maildrop=%s/%s\n" % (
                        home, maildrop, target)
                elif type == co.email_server_type_cyrus:
                    rest += "IMAPserver: %s\n" % name

        elif tt == co.email_target_deleted:
            # Target type for addresses that are no longer working, but
            # for which it is useful to include of a short custom text in
            # the error message returned to the sender.  The text
            # is taken from email_target.alias_value
            if et == co.entity_account:
                if acc2name.has_key(ei):
                    target = acc2name[ei][0]
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

            if run_as_id is not None:
                if acc2name.has_key(run_as_id):
                    uid = acc2name[run_as_id][0]
                else:
                    txt = "Target: %s(%s) no user found: %s\n" % (t, tt, ei)
                    sys.stderr.write(txt)
                    continue

        elif tt == co.email_target_multi:
            # Target is the set of `account`-type targets corresponding to
            # the Accounts that are first-level members of the Group that
            # has group_id == email_target.entity_id.
            if et == co.entity_group:
                try:
                    addrs = read_multi_target(ei)
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

        f.write("dn: cn=d%s,ou=mail,%s\n" % (t, base_dn))
        f.write("objectClass: mailAddr\n")
        f.write("cn: d%s\n" % t)
        f.write("targetType: %s\n" % db_tt2ldif_tt.get(str(tt), str(tt)))
        if target:
            f.write("target: %s\n" % target)
        if uid:
            f.write("uid: %s\n" % uid)
        if rest:
            f.write(rest)
        
        # Find primary mail-address:
        if targ2prim.has_key(t):
            if aid2addr.has_key(targ2prim[t]):
                f.write("defaultMailAddress: %s\n" % aid2addr[targ2prim[t]])
            else:
                print "Strange: t: %d, targ2prim[t]: %d, but no aid2addr" % (
                    t, targ2prim[t])
            
        # Find addresses for target:
        for a in targ2addr[t]:
            f.write("mail: %s\n" % a)

        # Find forward-settings:
        if targ2forward.has_key(t):
            for addr,enable in targ2forward[t]:
                if enable == 'T':
                    f.write("forwardDestination: %s\n" % addr)

        if tt in (co.email_target_account, co.email_target_Mailman):
            # Find spam-settings:
            if targ2spam.has_key(t):
                level, action = targ2spam[t]
                f.write("spamLevel: %d\n" % level)
                f.write("spamAction: %d\n" % action)
            else:
                # Set default-settings.
                f.write("spamLevel: 9999\n")
                f.write("spamAction: 0\n")

            # Find virus-setting:
            if targ2virus.has_key(t):
                found, rem, enable = targ2virus[t]
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
        print "Starting make_home2spool()..."
        curr = now()
    make_home2spool()
    if verbose:
        print "  done in %d sec." % (now() - curr)
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
        print "Starting read_server()..."
        curr = now()    
    read_server()
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
