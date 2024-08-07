# -*- coding: utf-8 -*-
#
# Copyright 2014-2024 University of Oslo, Norway
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
""" Constants for the bofh guest module. """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import Cerebrum.Constants
from Cerebrum.modules.EntityTrait import _EntityTraitCode


class GuestConstants(Cerebrum.Constants.Constants):
    """ Guest constants. """

    account_guest = Cerebrum.Constants._AccountCode(
        'gjestebruker',
        'Gjestekonto',
    )

    trait_guest_owner = _EntityTraitCode(
        'guest_owner',
        Cerebrum.Constants.Constants.entity_account,
        "Trait for storing the entity_id that is responsible for a guest "
        "account. The trait is given to the guest account.",
    )

    trait_guest_name = _EntityTraitCode(
        'guest_name',
        Cerebrum.Constants.Constants.entity_account,
        "The full name of the user of the guest account. "
        "The trait is given to the guest account.",
    )

    # Quarantine is given on creation, but with a delayed start date.
    quarantine_guest_old = Cerebrum.Constants._QuarantineCode(
        'guest_old',
        'Expired guest account.',
    )
