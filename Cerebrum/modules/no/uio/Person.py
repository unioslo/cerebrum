# -*- coding: utf-8 -*-
# Copyright 2013-2014 University of Oslo, Norway
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

import cereconf
from Cerebrum import Person
from Cerebrum import Errors

class PersonUiOMixin(Person.Person):
    """Person mixin class providing functionality specific to UiO.

    The methods of the core Person class that are overridden here,
    ensure that any Person objects generated through
    Cerebrum.Utils.Factory.get() provide functionality that reflects
    the policies of the University of Oslo.
    """
    # check if a person has an electronic listing reservation
    def has_e_reservation(self):
        # this method may be applied to any Cerebrum-instances that
        # use trait_public_reservation
        r = self.get_trait(self.const.trait_public_reservation)
        if r and r['numval'] == 0:
            return False
        return True
