# -*- coding: iso-8859-1 -*-

# Copyright 2004, 2005 University of Oslo, Norway
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

import SpineClient

def get_persons(tr, const):
    search = SpineClient.Search(tr)

    full = search.person_name('full_name', name_variant=const.full_name, source_system=const.source_system)
    first = search.person_name('first_name', name_variant=const.first_name, source_system=const.source_system)
    last = search.person_name('last_name', name_variant=const.last_name, source_system=const.source_system)
    persons = search.person('person')

    persons.add_join('', full, 'person')
    persons.add_join('', first, 'person')
    persons.add_join('', last, 'person')

    if const.person_spread is not None:
        entityspreads = search.entity_spread('spread', spread=const.person_spread, entity_type=const.person_type)
        persons.add_join('', entityspreads, 'entity')

    persons.order_by(last, 'name')

    return search.dump(persons)

# arch-tag: 905ae11c-47f8-11da-941a-0c642470d9b5
