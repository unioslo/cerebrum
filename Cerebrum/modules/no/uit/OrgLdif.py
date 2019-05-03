#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
# Copyright 2002, 2003, 2004 University of Oslo, Norway
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



import mx

import cerebrum_path
import cereconf
from Cerebrum.Utils             import Factory, make_timer
from Cerebrum.modules.LDIFutils import *
from Cerebrum.modules           import OrgLDIF
from Cerebrum.QuarantineHandler import QuarantineHandler
from Cerebrum.modules.OrgLDIF import *

class OrgLdifUitMixin(OrgLDIF):


    def __init__(self, db, logger):
        self.__super.__init__(db, logger)
        self.norEduOrgUniqueNumber = ("000%05d"  # Note: 000 = Norway in FEIDE.
                                      % int(cereconf.DEFAULT_INSTITUSJONSNR),)
        self.norEduOrgNIN = (cereconf.DEFAULT_FORETAKSNR)
        self.norEduOrgSchemaVersion=(cereconf.norEduOrgSchemaVersion)
        # '@<security domain>' for the eduPersonPrincipalName attribute.
        self.eduPPN_domain = '@' + cereconf.INSTITUTION_DOMAIN_NAME



    def make_ou_entry(self, ou_id, parent_dn):
        # Changes from superclass:
        # If Stedkode is used, only output OUs that are publishable.
        # Add object class norEduOrgUnit and its attributes norEduOrgAcronym,
        # cn, norEduOrgUnitUniqueIdentifier, norEduOrgUniqueIdentifier.
        # If a DN is not unique, prepend the norEduOrgUnitUniqueIdentifier.
        self.ou.clear()
        self.ou.find(ou_id)
        if not self.ou.has_spread(self.const.spread_ou_publishable):
            return parent_dn, None
        
        ou_names = [iso2utf((n or '').strip()) for n in (
            self.ou.get_name_with_language(self.const.ou_name_acronym,
                                           self.const.language_nb,
                                           default=''),
            self.ou.get_name_with_language(self.const.ou_name_short,
                                           self.const.language_nb,
                                           default=''),
            self.ou.get_name_with_language(self.const.ou_name_display,
                                           self.const.language_nb,
                                           default=''))]
        acronym  = ou_names[0]
        ou_names = filter(None, ou_names)
        ldap_ou_id = self.get_orgUnitUniqueID()
        entry = {
            'objectClass': ['top', 'organizationalUnit', 'norEduOrgUnit','norEduOrg','eduOrg'],
            self.FEIDE_attr_ou_id:  (ldap_ou_id,),
            self.FEIDE_attr_org_id: self.norEduOrgUniqueID,
            'ou': ou_names,
            'cn': ou_names[-1:]}
        if self.FEIDE_class_obsolete:
            entry['objectClass'].append(self.FEIDE_class_obsolete)
            entry['norEduOrgUniqueNumber'] = self.norEduOrgUniqueID
            entry['norEduOrgUnitUniqueNumber'] = (ldap_ou_id,)
        if acronym:
            entry['norEduOrgAcronym'] = (acronym,)
        dn = self.make_ou_dn(entry, parent_dn or self.ou_dn)
        if not dn:
            return parent_dn, None
        entry['ou'] = self.attr_unique(entry['ou'], normalize_string)
        self.fill_ou_entry_contacts(entry)
        self.update_ou_entry(entry)
        return dn, entry



    def generate_person(self, outfile, alias_outfile, use_mail_module):
        """Output person tree and aliases if cereconf.LDAP_PERSON['dn'] is set.

        Aliases are only output if cereconf.LDAP_PERSON['aliases'] is true.

        If use_mail_module is set, persons' e-mail addresses are set to
        their primary users' e-mail addresses.  Otherwise, the addresses
        are taken from contact info registered for the individual persons."""
        if not self.person_dn:
            return
        self.init_person_dump(use_mail_module)
        if self.person_parent_dn not in (None, self.org_dn):
            outfile.write(container_entry_string('PERSON'))
        timer       = make_timer(self.logger, 'Processing persons...')
        round_timer = make_timer(self.logger)
        round       = 0
        for person_id, row in self.person_cache.iteritems():
            if round % 10000 == 0:
                round_timer("...rounded %d rows..." % round)
            round += 1
            dn, entry, alias_info = self.make_person_entry(row, person_id)
            if dn:
                if dn in self.used_DNs:
                    self.logger.warn("Omitting person_id %d: duplicate DN '%s'"
                                     % (person_id, dn))
                else:
                    self.used_DNs[dn] = True
                    outfile.write(entry_string(dn, entry, False))
                    if self.aliases and alias_info:
                        self.write_person_alias(alias_outfile,
                                                dn, entry, alias_info)
        timer("...persons done.")
        self.generate_system_object(outfile) # this line is the only reason for having generate_persons here

    #UIT: added the system object. This is needed when we add users under it
    def generate_system_object(self,outfile):
        entry= {'objectClass':['top','uioUntypedObject']}
        self.ou_dn = "cn=system,dc=uit,dc=no"
        outfile.write(entry_string(self.ou_dn,entry))


    def generate_org_object(self, outfile):
        """Output the organization object if cereconf.LDAP_ORG['dn'] is set."""
        if not self.org_dn:
            return
        self.init_org_object_dump()
        entry = {}
        self.ou.clear()
        if self.root_ou_id is not None:
            self.ou2DN[self.root_ou_id] = None
            self.ou.find(self.root_ou_id)
            self.fill_ou_entry_contacts(entry)
        entry.update(ldapconf('ORG', 'attrs', {}))
        oc = ['top', 'organization', 'eduOrg']
        oc.extend(entry.get('objectClass', ()))
        entry['objectClass'] = (['top', 'organization', 'eduOrg','norEduOrg','dcObject']
                                + list(entry.get('objectClass', ())))
        self.update_org_object_entry(entry)
        entry['o'] = (['UiT The Artcic University of Norway','UiT Norges Arktiske Universitet'])
        entry['eduOrgLegalName']=(['UiT Norges Arktiske Universitet','UiT The Artcic University of Norway'])
        entry['objectClass'] = self.attr_unique(entry['objectClass'],str.lower)
        #print "entry=%s " % entry
        outfile.write(entry_string(self.org_dn, entry))

    def update_org_object_entry(self, entry):
        # Changes from superclass:
        # Add object class norEduOrg and its attr norEduOrgUniqueIdentifier,
        # and optionally eduOrgHomePageURI, labeledURI and labeledURIObject.
        # Also add attribute federationFeideSchemaVersion if appropriate.
        entry['objectClass'].append('norEduOrg')
        entry['norEduOrgNIN']=self.norEduOrgNIN
        entry[self.FEIDE_attr_org_id] = self.norEduOrgUniqueID
        if self.FEIDE_class_obsolete:
            entry['objectClass'].append(self.FEIDE_class_obsolete)
            entry['norEduOrgUniqueNumber'] = self.norEduOrgUniqueID
        if self.FEIDE_schema_version > '1.1' and self.extensibleObject:
                entry['objectClass'].append(self.extensibleObject)
                entry['norEduOrgSchemaVersion']= (self.FEIDE_schema_version,)
        uri = entry.get('labeledURI') or entry.get('eduOrgHomePageURI')
        if uri:
            entry.setdefault('eduOrgHomePageURI', uri)
            if entry.setdefault('labeledURI', uri):
                if self.FEIDE_schema_version <= '1.1':
                    entry['objectClass'].append('labeledURIObject')

    def make_person_entry(self, row, person_id):
        # Return (dn, person entry, alias_info) for a person to output,
        # or (None, anything, anything) if the person should not be output.
        # bool(alias_info) == False means no alias will be output.
        # Receives a row from list_persons() as a parameter.
        # The row must have key 'account_id',
        # and if person_dn_primaryOU() is not overridden: 'ou_id'.
        account_id = int(row['account_id'])

        p_affiliations = self.affiliations.get(person_id)
        if not p_affiliations:
            return None, None, None

        names = self.person_names.get(person_id)
        if not names:
            self.logger.warn("Person %s got no names. Skipping.", person_id)
            return None, None, None
        name      = iso2utf(names.get(int(self.const.name_full),  '').strip())
        givenname = iso2utf(names.get(int(self.const.name_first), '').strip())
        lastname  = iso2utf(names.get(int(self.const.name_last),  '').strip())
        if not (lastname and givenname):
            givenname, lastname = self.split_name(name, givenname, lastname)
            if not lastname:
                self.logger.warn("Person %s got no lastname. Skipping.",
                                 person_id)
                return None, None, None
        if not name:
            name = " ".join(filter(None, (givenname, lastname)))

        entry = {
            'objectClass': ['top', 'person', 'organizationalPerson',
                            'inetOrgPerson', 'eduPerson'],
            'cn': (name,),
            'sn': (lastname,)}
        if givenname:
            entry['givenName'] = (givenname,)
        try:
            entry['uid'] = (self.acc_name[account_id],)
        except KeyError:
            pass

        passwd = self.acc_passwd.get(account_id)
        nt4_passwd=self.acc_passwd_nt4.get(account_id)
        if nt4_passwd ==None:
            nt4_passwd='*Invalid'
        qt = self.acc_quarantines.get(account_id)
        if qt:
            qh = QuarantineHandler(self.db, qt)
            if qh.should_skip():
                return None, None, None
            if qh.is_locked():
                passwd = 0
        if passwd:
            #entry['nt4_userPassword'] = (nt4_passwd,)
            entry['userPassword'] = ("{MD5}" + passwd,)
        elif passwd != 0 and entry.get('uid'):
            self.logger.debug("User %s got no password-hash.", entry['uid'][0])

        dn, primary_ou_dn = self.person_dn_primaryOU(entry, row, person_id)
        if not dn:
            return None, None, None

        if self.org_dn:
            entry['eduPersonOrgDN'] = (self.org_dn,)
        if primary_ou_dn:
            entry['eduPersonPrimaryOrgUnitDN'] = (primary_ou_dn,)
        edu_OUs = [primary_ou_dn] + [self.ou2DN.get(aff[2])
                                     for aff in p_affiliations]
        entry['eduPersonOrgUnitDN']   = self.attr_unique(filter(None, edu_OUs))
        entry['eduPersonAffiliation'] = self.attr_unique(self.select_list(
            self.eduPersonAff_selector, person_id, p_affiliations))

        if self.select_bool(self.contact_selector, person_id, p_affiliations):
            # title:
            title = self.person_title.get(person_id)
            if title:
                entry['title'] = (iso2utf(title),)
            # phone & fax:
            for attr, contact in self.attr2id2contacts:
                contact = contact.get(person_id)
                if contact:
                    entry[attr] = contact
            # addresses:
            addrs = self.addr_info.get(person_id)
            post  = addrs and addrs.get(int(self.const.address_post))
            if post:
                a_txt, p_o_box, p_num, city, country = post
                post = self.make_address("$", p_o_box,a_txt,p_num,city,country)
                if post:
                    entry['postalAddress'] = (post,)
            street = addrs and addrs.get(int(self.const.address_street))
            if street:
                a_txt, p_o_box, p_num, city, country = street
                street = self.make_address(", ", None,a_txt,p_num,city,country)
                if street:
                    entry['street'] = (street,)
        else:
            URIs = self.id2labeledURI.get(person_id)
            if URIs:
                entry['labeledURI'] = self.attr_unique(
                    map(iso2utf, URIs), normalize_caseExactString)

        if self.account_mail:
            mail = self.account_mail(int(account_id))
            if mail:
                entry['mail'] = (mail,)
        else:
            mail = self.get_contacts(
                entity_id    = person_id,
                contact_type = self.const.contact_email,
                verify       = verify_IA5String,
                normalize    = normalize_IA5String)
            if mail:
                entry['mail'] = mail

        alias_info = ()
        if self.select_bool(self.visible_person_selector,
                            person_id, p_affiliations):
            entry.update(self.visible_person_attrs)
            alias_info = (primary_ou_dn,)

        self.update_person_entry(entry, row, person_id)
        return dn, entry, alias_info

    
    
    def init_account_info(self):

        timer = make_timer(self.logger, 'Fetching account information...')
        timer2 = make_timer(self.logger)
        self.account = Factory.get('Account')(self.db)
        self.acc_name = acc_name = {}
        self.acc_passwd_nt4={}
        self.acc_passwd = {}
        self.acc_quarantines = acc_quarantines = {}
        fill_passwd = {

            int(self.const.auth_type_md5_b64):  self.acc_passwd.__setitem__,
            int(self.const.auth_type_md4_nt):  self.acc_passwd_nt4.__setitem__,
            int(self.const.auth_type_md5_b64):  self.acc_passwd.setdefault}
            #int(self.const.auth_type_md4_nt): self.acc_passwd.setdefault }
        for row in self.account.list_account_authentication(
            auth_type = fill_passwd.keys()):
            account_id           = int(row['account_id'])
            acc_name[account_id] = row['entity_name']
            method               = row['method']
            if method:
                fill_passwd[int(method)](account_id, row['auth_data'])
                #print "method: %s , fill=%s" % (method,fill_passwd)
        timer2("...account quarantines...")
        now = mx.DateTime.now()
        for row in self.account.list_entity_quarantines(
            entity_types = self.const.entity_account):
            if (row['start_date'] <= now
                and (row['end_date'] is None or row['end_date'] >= now)
                and (row['disable_until'] is None
                     or row['disable_until'] < now)):
                # The quarantine in this row is currently active.
                acc_quarantines.setdefault(int(row['entity_id']), []).append(
                    int(row['quarantine_type']))
        timer("...account information done.")


    def update_person_entry(self,entry, row, person_id):
        # Override this to fill in a person entry further before output.
        #
        # If there is no password, store a useless one instead of no password
        # so that a text filter can easily find and replace the password.
        entry.setdefault('userPassword', ("{MD5}*Invalid",)) # UIT: changed to MD5 from crypt
        #entry.setdefault('nt4_userPassword', ("*Invalid",)) # UIT: changed to MD5 from crypt


        self.__super.update_person_entry(entry, row, person_id)
        uname = entry.get('uid')
        person_id = int(row['person_id'])
        fnr = self.fodselsnrs.get(person_id)
        if uname and fnr:
            #entry['objectClass'].append('norEduPerson')
            entry['eduPersonPrincipalName'] = (uname[0] + self.eduPPN_domain,)
            entry['norEduPersonNIN'] = (str(fnr),)
            birth_date = self.birth_dates.get(person_id)
            if birth_date:
                entry['norEduPersonBirthDate'] = ("%04d%02d%02d" % (
                    birth_date.year, birth_date.month, birth_date.day),)



