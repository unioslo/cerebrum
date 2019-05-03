# -*- coding: utf-8 -*-
# Copyright 2013 University of Oslo, Norway
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
from collections import defaultdict
from os.path import join as join_paths

from Cerebrum.modules.no.OrgLDIF import *


class OrgLDIFUiTMixin(OrgLDIF):
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
        sap, fs = self.const.system_sap, self.const.system_fs
        c = [(a, self.get_contacts(contact_type=t,
                                   source_system=s,
                                   convert=self.attr2syntax[a][0],
                                   verify=self.attr2syntax[a][1],
                                   normalize=self.attr2syntax[a][2]))
             for a, s, t in (('mobile', fs, self.const.contact_mobile_phone),)]
        self.attr2id2contacts.extend((v for v in c if v[1]))

    def update_org_object_entry(self, entry):
        # Changes from superclass:
        # Add attributes needed by UiT.
        self.__super.update_org_object_entry(entry)

        if 'o' in entry:
            entry['o'].append(['UiT The Artcic University of Norway',
                               'UiT Norges Arktiske Universitet'])
        else:
            entry['o'] = (
                ['University of Tromsoe', 'UiT Norges Arktiske Universitet'])

        if 'eduOrgLegalName' in entry:
            entry['eduOrgLegalName'].append([
                'UiT Norges Arktiske Universitet',
                'UiT The Artcic University of Norway'])
        else:
            entry['eduOrgLegalName'] = ([
                'UiT Norges Arktiske Universitet',
                'UiT The Artcic University of Norway'])

        entry['norEduOrgNIN'] = (['NO970422528'])
        entry['mail'] = (['postmottak@uit.no'])

    def update_ou_entry(self, entry):
        # Changes from superclass:
        # Add object class norEduOrg and its attr norEduOrgUniqueIdentifier
        entry['objectClass'].append('norEduOrg')
        entry['norEduOrgUniqueIdentifier'] = self.norEduOrgUniqueID

        # ?? Are these needed?
        # entry['objectClass'].append('eduOrg')
        # entry['objectClass'].append('norEduObsolete')

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
        acc_names = self.acc_name.copy()
        for account_id in acc_names:
            self.logger.debug("processing account:%s" % acc_names[account_id])
            if len(acc_names[account_id]) == 7:
                if acc_names[account_id][-1] == 's':
                    self.logger.debug(
                        "filtering out account:%s" % acc_names[account_id])
                    self.acc_name.pop(account_id)
                    self.account_auth.pop(account_id)
        del acc_names

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
        # home or work address set it to empty string
        #
        entry['postalAddress'] = ''

        return dn, entry, alias_info
