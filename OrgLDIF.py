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

# kbj005 2015.02.16: copied from /cerebrum/lib/python2.7/site-packages/Cerebrum/modules/no/hih

"""Mixin for OrgLDIF for UiT."""

from collections import defaultdict
from os.path import join as join_paths
from Cerebrum.Utils import Factory
from Cerebrum.modules.no.OrgLDIF import *
from Cerebrum.modules.LDIFutils import *
from pprint import pprint
        
class OrgLDIFUiTMixin(OrgLDIF):
    def __init__(self, db, logger):
        self.__super.__init__(db, logger)
        self.attr2syntax['mobile'] = self.attr2syntax['telephoneNumber']

    def init_person_course(self):
        """Populate dicts with a person's course information."""
        timer = make_timer(self.logger,"Processing person courses...")
        self.ownerid2urnlist = pickle.load(file(
            join_paths(ldapconf(None, 'dump_dir'), "ownerid2urnlist.pickle")))
        timer("...person courses done.")
    
    def init_person_groups(self):
        """Populate dicts with a person's group information."""
        timer = make_timer(self.logger,"Processing person groups...")
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
        c = [(a, self.get_contacts(contact_type  = t,
                                   source_system = s,
                                   convert       = self.attr2syntax[a][0],
                                   verify        = self.attr2syntax[a][1],
                                   normalize     = self.attr2syntax[a][2]))
             for a,s,t in (('mobile', fs, self.const.contact_mobile_phone),)]
        self.attr2id2contacts.extend((v for v in c if v[1]))

    def update_org_object_entry(self, entry):
        # Changes from superclass:
        # Add attributes needed by UiT.
        self.__super.update_org_object_entry(entry)
  
        if entry.has_key('o'):
            entry['o'].append(['University of Tromsoe','Universitetet i Tromso'])
        else:
            entry['o'] = (['University of Tromsoe','Universitetet i Tromso'])
  
        if entry.has_key('eduOrgLegalName'):
            entry['eduOrgLegalName'].append(['Universitetet i Tromso','University of Tromsoe'])
        else:
            entry['eduOrgLegalName'] = (['Universitetet i Tromso','University of Tromsoe'])
        
        entry['norEduOrgNIN'] = (['NO970422528'])


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
            self.const.OUPerspective(cereconf.LDAP_OU['perspective']), filter_expired = True)
        self.logger.debug("OU-list length: %d", len(ou_list))
        self.ou_tree = {None: []}  # {parent ou_id or None: [child ou_id...]}
        for ou_id, parent_id in ou_list:
            if parent_id is not None:
                parent_id = int(parent_id)
            self.ou_tree.setdefault(parent_id, []).append(int(ou_id))
        timer("...OU tree done.")
    
    def generate_person(self, outfile, alias_outfile, use_mail_module):
        """Output person tree and aliases if cereconf.LDAP_PERSON['dn'] is set.

        Aliases are only output if cereconf.LDAP_PERSON['aliases'] is true.

        If use_mail_module is set, persons' e-mail addresses are set to
        their primary users' e-mail addresses.  Otherwise, the addresses
        are taken from contact info registered for the individual persons."""

        # Changes from superclass:
        # - Persons with affiliation_ansatt_sito or affiliation_manuell_gjest_u_konto are ignored.
        # - system object is added.
        
        if not self.person_dn:
            return
        self.init_person_dump(use_mail_module)
        if self.person_parent_dn not in (None, self.org_dn):
            outfile.write(container_entry_string('PERSON'))
        timer       = make_timer(self.logger,"Processing persons...")
        round_timer = make_timer(self.logger)
        round       = 0
        for row in self.list_persons():
            #print "---"
            #pprint(row)
            #print "---"
            if(row[2] in [int(self.const.affiliation_ansatt_sito)]):
                # this person does not qualify to be listed in the FEIDE tree on the ldap server.
                #self.logger.warn("sito person. Not to be included")
                continue
            if (row[2] in [int(self.const.affiliation_manuell_gjest_u_konto)]):
                #self.logger.warn("person withouth account. not to be included")
                continue
            if round % 10000 == 0:
                round_timer("...rounded %d rows..." % round)
            round += 1
            dn, entry, alias_info = self.make_person_entry(row)
            if dn:
                if dn in self.used_DNs:
                    self.logger.warn("Omitting person_id %d: duplicate DN '%s'"
                                     % (row['person_id'], dn))
                else:
                    self.used_DNs[dn] = True
                    outfile.write(entry_string(dn, entry, False))
                    if self.aliases and alias_info:
                        self.write_person_alias(alias_outfile,
                                                dn, entry, alias_info)
        timer("...persons done.")
        self.generate_system_object(outfile)

    def generate_system_object(self,outfile):
        entry= {'objectClass':['top','uioUntypedObject']}
        self.ou_dn = "cn=system,dc=uit,dc=no"
        outfile.write(entry_string(self.ou_dn,entry))
    
    def make_uioPersonScopedAffiliation(self, p_id, pri_aff, pri_ou):
        # [primary|secondary]:<affiliation>@<status>/<stedkode>
        ret = []
        pri_aff_str, pri_status_str = pri_aff
        for aff, status, ou in self.affiliations[p_id]:
            # populate the caches
            if self.aff_cache.has_key(aff):
                aff_str = self.aff_cache[aff]
            else:
                aff_str = str(self.const.PersonAffiliation(aff))
                self.aff_cache[aff] = aff_str
            if self.status_cache.has_key(status):
                status_str = self.status_cache[status]
            else:
                status_str = str(self.const.PersonAffStatus(status).str)
                self.status_cache[status] = status_str
            p = 'secondary'
            if aff_str == pri_aff_str and status_str == pri_status_str and ou == pri_ou:
                p = 'primary'
            ou = self.ou_id2ou_uniq_id[ou]
            if ou:
                ret.append(''.join((p,':',aff_str,'/',status_str,'@',ou)))
        return ret
        
    def make_person_entry(self, row):
        """Add data from person_course to a person entry."""
        p_id = int(row['person_id'])
        dn, entry, alias_info = self.__super.make_person_entry(row,p_id)
        if not dn:
            return dn, entry, alias_info
        if self.ownerid2urnlist.has_key(p_id):
            # Some of the chars in the entitlements are outside ascii
            if entry.has_key('eduPersonEntitlement'):
                entry['eduPersonEntitlement'].extend(self.ownerid2urnlist[p_id])
            else:
                entry['eduPersonEntitlement'] = self.ownerid2urnlist[p_id]
        #entry['uioPersonID'] = str(p_id)
        
        #
        # self.person2group == list over person_id : {gruppe_navn}
        # p_id == person_id
        #
        
        if self.person2group.has_key(p_id):
            # TODO: remove member and uioPersonObject after transition period
            entry['uitMemberOf'] = self.person2group[p_id]
            #entry['objectClass'].extend(('uioMembership', 'uioPersonObject'))
            entry['objectClass'].append('uioMembership')
        pri_edu_aff, pri_ou, pri_aff = self.make_eduPersonPrimaryAffiliation(p_id)
        #entry['uioPersonScopedAffiliation'] = self.make_uioPersonScopedAffiliation(p_id, pri_aff, pri_ou)
        #if 'uioPersonObject' not in entry['objectClass']:
        #    entry['objectClass'].extend(('uioPersonObject',))

        # Check if there exists «avvikende» addresses, if so, export them instead:
        addrs = self.addr_info.get(p_id)
        # post  = addrs and addrs.get(int(self.const.address_other_post))
        # if post:
        #     a_txt, p_o_box, p_num, city, country = post
        #     post = self.make_address("$", p_o_box,a_txt,p_num,city,country)
        #     if post:
        #         entry['postalAddress'] = (post,)
        # street = addrs and addrs.get(int(self.const.address_other_street))
        # if street:
        #     a_txt, p_o_box, p_num, city, country = street
        #     street = self.make_address(", ", None,a_txt,p_num,city,country)
        #     if street:
        #         entry['street'] = (street,)

        return dn, entry, alias_info
    
