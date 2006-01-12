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
from Cerebrum.Utils import Factory

class PosixLDIF_UiOMixin(PosixLDIF):
    """PosixLDIF mixin class providing functionality specific to UiO."""

    def init_user(self, *args, **kwargs):
	# Prepare to include eduPersonAffiliation, taken from OrgLDIF.
	self.org_ldif = Factory.get('OrgLDIF')(self.db, self.logger)
	self.org_ldif.init_eduPersonAffiliation_lookup()
	return self.__super.init_user(*args, **kwargs)

    def auth_methods(self, auth_meth= None):
	# Also fetch NT password, for attribute sambaNTPassword.
	meth = self.__super.auth_methods(auth_meth)
	meth.append(int(self.const.auth_type_md4_nt))
	return meth

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

	# sambaNTPassword (used by FreeRadius)
	try:
	    hash = self.auth_data[account_id][int(self.const.auth_type_md4_nt)]
	except KeyError:
	    pass
	else:
	    entry['sambaNTPassword'] = (hash,)
	    # TODO: Remove sambaSamAccount and sambaSID after Radius-testing
	    entry['objectClass'].append('sambaSamAccount')
	    entry['sambaSID'] = entry['uidNumber']
	    added = True

	# Object class which allows the additional attributes
	if added:
	    entry['objectClass'].append('uioAccountObject')
	return self.__super.update_user_entry(account_id,entry, row)

# arch-tag: e2f10a69-807b-4b18-8893-530a4cae1a38
