# -*- coding: iso-8859-1 -*-
# Copyright 2004-2006 University of Oslo, Norway
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
from Cerebrum.QuarantineHandler import QuarantineHandler
from Cerebrum.Utils import Factory

class PosixLDIF_UiOMixin(PosixLDIF):
    """PosixLDIF mixin class providing functionality specific to UiO."""

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
	# Add eduPersonAffiliation and sambaNTPassword

	# eduPersonAffiliation (taken from OrgLDIF)
	owner_id = int(row['owner_id'])
	added = self.org_ldif.affiliations.get(owner_id)
	if added:
	    added = self.org_ldif.attr_unique(self.org_ldif.select_list(
		self.org_ldif.eduPersonAff_selector, owner_id, added))
	    if added:
		entry['eduPersonAffiliation'] = added

        # uioAffiliation, uioPrimaryAffiliation
        affs = ["%s@%s" % ((self.const.PersonAffiliation(arow[0]),
                            self.id2stedkode(arow[1])))
                for arow in self.account_aff.get(account_id, ())]
        if affs:
            entry['uioAffiliation'] = affs
            entry['uioPrimaryAffiliation'] = (affs[0],)
            added = True

	# Object class which allows the additional attributes
	if added:
	    entry['objectClass'].append('uioAccountObject')
	return self.__super.update_user_entry(account_id,entry, row)

# arch-tag: e2f10a69-807b-4b18-8893-530a4cae1a38
