#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2016-2018 University of Oslo, Norway
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
"""Mixin for saving account passwords as GPG data."""

import base64
from six import text_type

from Cerebrum.Account import Account
from Cerebrum.modules.gpg.data import EntityGPGData


class AccountPasswordEncrypterMixin(Account, EntityGPGData):
    """Mixin for saving passwords as GPG data."""
    def set_password(self, plaintext):
        super(AccountPasswordEncrypterMixin, self).set_password(plaintext)
        assert isinstance(plaintext, text_type)
        plaintext = plaintext.encode('utf-8')
        self.remove_gpg_data_by_tag('password-base64')
        self.add_gpg_data('password-base64', base64.b64encode(plaintext))
        self.remove_gpg_data_by_tag('password')
        self.add_gpg_data('password', plaintext)
