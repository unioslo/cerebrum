#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2016 University of Oslo, Norway
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
"""Constants for the PasswordNotifier."""

from Cerebrum import Constants as _c
from Cerebrum.modules.EntityTrait import _EntityTraitCode


class Constants(_c.Constants):
    """
    Constants used by PasswordNotifier
    """
    trait_passwordnotifier_excepted = _EntityTraitCode(
        'autopass_except',
        _c.Constants.entity_account,
        "Trait marking accounts whose password's change is not enforced "
        "by PasswordNotifier.")

    trait_passwordnotifier_notifications = _EntityTraitCode(
        'pw_notifications',
        _c.Constants.entity_account,
        "Trait for PasswordNotifier's bookkeeping.")

    trait_passwordnotifier_sms_notifications = _EntityTraitCode(
        'pw_sms_notificat',
        _c.Constants.entity_account,
        "Trait for bookkeeping number of SMSes sent by PasswordNotifier.")
