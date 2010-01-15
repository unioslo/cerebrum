# -*- coding: iso-8859-1 -*-
# Copyright 2005 University of Oslo, Norway
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

import cerebrum_path
import cereconf

from mx import DateTime

from Cerebrum import Errors
from Cerebrum import Constants
from Cerebrum.Utils import Factory, auto_super
from Cerebrum.extlib.doc_exception import DocstringException
from Cerebrum.modules.abcenterprise.Object2Cerebrum import Object2Cerebrum
from Cerebrum.modules.abcenterprise.Object2Cerebrum import ABCMultipleEntitiesExistsError
from Cerebrum.modules.abcenterprise.Object2Cerebrum import ABCErrorInData

from Cerebrum.modules.no.ntnu.abcenterprise.ABCDataObjectsExt import DataPersonExt

class Object2CerebrumExt(Object2Cerebrum):

    __metaclass__ = auto_super

    
    def _find_lowest(self, kodes):
        if len(kodes) == 0:
            return None
        saved_kodes = []
        if len(kodes) == 1:
            saved_kodes.append(kodes[0])
        else:
            save_num_zeros = 0
            for i in range(0, len(kodes)):
                ## reverse stedkode
                kode = kodes[i][::-1]
                num_zeros = 0
                for j in range(0, len(kode)):
                    if kode[j] != '0':
                        break
                    num_zeros +=1
                if num_zeros > save_num_zeros:
                    save_num_zeros = num_zeros
                    saved_kodes = [kodes[i]]
                elif num_zeros == save_num_zeros:
                    saved_kodes.append(kodes[i])
        if len(saved_kodes) > 1:
            saved_kodes.sort()
        return saved_kodes[0]

    def _populate_ou(self, ou, stedkode):
        if stedkode:
            country = int(stedkode[:2])
            institution= int(stedkode[2:5])
            faculty = int(stedkode[5:7])
            department = int(stedkode[7:9])
            workgroup = int(stedkode[9:])
        else:
            country = self._ou.landkode
            institution = self._ou.institusjon
            faculty = self._ou.fakultet
            department = self._ou.institutt
            workgroup = self._ou.avdeling
        self._ou.populate(ou.ou_names['name'],
                            faculty,
                            department,
                            workgroup,
                            institusjon = institution,
                            landkode = country,
                            acronym = ou.ou_names['acronym'],
                            short_name = ou.ou_names['acronym'],
                            display_name = ou.ou_names['name'],
                            sort_name = ou.ou_names['name'],
                            parent=None)

    def _find_replacedby(self, kjerne_id):
        entity_id = None
        replacedby = Factory.get("OU")(self.db)
        replacedby.clear()
        try:
            replacedby.find_by_external_id(self.co.externalid_kjerneid_ou,
                                        kjerne_id,
                                        self.source_system)
            entity_id = replacedby.entity_id
        except Errors.NotFoundError, e:
            entity_id = None
        return entity_id

    def store_ou(self, ou):
        """Pass a DataOU to this function and it gets stored
        in Cerebrum."""
        if self._ou is None:
            self._ou = Factory.get("OU")(self.db)
        self._ou.clear()
        ##self.co = Factory.get('Constants')()
        stedkode = None
        entity_id = self._check_entity(self._ou, ou)
        if entity_id:
            ## ou has an uniq external identifier
            ##  and an entity_id
            stedkode = None
            self._ou.clear()
            self._ou.find(entity_id)
            self._populate_ou(ou, stedkode)
            populated = True
        else:
            ## try to find by stedkode, stedkode may
            ## not be uniq and we have to loop thru
            ## all possible stedkodes
            entity_id = None
            for kode in ou.stedkodes:
                try:
                    self._ou.clear()
                    self._ou.find_stedkode(int(kode[5:7]),
                                           int(kode[7:9]),
                                           int(kode[9:]),
                                           int(kode[2:5]),
                                           landkode = int(kode[:2]))
                    entity_id = self._ou.entity_id
                    stedkode = kode
                    break
                except Errors.NotFoundError, e:
                    # paranoia
                    stedkode = None
                    entity_id = None
                    continue
            if entity_id and stedkode:
                self._populate_ou(ou, stedkode)
            else:
                ## could not identify an ou from stedkodes.
                ## pick the lowest stedkode, populate ou and
                ## and the db will auto-generate entity_id
                if ou.stedkodes:
                    stedkode = self._find_lowest(ou.stedkodes)
                    if stedkode:
                        self._populate_ou(ou, stedkode)
                else:
                    self.logger.warning('Skipping OU %s without stedkode' % ou.ou_names['name'])
                    return (None, None)

        self._ou.write_db()
        self._add_external_ids(self._ou, ou._ids)
        self._add_entity_addresses(self._ou, ou._address)
        self._add_entity_contact_info(self._ou, ou._contacts)
        if ou.replacedby:
            # find the entity_id which replaces this ou
            self._replacedby[self._ou.entity_id] = self._find_replacedby(ou.replacedby)   
        return (self._ou.write_db(), self._ou.entity_id)


    def store_person(self, person):
        """Pass a DataPerson to this function and it gets stored
        in Cerebrum."""
        if self._person is None:
            self._person = Factory.get("Person")(self.db)
        self._person.clear()

        entity_id = None

        ## try to find in the usual way
        entity_id = self._check_entity(self._person, person)
        if not entity_id:
            ## the ordinary ids did not find a person.
            ## try with the old NINs one by one in
            ## in case the person is stored with one
            ## of the old NINs
    
            if person.fnr_closed:
                ## loop thru old NINs
                for closed_fnr in person.fnr_closed:
                    ## use only the old NIN for search.
                    copy_person = DataPersonExt()
                    copy_person._ids[self.co.externalid_fodselsnr] = closed_fnr
                    entity_id = self._check_entity(self._person, copy_person)
                    if entity_id:
                        ## success
                        break
        if entity_id:
            # We found one
            self._person.find(entity_id)
        # else:
            # Noone in the database could be found with our IDs.
            # This is fine, write_db() figures it out.

        if person.birth_date == None:
            raise ABCErrorInData, "No birthdate for person: %s." % person._ids

        # Populate the person
        self._person.populate(person.birth_date, person.gender)
        self._add_external_ids(self._person, person._ids)
        # Deal with names
        self._person.affect_names(self.source_system, *person._names.keys())
        for name_type in person._names.keys():
            self._person.populate_name(name_type,
                                       person._names[name_type])
        ret = self._person.write_db()
        # deal with traits
        if person.reserv_publish:
            reserv_trait = self._person.get_trait(self.co.trait_reserve_publish)
            if person.reserv_publish == "yes":
                self._person.populate_trait(self.co.trait_reserve_publish)
            # person want to delete reservation
            elif person.reserv_publish == "no" and reserv_trait:
                self._person.delete_trait(self.co.trait_reserve_publish)
        # Deal with addresses and contacts. 
        self._add_entity_addresses(self._person, person._address)
        self._add_entity_contact_info(self._person, person._contacts)
        ret = self._person.write_db()
        return ret

    def _update_ou_affiliations(self):
        person = Factory.get('Person')(self.db)
        pp = Factory.get('Person')(self.db)
        for k in self._replacedby.keys():
            ou_id = int(k)
            person.clear()
            for row in person.list_affiliations(source_system=self.source_system, ou_id=ou_id):
                p_id = int(row['person_id'])
                aff = int(row['affiliation'])
                status = int(row['status'])
                pp.clear()
                pp.find(p_id)
                pp.delete_affiliation( ou_id, aff, self.source_system)
                pp.add_affiliation(int(self.replacedby[k]), aff,
                        self.source_system, status)

    def _update_ous(self):
        self._update_ou_affiliations()
            
# arch-tag: fda7302c-6995-11da-943c-1c905588559b
