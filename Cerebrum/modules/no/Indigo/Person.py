# -*- coding: iso-8859-1 -*-
# Copyright 2008 University of Oslo, Norway
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
import cereconf
from Cerebrum import Person

class PersonGiskeMixin(Person.Person):
    """Stop process_entity from adding person@ldap spread to people
       who are not registered as pupils or employees at Giske schools."""
    def add_spread(self, spread):
        #
        # Pre-add checks
        #
        fed_member = False
        affs = self.get_affiliations()

        if spread == self.const.spread_ldap_per:
            for a in affs:
                if a['affiliation'] in [self.const.affiliation_ansatt,
                                        self.const.affiliation_teacher,
                                        self.const.affiliation_elev]:
                    fed_member = True
                    break
            if not fed_member:
                ret = False
            else:
                # (Try to) perform the actual spread addition.
                ret = self.__super.add_spread(spread)
        return ret

