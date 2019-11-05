# -*- coding: utf-8 -*-
# Copyright 2013-2019 University of Oslo, Norway
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

# kbj005 2015.02.16: copied from
# /cerebrum/lib/python2.7/site-packages/Cerebrum/modules/no/hih
"""Mixin for OrgLDIF for UiT."""
from __future__ import unicode_literals

import pickle
from os.path import join as join_paths

import cereconf
from Cerebrum.Utils import make_timer
from Cerebrum.modules.LDIFutils import ldapconf
from Cerebrum.modules.no.OrgLDIF import norEduLDIFMixin

from .Account import UsernamePolicy


class OrgLDIFUiTMixin(norEduLDIFMixin):

    def __init__(self, db, logger):
        self.__super.__init__(db, logger)
        self.attr2syntax['mobile'] = self.attr2syntax['telephoneNumber']

    def init_person_course(self):
        """Populate dicts with a person's course information."""
        timer = make_timer(self.logger, "Processing person courses...")
        self.ownerid2urnlist = pickle.load(file(
            join_paths(ldapconf(None, 'dump_dir'), "ownerid2urnlist.pickle")))
        timer("...person courses done.")

    def init_person_groups(self):
        """Populate dicts with a person's group information."""
        timer = make_timer(self.logger, "Processing person groups...")
        self.person2group = pickle.load(file(
            join_paths(ldapconf(None, 'dump_dir'), "personid2group.pickle")))
        timer("...person groups done.")

    def init_person_dump(self, use_mail_module):
        """Suplement the list of things to run before printing the
        list of people."""
        self.__super.init_person_dump(use_mail_module)
        self.init_person_course()
        self.init_person_groups()

    def init_attr2id2contacts(self):
        """Override to include more, local data from contact info."""
        self.__super.init_attr2id2contacts()
        fs = self.const.system_fs
        c = [(a, self.get_contacts(contact_type=t,
                                   source_system=s,
                                   convert=self.attr2syntax[a][0],
                                   verify=self.attr2syntax[a][1],
                                   normalize=self.attr2syntax[a][2]))
             for a, s, t in (('mobile', fs, self.const.contact_mobile_phone),)]
        self.attr2id2contacts.extend((v for v in c if v[1]))

    #
    # override of OrgLDIF.init_ou_structure() with filtering of expired ous
    #
    def init_ou_structure(self):
        # Set self.ou_tree = dict {parent ou_id: [child ou_id, ...]}
        # where the root OUs have parent id None.
        timer = make_timer(self.logger, "Fetching OU tree...")
        self.ou.clear()
        ou_list = self.ou.get_structure_mappings(
            self.const.OUPerspective(cereconf.LDAP_OU['perspective']),
            filter_expired=True)
        self.logger.debug("OU-list length: %d", len(ou_list))
        self.ou_tree = {None: []}  # {parent ou_id or None: [child ou_id...]}
        for ou_id, parent_id in ou_list:
            if parent_id is not None:
                parent_id = int(parent_id)
            self.ou_tree.setdefault(parent_id, []).append(int(ou_id))
        timer("...OU tree done.")

    def init_account_info(self):
        super(OrgLDIFUiTMixin, self).init_account_info()

        # Filter out sito accounts
        for account_id in tuple(self.acc_name):
            name = self.acc_name[account_id]
            self.logger.debug("processing account: %r (%s)", account_id, name)
            if UsernamePolicy.is_valid_sito_name(name):
                self.logger.debug("filtering out account %r (%s)",
                                  account_id, name)
                self.acc_name.pop(account_id)

    def make_person_entry(self, row, person_id):
        """ Extend with UiO functionality. """
        dn, entry, alias_info = self.__super.make_person_entry(row, person_id)
        if not dn:
            return dn, entry, alias_info

        # Add group memberships
        self.logger.debug("get group memberships")
        if person_id in self.person2group:
            self.logger.debug(
                "appending uioMemberOf:%s" % self.person2group[person_id])
            entry['member'] = self.person2group[person_id]
            entry['objectClass'].extend((['uitMembership']))

        #
        # UiT does not wish to populate the postalAddress field with either
        # home or work address. Remove it if set by super.
        #
        entry.pop('postalAddress', None)

        return dn, entry, alias_info
