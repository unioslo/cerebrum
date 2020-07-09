# -*- coding: utf-8 -*-
#
# Copyright 2017-2020 University of Oslo, Norway
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
"""Mixin for contrib/no/uio/generate_randsone_ldif.py."""

from Cerebrum.modules.no.OrgLDIF import norEduLDIFMixin


class RandsoneOrgLdif(norEduLDIFMixin):  # noqa: N801

    def init_ou_structure(self):
        # Change from original: Drop OUs outside self.root_ou_id subtree.
        super(RandsoneOrgLdif, self).init_ou_structure()
        ous, tree = [self.root_ou_id], self.ou_tree
        for ou in ous:
            ous.extend(tree.get(ou, ()))
        self.ou_tree = dict((ou, tree[ou]) for ou in ous if ou in tree)

    def init_attr2id2contacts(self):
        self.attr2id2contacts = {}
        self.id2labeledURI = {}

    def init_person_titles(self):
        self.person_titles = {}

    def init_person_addresses(self):
        self.addr_info = {}
