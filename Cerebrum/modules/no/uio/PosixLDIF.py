# -*- coding: utf-8 -*-
# Copyright 2004-2018 University of Oslo, Norway
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

from __future__ import unicode_literals

import cereconf
from Cerebrum.modules.PosixLDIF import PosixLDIF
from Cerebrum.modules.no.uio.printer_quota import PaidPrinterQuotas
from Cerebrum.Errors import NotFoundError
from Cerebrum.Utils import Factory, make_timer


class PosixLDIF_UiOMixin(PosixLDIF):
    """PosixLDIF mixin class providing functionality specific to UiO."""

    def __init__(self, *rest, **kw):
        super(PosixLDIF_UiOMixin, self).__init__(*rest, **kw)
        timer = make_timer(self.logger, 'Initing PosixLDIF_UiOMixin...')

        # load person_id -> primary account_id
        account = Factory.get("Account")(self.db)
        self.pid2primary_aid = dict()
        for row in account.list_accounts_by_type(
                primary_only=True,
                account_spread=self.spread_d["user"][0]):
            self.pid2primary_aid[row["person_id"]] = row["account_id"]
        timer('... done initing PosixLDIF_UiOMixin')
        # handle exempt users
        self.pq_exempt_user_ids = set()
        if hasattr(cereconf, 'PQ_EXEMPT_GROUP'):
            try:
                self.grp.find_by_name(cereconf.PQ_EXEMPT_GROUP)
                for member in self.grp.search_members(
                        group_id=self.grp.entity_id,
                        member_type=(self.const.entity_account,
                                     self.const.entity_person),
                        indirect_members=True):
                    self.pq_exempt_user_ids.add(member['member_id'])
                self.grp.clear()
            except NotFoundError:
                self.logger.error(
                    'Could not find PQ_EXEMPT_GROUP "{group}"'.format(
                        group=cereconf.PQ_EXEMPT_GROUP))
            except Exception as e:
                # should not happen unless nonexisting group-name is specified
                self.logger.error(
                    'PQ_EXEMPT_GROUP defined in cereconf, but extracting '
                    'exempt users failed: {error}'.format(error=e))

    def init_user(self, *args, **kwargs):
        self.__super.init_user(*args, **kwargs)
        timer = make_timer(self.logger, 'Starting UiO init_user...')
        # Prepare to include eduPersonAffiliation, taken from OrgLDIF.
        self.org_ldif = Factory.get('OrgLDIF')(self.db, self.logger)
        self.org_ldif.init_eduPersonAffiliation_lookup()
        self.cache_id2stedkode()

        self.account_aff = account_aff = {}
        for arow in self.posuser.list_accounts_by_type():
            val = (arow['affiliation'], int(arow['ou_id']))
            account_id = int(arow['account_id'])
            if account_id in account_aff:
                account_aff[account_id].append(val)
            else:
                account_aff[account_id] = [val]

        self.pq_people = frozenset(
            int(row['person_id'])
            for row in PaidPrinterQuotas.PaidPrinterQuotas(self.db).list(
                    only_with_quota=True))
        timer('... done UiO init_user')

    def init_netgroup(self, *args, **kwargs):
        self.__super.init_netgroup(*args, **kwargs)
        timer = make_timer(self.logger, 'Starting UiO init_netgroup...')
        timer('... done UiO init_netgroup')

    def cache_id2stedkode(self):
        timer = make_timer(self.logger, 'Starting cache_id2stedkode...')
        self.id2stedkode = {}
        ou = Factory.get('OU')(self.db)
        for row in ou.get_stedkoder():
            self.id2stedkode[row['ou_id']] = "%02d%02d%02d" % \
                (row['fakultet'], row['institutt'], row['avdeling'])
        timer('... done cache_id2stedkode')

    def update_user_entry(self, account_id, entry, owner_id):
        # Add some additional attributes that are in use @ UiO

        # eduPersonAffiliation (taken from OrgLDIF)
        added = self.org_ldif.affiliations.get(owner_id)
        if added:
            added = self.org_ldif.attr_unique(self.org_ldif.select_list(
                self.org_ldif.eduPersonAff_selector, owner_id, added))
        if added:
            entry['eduPersonAffiliation'] = added

        # uioAffiliation, uioPrimaryAffiliation
        affs = ["%s@%s" % ((self.const.PersonAffiliation(arow[0]),
                            self.id2stedkode[arow[1]]))
                for arow in self.account_aff.get(account_id, ())]
        if affs:
            entry['uioAffiliation'] = affs
            entry['uioPrimaryAffiliation'] = (affs[0],)
            added = True

        # Add owner_id to the entry, but only if the owner is a person
        # We can simply reuse pid2primary_aid dictionary, that contains
        # all persons with primary accounts
        if owner_id in self.pid2primary_aid:
            entry['uioPersonID'] = str(owner_id)
            added = True

        # Handle exempt users and people with printer quotas. #
        if (
                account_id not in self.pq_exempt_user_ids and
                owner_id not in self.pq_exempt_user_ids and
                owner_id in self.pq_people
        ):
            entry['uioHasPrinterQuota'] = "TRUE"
            added = True

        # Object class which allows the additional attributes
        if added:
            entry['objectClass'].append('uioAccountObject')
        return self.__super.update_user_entry(account_id, entry, owner_id)

    def cache_group2persons(self):
        # IVR 2010-03-10: A number of groups at UiO (ansatt-* -- autogenerated
        # based on employment data) have people, rather than accounts as
        # members. However, in order to help vortex, we expand temporarily
        # these groups in such a fashion, that export to LDAP entails
        # remapping person_id to its primary user's id.
        timer = make_timer(self.logger, 'Starting UiO cache_group2persons...')
        ldapgroup = set()
        nisng = set()
        for row in self.grp.list_all_with_spread(
                spreads=self.const.spread_ldap_group):
            ldapgroup.add(int(row['entity_id']))
        for row in self.grp.list_all_with_spread(
                spreads=self.const.spread_uio_nis_ng):
            nisng.add(int(row['entity_id']))

        help_vortex_groups = ldapgroup & nisng

        for row in self.grp.search_members(
                group_id=help_vortex_groups,
                member_type=self.const.entity_person):
            person_id = row["member_id"]
            # This is a hack. When it fails, ignore it silently.
            if person_id not in self.pid2primary_aid:
                continue

            user_id = int(self.pid2primary_aid[person_id])
            self.group2persons[int(row['group_id'])].append(user_id)
        timer('... done UiO cache_group2persons')
