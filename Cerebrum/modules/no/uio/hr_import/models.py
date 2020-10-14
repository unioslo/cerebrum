# -*- coding: utf-8 -*-
# Copyright 2020 University of Oslo, Norway
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
This module contains classes for holding information about a person from
an HR system.
"""
from Cerebrum.modules.hr_import import models as _base


class HRPerson(_base.HRPerson):
    """
    Main class for holding all information that Cerebrum should need
    about a person from an HR system
    """

    def __init__(self,
                 hr_id,
                 first_name,
                 last_name,
                 birth_date,
                 gender,
                 reserved):
        """
        :param str hr_id: The person's ID in the source system
        :param str first_name: First name of the person
        :param str last_name: Last name of the person
        :param date birth_date: Date the person was born
        :param str gender: Gender of the person ('M'/'F'/None)
        :param bool reserved: If the person is reserved from public display
        """
        super(HRPerson, self).__init__(
            hr_id=hr_id,
            first_name=first_name,
            last_name=last_name,
            birth_date=birth_date,
            gender=gender
        )
        self.reserved = reserved

        self.leader_groups = set()  # set of int (group ids)
