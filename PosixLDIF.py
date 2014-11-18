# -*- coding: iso-8859-1 -*-
# Copyright 2004-2014 University of Oslo, Norway
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

from Cerebrum.modules.PosixLDIF import PosixLDIF
from Cerebrum.modules.no.uit.printer_quota import PaidPrinterQuotas
from Cerebrum.QuarantineHandler import QuarantineHandler
from Cerebrum.Utils import Factory

class PosixLDIF_UiOMixin(PosixLDIF):
    """PosixLDIF mixin class providing functionality specific to UiO."""


    def __init__(self, *rest, **kw):
        super(PosixLDIF_UiOMixin, self).__init__(*rest, **kw)

        # load person_id -> primary account_id
        account = Factory.get("Account")(self.db)
        self.pid2primary_aid = dict()
        for row in account.list_accounts_by_type(
                               primary_only=True,
                               account_spread=self.spread_d["user"][0]):
            self.pid2primary_aid[row["person_id"]] = row["account_id"]
    # end __init__
    

    def init_user(self, *args, **kwargs):
	# Prepare to include eduPersonAffiliation, taken from OrgLDIF.
	self.org_ldif = Factory.get('OrgLDIF')(self.db, self.logger)
	self.org_ldif.init_eduPersonAffiliation_lookup()
	self.steder = {}
	self.__super.init_user(*args, **kwargs)

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
            for row in PaidPrinterQuotas.PaidPrinterQuotas(self.db).list()
            if row['has_quota'] == 'T')

    def id2stedkode(self, ou_id):
	try:
	    return self.steder[ou_id]
	except KeyError:
	    ou = self.org_ldif.ou
	    ou.clear()
	    try:
		ou.find(ou_id)
	    except Errors.NotFoundError:
		raise CerebrumError, "Stedkode unknown for ou_id %d" % ou_id
	    ret = self.steder[ou_id] = \
		  "%02d%02d%02d" % (ou.fakultet, ou.institutt, ou.avdeling)
	    return ret

    def update_user_entry(self, account_id, entry, row):
	# Add some additional attributes that are in use @ UiO

	# eduPersonAffiliation (taken from OrgLDIF)
	owner_id = int(row['owner_id'])
	added = self.org_ldif.affiliations.get(owner_id)
	if added:
	    added = self.org_ldif.attr_unique(self.org_ldif.select_list(
		self.org_ldif.eduPersonAff_selector, owner_id, added))
	    if added:
		entry['eduPersonAffiliation'] = added

        # uitAffiliation, uitPrimaryAffiliation
        affs = ["%s@%s" % ((self.const.PersonAffiliation(arow[0]),
                            self.id2stedkode(arow[1])))
                for arow in self.account_aff.get(account_id, ())]
        if affs:
            entry['uitAffiliation'] = affs
            entry['uitPrimaryAffiliation'] = (affs[0],)
            added = True

        # Add owner_id to the entry, but only if the owner is a person
        # We can simply reuse pid2primary_aid dictionary, that contains
        # all persons with primary accounts
        if (owner_id in self.pid2primary_aid):
  	    entry['uitPersonID'] = str(owner_id)
            added = True

        # People with printer quotas.
        if owner_id in self.pq_people:
            entry['uitHasPrinterQuota'] = "TRUE"
            added = True

	# Object class which allows the additional attributes
	if added:
	    entry['objectClass'].append('uitAccountObject')
	return self.__super.update_user_entry(account_id,entry, row)



    def get_netgrp(self, triples, memgrp):

        if not (self.grp.has_spread(self.const.spread_ldap_group) and
                self.grp.has_spread(self.const.spread_uit_nis_ng)):
            return super(PosixLDIF_UiOMixin, self).get_netgrp(triples, memgrp)

        # IVR 2010-03-10: A number of groups at UiO (ansatt-* -- autogenerated
        # based on employment data) have people, rather than accounts as
        # members. However, in order to help vortex, we expand temporarily
        # these groups in such a fashion, that export to LDAP entails
        # remapping person_id to its primary user's id.

        # We deal with person members only here, and let the superclass
        # perform its magic on everything else.
        for row in self.grp.search_members(group_id=self.grp.entity_id,
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

        return super(PosixLDIF_UiOMixin, self).get_netgrp(triples, memgrp)
    # end get_netgrp
# end class PosixLDIF_UiOMixin
