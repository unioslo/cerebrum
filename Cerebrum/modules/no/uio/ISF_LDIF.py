# -*- coding: iso-8859-1 -*-
# Copyright 2012 University of Oslo, Norway
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

"""Mixin for contrib/no/uio/generate_isf_ldif.py."""

from Cerebrum.modules.no.OrgLDIF import norEduLDIFMixin

class ISS_LDIF(norEduLDIFMixin):
    def init_ou_structure(self):
        self.ou_tree = {self.root_ou_id: []}

    def uninit_ou_dump(self):
        # Change from original: Do not 'del self.ou_tree'
        del self.ou

    def list_persons(self):
        # Change from original: Include ou_id in arguments
        return self.account.list_accounts_by_type(
            ou_id         = self.root_ou_id,
            primary_only  = True,
            person_spread = self.person_spread)

    def init_attr2id2contacts(self):
        self.attr2id2contacts = {}
        self.id2labeledURI    = {}
    def init_person_titles(self):
        self.person_titles = {}
    def init_person_addresses(self):
        self.addr_info = {}
