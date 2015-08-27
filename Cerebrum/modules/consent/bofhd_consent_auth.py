#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2015 University of Oslo, Norway
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

""" This is an auth module for use with bofhd_consent_cmds.

This module controls access to the guest commands.
"""
import cerebrum_path

import cereconf
import guestconfig

from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd import auth
from Cerebrum.modules.bofhd.errors import PermissionDenied


class BofhdAuth(auth.BofhdAuth):
    """ Methods to control command access. """

    def can_create_consent(self, operator, entity):
        """
        """
        pass

    def can_remove_consent(self, operator, entity):
        """
        """
        pass

    def can_do_consent_info(self, operator, entity):
        """
        """
        pass

    def can_list_consents(self, operator):
        """
        """
        pass
