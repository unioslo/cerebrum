# -*- coding: utf-8 -*-
# Copyright 2004-2019 University of Oslo, Norway
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
"""
PosixLDIF customization for UiT.
"""
from __future__ import unicode_literals

from Cerebrum.Utils import Factory
from Cerebrum.Utils import make_timer
from Cerebrum.modules import LDIFutils
from Cerebrum.modules.PosixLDIF import PosixLDIF


class PosixLDIF_UiTMixin(PosixLDIF):  # noqa: N801
    """PosixLDIF mixin class providing functionality specific to UiT."""

    def __init__(self, *rest, **kw):
        super(PosixLDIF_UiTMixin, self).__init__(*rest, **kw)

        # load person_id -> primary account_id
        account = Factory.get("Account")(self.db)
        self.pid2primary_aid = dict()
        for row in account.list_accounts_by_type(
                               primary_only=True,
                               account_spread=self.spread_d["user"][0]):
            self.pid2primary_aid[row["person_id"]] = row["account_id"]

    def user_ldif(self, filename=None, auth_meth=None):
        """Generate posix-user."""
        timer = make_timer(self.logger, 'Starting user_ldif...')
        self.init_user(auth_meth)
        f = LDIFutils.ldif_outfile('USER', filename, self.fd)
        # this line is the only reason for having this function here:
        self.generate_system_object(f)
        f.write(LDIFutils.container_entry_string('USER'))
        self.logger.debug("filter out quarantined accounts")
        self.logger.debug("only include accounts with spread: %r",
                          self.spread_d['user'])
        for row in self.posuser.list_extended_posix_users(
                self.user_auth,
                spread=self.spread_d['user'],
                include_quarantines=False):
            dn, entry = self.user_object(row)
            if dn:
                f.write(LDIFutils.entry_string(dn, entry, False))
                self.logger.warn("writing:%s - %s" % (dn, entry))
        LDIFutils.end_ldif_outfile('USER', f, self.fd)
        timer('... done user_ldif')

    def generate_system_object(self, outfile):
        """
        Add a system object. This is needed when we add users under it
        """
        entry = {'objectClass': ['top', 'uioUntypedObject']}
        self.ou_dn = "cn=system,dc=uit,dc=no"
        outfile.write(LDIFutils.entry_string(self.ou_dn, entry))

    def init_user(self, *args, **kwargs):
        # Prepare to include eduPersonAffiliation, taken from OrgLDIF.
        self.org_ldif = Factory.get('OrgLDIF')(self.db, self.logger)
        self.org_ldif.init_eduPersonAffiliation_lookup()
        self.steder = {}

        super(PosixLDIF_UiTMixin, self).init_user(*args, **kwargs)

        self.account_aff = account_aff = {}
        for arow in self.posuser.list_accounts_by_type():
            val = (arow['affiliation'], int(arow['ou_id']))
            account_id = int(arow['account_id'])
            if account_id in account_aff:
                account_aff[account_id].append(val)
            else:
                account_aff[account_id] = [val]

    def user_object(self, row):
        dn, entry = super(PosixLDIF_UiTMixin, self).user_object(row)

        if entry:
            # Skip if sito account.
            #
            # this should really be done using spreads, but since all accounts
            # have the same spread as the person object, we are unable to
            # filter out any single account (for those persons with multiple
            # accounts)
            #
            # uname = row['entity_name']
            # if len(uname) == 7:
            #     if uname[-1] == 's':
            #         self.logger.debug("filtering out account name=%r",
            #                           row['entity_name'])
            #         return None, None

            # Add displayName, norEduPersonLegalName and
            # objectClass: norEduPerson
            if 'displayName' in entry:
                entry['displayName'].extend(entry['cn'])
            else:
                entry['displayName'] = entry['cn']

            if 'norEduPersonLegalName' in entry:
                entry['norEduPersonLegalName'].extend(entry['cn'])
            else:
                entry['norEduPersonLegalName'] = entry['cn']

            entry['objectClass'].extend(('norEduPerson',))
        return dn, entry

    def update_user_entry(self, account_id, entry, row):
        # Add some additional attributes that are in use @ UiT

        # eduPersonAffiliation (taken from OrgLDIF)
        owner_id = int(row['owner_id'])
        added = self.org_ldif.affiliations.get(owner_id)
        if added:
            added = self.org_ldif.attr_unique(self.org_ldif.select_list(
                self.org_ldif.eduPersonAff_selector, owner_id, added))
            if added:
                entry['eduPersonAffiliation'] = added
        entry['objectClass'].append('eduPerson')

        return super(PosixLDIF_UiTMixin, self).update_user_entry(account_id,
                                                                 entry, row)

    def get_netgrp(self, triples, memgrp):

        if not (self.grp.has_spread(self.const.spread_ldap_group) and
                self.grp.has_spread(self.const.spread_uit_nis_ng)):
            return super(PosixLDIF_UiTMixin, self).get_netgrp(triples, memgrp)

        # IVR 2010-03-10: A number of groups at UiO (ansatt-* -- autogenerated
        # based on employment data) have people, rather than accounts as
        # members. However, in order to help vortex, we expand temporarily
        # these groups in such a fashion, that export to LDAP entails
        # remapping person_id to its primary user's id.

        # We deal with person members only here, and let the superclass
        # perform its magic on everything else.
        for row in self.grp.search_members(
                group_id=self.grp.entity_id,
                member_type=self.const.entity_person):
            person_id = row["member_id"]

            # This is a hack. When it fails, ignore it silently.
            if person_id not in self.pid2primary_aid:
                continue

            uname_id = int(self.pid2primary_aid[person_id])
            if self.get_name:
                uname = self.entity2name[uname_id]
            else:
                try:
                    uname = self.id2uname[uname_id]
                except:
                    self.logger.warn("Cache enabled but user id=%s not found",
                                     uname_id)
                    continue

            if uname_id in self._gmemb or "_" in uname:
                continue

            triples.append("(,%s,)" % uname)
            self._gmemb[uname_id] = True

        return super(PosixLDIF_UiTMixin, self).get_netgrp(triples, memgrp)
