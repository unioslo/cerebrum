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

""""""

import os
import re
import sys
import string
import time

from Cerebrum.Utils import Factory
from Cerebrum.modules import Email
from Cerebrum.modules.EmailLDAP import EmailLDAP

class EmailLDAPUiOMixin(EmailLDAP):
    """Methods specific for UiO."""

    __write_attr__ = ('home2spool', 'local_uio_domain', 'e_id2passwd')

    def __init__(self, db):
        self.__super.__init__(db)
        self.local_uio_domain = {}
        self.home2spool = {}
        self.e_id2passwd = {}
        

    spam_act2dig = {'noaction':   '0',
                    'spamfolder': '1',
                    'dropspam':   '2'}
    db_tt2ldif_tt = {'account': 'user',
                     'forward': 'forwardAddress'}         
    _translate_domains = {'UIO_HOST': 'ulrik.uio.no',
                          }
    maildrop = "/uio/mailspool/mail"


    def get_targettype(self, targettype):
        return self.db_tt2ldif_tt.get(str(targettype), str(targettype))


    def get_server_info(self, target, entity, home, path):
        # Find mail-server settings:
        uname = self.acc2name[entity][0]
        sinfo = ""
        if self.targ2server_id.has_key(target):
            type, name = self.serv_id2server[int(self.targ2server_id[target])]
            if type == self.const.email_server_type_nfsmbox:
                # If no path; do not verify.
                if path:
                    r = re.search(r'^(/[^/]+)(/[^/]+)/', path)
                if (not path) or (r.group(1) in ("/local", "/ifi")):
                    maildrop = self.maildrop
                else:
                    if r:
                        path = "%s%s" % (r.group(1),r.group(2))
                    if self.home2spool.has_key(path):
                        maildrop = self.home2spool[path]
                    else:
                        raise RuntimeError, \
                              "No '%s' in home2spool. Error in DNS" % path
                sinfo += "spoolInfo: home=%s maildrop=%s/%s\n" % (
                    home, maildrop, uname)
            elif type == self.const.email_server_type_cyrus:
                sinfo += "IMAPserver: %s\n" % name
        return sinfo
    

    def _build_addr(self, local_part, domain):
        domain = self._translate_domains.get(domain, domain)
        return '@'.join((local_part, domain))

    
    def read_server(self, spread):
        self.__super.read_server(spread)
        self.make_home2spool(spread)
        
  
    def list_machines(self, spread):
        disk = Factory.get('Disk')(self._db)
        res = []
        path_pattern = re.compile(r'/(?P<department>[^/]+)/(?P<host>[^/]+)/[^/]+')
        for d in disk.list(spread=spread):
            path = d['path']
            m = path_pattern.match(path)
            if m:
                res.append([m.group('department'), m.group('host')])
        return res


    def read_spam(self):
        mail_spam = Email.EmailSpamFilter(self._db)
        for row in mail_spam.list_email_spam_filters_ext():
            self.targ2spam[int(row['target_id'])] = [
                row['level'], self.spam_act2dig.get(row['code_str'], '0')]

    
    def read_addr(self):
        mail_dom = Email.EmailDomain(self._db)
        mail_addr = Email.EmailAddress(self._db)
        # Handle "magic" domains.
        #   local_part@magic_domain
        # defines
        #   local_part@[all domains with category magic_domains],
        # overriding any entry for that local_part in any of those
        # domains.
        glob_addr = {}
        for dom_catg in (self.const.email_domain_category_uio_globals,):
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
                    addr = self._build_addr(lp, row['domain'])
                    t_id = int(row2['target_id'])
                    self.targ2addr.setdefault(t_id, []).append(addr)
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
            addr = self._build_addr(lp, dom)
            a_id, t_id = [int(row[x]) for x in ('address_id', 'target_id')]
            self.targ2addr.setdefault(t_id, []).append(addr)
            self.aid2addr[a_id] = addr
            
                
    def _validate_primary(self, dom, prim, local_uio_domain):
        if prim in ['pat', 'mons', 'goggins', 'miss', 'smtp', 'mail-mx1',
                    'mail-mx2', 'mail-mx3']:
            self.local_uio_domain[dom] = prim


    def make_home2spool(self, spread):
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
                    self._validate_primary(curdom, primary, self.local_uio_domain)
                    curdom = dom
                    lowpri, primary = "", ""
                if (not lowpri) or (pri < lowpri):
                    lowpri, primary = pri, mx
                if int(pri) == 33:
                    spoolhost[dom] = mx
                    
        if curdom and primary:
            self._validate_primary(curdom, primary, self.local_uio_domain)

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
                if self.local_uio_domain.has_key(real):
                    self.local_uio_domain[alias] = self.local_uio_domain[real]
                if spoolhost.has_key(real):
                    spoolhost[alias] = spoolhost[real]

        # Define domains in zone ifi.uio.no whose primary MX is one of our
        # mail servers as "local domains".  Cache CNAMEs at the same time.

        # NB: ifi-kode tatt vekk. DNS-parsing er noe herk siden det ikke stemmer
        #     med hva ifi har av hjemmeområder.


        #no_uio_ifi = r'\.ifi\.uio\.no'
        #cmd = "/local/bin/dig @bestemor.ifi.uio.no ifi.uio.no. axfr"
        #out = os.popen(cmd)
        #res = out.readlines()
        #err = out.close()
        #if err:
        #    raise RuntimeError, '%s: failed with exit code %d' % (cmd, err)

        #pat = r'^(\S+)\.\s+\d+\s+IN\s+MX\s+(\d+)\s+(\S+)\.'
        #pat2 = r'^(\S+)\.\s+\d+\s+IN\s+CNAME\s+(\S+)\.'
        #for line in res:
        #    m = re.search(pat, line)
        #    if m:
        #        dom = string.lower(m.group(1))
        #        pri = int(m.group(2))
        #        mx = string.lower(m.group(3))
        #        dom = re.sub(no_uio_ifi, '', dom)
        #        mx = re.sub(no_uio, '', mx)
        #        if not curdom:
        #            curdom = dom
        #        if curdom and curdom != dom:
        #            self._validate_primary(curdom, primary, self.local_uio_domain)
        #            curdom = dom
        #            lowpri, primary = "", ""
        #        if (not lowpri) or (pri < lowpri):
        #            lowpri, primary = pri, mx
        #        if pri == 33:
        #            spoolhost[dom] = mx
        #    else:
        #        m = re.search(pat2, line)
        #        if m:
        #            alias = string.lower(m.group(1))
        #            real = string.lower(m.group(2))
        #            alias = re.sub(no_uio, '', alias)
        #            real = re.sub(no_uio, '', real)
        #            cname_cache[alias] = real

        #if curdom and primary:
        #    self._validate_primary(curdom, primary, self.local_uio_domain)

        # Define CNAMEs for domains whose primary MX is one of our mail
        # servers as "local domains".

        for alias in cname_cache.keys():
            real = cname_cache[alias]
            if self.local_uio_domain.has_key(real):
                self.local_uio_domain[alias] = self.local_uio_domain[real]
            if spoolhost.has_key(real):
                spoolhost[alias] = spoolhost[real]

        for faculty, host in self.list_machines(spread):
            host = string.lower(host)
            if host == '*':
                continue
            elif not spoolhost.has_key(host):
                continue
            if spoolhost[host] == "ulrik":
                self.home2spool["/%s/%s" % (faculty, host)] = self.maildrop
                continue
            self.home2spool["/%s/%s" % (faculty, host)] = "/%s/%s/mail" % (
                faculty, spoolhost[host])

    def read_misc_target(self):
        a = Factory.get('Account')(self._db)
        # For the time being, remove passwords for all quarantined
        # accounts, regardless of quarantine type.
        quarantines = {}
        now = self._db.DateFromTicks(time.time())
        for row in a.list_entity_quarantines(
                entity_types = self.const.entity_account):
            if (row['start_date'] <= now
                and (row['end_date'] is None or row['end_date'] >= now)
                and (row['disable_until'] is None
                     or row['disable_until'] < now)):
                # The quarantine in this row is currently active.
                quarantines[int(row['entity_id'])] = "*locked"
        for row in a.list_account_authentication():
            account_id = int(row['account_id'])
            self.e_id2passwd[account_id] = (
                row['entity_name'],
                quarantines.get(account_id) or row['auth_data'])
        for row in a.list_account_authentication(self.const.auth_type_crypt3_des):
            # *sigh* Special-cases do exist. If a user is created when the
            # above for-loop runs, this loop gets a row more. Before I ignored
            # this, and the whole thing went BOOM on me.
            account_id = int(row['account_id'])
            if not self.e_id2passwd.get(account_id, (0, 0))[1]:
                self.e_id2passwd[account_id] = (
                    row['entity_name'],
                    quarantines.get(account_id) or row['auth_data'])

    def get_misc(self, entity_id, target_id, email_target_type):
        if email_target_type == self.const.email_target_account:
            if self.e_id2passwd.has_key(entity_id):
                uname, passwd = self.e_id2passwd[entity_id]
                if not passwd:
                    passwd = "*invalid"
                txt = "uid: %s\nuserPassword: {crypt}%s" % (uname, passwd)
                return txt
            else:
                txt = "No auth-data for user: %s\n" % entity_id
                sys.stderr.write(txt)

# arch-tag: 7bb4c2b7-8112-4bd0-85dd-0112db222638
