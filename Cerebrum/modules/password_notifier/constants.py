# -*- coding: utf-8 -*-
#
# Copyright 2016-2023 University of Oslo, Norway
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
Constants for the PasswordNotifier.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import Cerebrum.Constants
from Cerebrum.modules.EntityTrait import _EntityTraitCode


class Constants(Cerebrum.Constants.Constants):

    trait_passwordnotifier_excepted = _EntityTraitCode(
        'autopass_except',
        Cerebrum.Constants.Constants.entity_account,
        "Trait marking accounts whose password's change is not enforced "
        "by PasswordNotifier.",
    )

    trait_passwordnotifier_notifications = _EntityTraitCode(
        'pw_notifications',
        Cerebrum.Constants.Constants.entity_account,
        "Trait for PasswordNotifier's bookkeeping.",
    )

    trait_passwordnotifier_sms_notifications = _EntityTraitCode(
        'pw_sms_notificat',
        Cerebrum.Constants.Constants.entity_account,
        "Trait for bookkeeping number of SMSes sent by PasswordNotifier.",
    )
