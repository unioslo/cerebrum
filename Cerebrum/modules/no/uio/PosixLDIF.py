# -*- coding: iso-8859-1 -*-
# Copyright 2004 University of Oslo, Norway
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

class SambaMixin(PosixLDIF):
    """
    Mixin class for sambaAccount. 
    Only partial sambaAccount to suppport NT-password used for freeradius 
    """

    def auth_methods(self, auth_meth= None):
	meth = self.__super.auth_methods(auth_meth)
	#meth = super(UserLdif, self).auth_methods() or []
	meth.append(int(self.const.auth_type_md4_nt))
	return meth

    def update_user_entry(self, account_id, entry, row):
	try:
	    hash = self.auth_data[account_id][int(self.const.auth_type_md4_nt)]
	except KeyError:
	    pass
        else:
	    entry['sambaNTPassword'] = (hash,)
	    entry['objectClass'].append('sambaSamAccount')
	    entry['sambaSID'] = entry['uidNumber']
	return self.__super.update_user_entry(account_id,entry, row)

