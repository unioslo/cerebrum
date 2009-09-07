# -*- coding: iso-8859-1 -*-

# Copyright 2004, 2005 University of Oslo, Norway
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
#

import unittest
from copy import deepcopy
from mx.DateTime import DateTime
from mx.DateTime import strptime
import cerebrum_path
from Cerebrum import Utils
from lib.data.DTO import DTO
from lib.data.PersonDAO import PersonDAO
from Cerebrum.Errors import NotFoundError
from CerebrumTestCase import CerebrumTestCase

import TestData

class PersonDAOTest(CerebrumTestCase):
    """We test against the test-database and we use the fabricated person Test Testesen to verify that we get the expected data."""

    def setUp(self):
        super(PersonDAOTest, self).setUp()
        self.dao = PersonDAO(self.db)

    def test_person_entity_has_correct_data(self):
        entity = self.dao.get_entity(TestData.test_testesen_id)
        expected = TestData.get_test_testesen_entity()

        self.assertEqual(expected, entity)

    def test_that_get_with_include_extra_has_quarantines(self):
        entity = self.dao.get(TestData.test_testesen_id, include_extra=True)

        self.assert_(len(entity.quarantines) > 0)

        quarantine = entity.quarantines[0]
        self.assertEqual("HUHUHU", quarantine.description)

    def test_get_accounts_returns_all_accounts(self):
        accounts = self.dao.get_accounts(TestData.test_testesen_id)

        self.assertEqual(3, len(accounts))

    def test_get_accounts_returns_correct_dtos(self):
        accounts = self.dao.get_accounts(TestData.test_testesen_id)

        expected = {
            'tstnogrp': (356047, False, True),
            'ctestpos': (355252, True, False),
            'cetest1': (354991, False, False)
        }

        for account in accounts:
            self.assert_(account.name in expected)
            expected_id, is_posix, is_primary = expected.pop(account.name)
            self.assertEqual(is_posix, account.is_posix)
            self.assertEqual(is_primary, account.is_primary)
            self.assertEqual(expected_id, account.id)

        self.assert_(expected == {})

    def test_person_has_correct_data(self):
        person = self.dao.get(TestData.test_testesen_id)
        expected = TestData.get_test_testesen()

        self.assertEqual(expected, person)

    def test_that_person_has_list_of_names(self):
        person = self.dao.get(TestData.test_testesen_id, True)

        self.assert_(person.names)

        for name in person.names:
            self.assert_(name.value in ("Test Testesen", "Test", "Testesen"), "Unexpected name.")

        control = (n for n in person.names if n.variant.name == 'FULL').next()

        source_systems = [s.name for s in control.source_systems]
        self.assertEqual(['Cached', 'Manual'], source_systems)
        self.assertEqual("Test Testesen", control.value)

    def test_that_person_has_list_of_external_ids(self):
        person = self.dao.get(TestData.test_testesen_id, True)
        self.assert_(person.external_ids)

        control = (i for i in person.external_ids if i.variant.name == "NO_BIRTHNO").next()
        self.assertEqual("10107910986", control.value)

    def test_that_person_has_list_of_contacts(self):
        person = self.dao.get(TestData.test_testesen_id, True)
        self.assert_(person.contacts)
        control = (i for i in person.contacts if i.variant.name == "PHONE").next()
        self.assertEqual("73 59 80 75", control.value)

    def test_that_person_has_list_of_addresses(self):
        person = self.dao.get(TestData.test_testesen_id, True)
        self.assert_(person.addresses)
        control = (i for i in person.addresses if i.variant.name == "POST").next()
        self.assertEqual("7491", control.value.postal_number)

    def test_that_we_can_get_affiliations_from_person_id(self):
        affiliations = self.dao.get_affiliations(TestData.test_testesen_id)
        self.assert_(len(affiliations) == 4)
        aff = (x for x in affiliations if x.name == "ALUMNI/aktiv").next()
        self.assertEquals(3, aff.ou.id)

class PersonDAOWriteTest(CerebrumTestCase):
    def setUp(self):
        super(PersonDAOWriteTest, self).setUp()
        self.dao = PersonDAO(self.db)

    def _get_and_clone(self, id):
        dto = self.dao.get(TestData.test_testesen_id)
        orig = deepcopy(dto)
        return dto, orig

    def test_that_we_can_change_the_birth_date_of_a_person(self):
        dto, orig = self._get_and_clone(TestData.test_testesen_id)

        dto.birth_date += 1
        self.dao.save(dto)

        result = self.dao.get(TestData.test_testesen_id)
        self.assertNotEqual(orig.birth_date, result.birth_date)
        self.assertEqual(dto.birth_date, result.birth_date)

    def test_that_we_can_change_the_gender_of_a_person(self):
        dto, orig = self._get_and_clone(TestData.test_testesen_id)

        dto.gender.id = 'X'
        self.dao.save(dto)

        result = self.dao.get(TestData.test_testesen_id)
        self.assertNotEqual(orig.gender.id, result.gender.id)

    def test_that_we_can_change_the_description_of_a_person(self):
        dto, orig = self._get_and_clone(TestData.test_testesen_id)

        dto.description = "Hulahula"
        self.dao.save(dto)

        result = self.dao.get(TestData.test_testesen_id)
        self.assertNotEqual(orig.description, result.description)
        self.assertEqual(dto.description, result.description)

    def test_that_we_can_change_the_deceased_date_of_a_person(self):
        dto, orig = self._get_and_clone(TestData.test_testesen_id)

        dto.deceased_date = strptime("1980-06-28", "%Y-%m-%d")
        self.dao.save(dto)

        result = self.dao.get(TestData.test_testesen_id)
        self.assertNotEqual(orig.deceased_date, result.deceased_date)
        self.assertEqual(dto.deceased_date, result.deceased_date)

    def _create_person(self):
        person = DTO()
        person.gender = DTO()
        person.gender.id = 'M'
        person.first_name = "Test"
        person.last_name = "Testesen"
        person.birth_date = strptime("1980-06-28", "%Y-%m-%d")
        person.description = "Brukt i PersonDAOTest, skal ikke ligge i databasen.  Du kan trygt slette meg."
        self.dao.create(person)

        return person

    def test_that_we_can_create_a_person(self):
        person = self._create_person()
        self.assert_(person.id > 0)

        result = self.dao.get(person.id, include_extra=True)

        self.assertEqual("Test Testesen", result.name)
        self.assertEqual(person.birth_date, result.birth_date)
        self.assertEqual(person.description, result.description)
        self.assertEqual('M', result.gender.name)

    def test_that_we_can_add_an_affiliation(self):
        person = self.dao.get(TestData.test_testesen_id, include_extra=True)
        affils_before = person.affiliations

        ou_rektor = 4
        status_gjest = 103
        self.dao.add_affiliation_status(person.id, ou_rektor, status_gjest)

        person = self.dao.get(person.id, include_extra=True)
        affils_after = person.affiliations

        self.assertEqual(1, len(affils_after) - len(affils_before))

    def test_that_we_can_remove_an_affiliation(self):
        person = self.dao.get(TestData.test_testesen_id, include_extra=True)
        affils_before = person.affiliations

        to_delete = affils_before[0]
        self.dao.remove_affiliation_status(person.id, to_delete.ou.id, to_delete.id, to_delete.source_system.id)

        person = self.dao.get(person.id, include_extra=True)
        affils_after = person.affiliations

        deleted_before = filter(lambda x: x.is_deleted, affils_before)
        deleted_after = filter(lambda x: x.is_deleted, affils_after)

        self.assertEqual(1, len(deleted_after) - len(deleted_before))
        for d in deleted_after:
            self.assertEqual(to_delete.id, d.id)
            self.assertEqual(to_delete.ou.id, d.ou.id)

    def test_that_we_can_remove_an_affiliation_with_string_arguments(self):
        person = self.dao.get(TestData.test_testesen_id, include_extra=True)
        affils_before = person.affiliations
        to_delete = affils_before[0]

        try:
            self.dao.remove_affiliation_status(person.id, str(to_delete.ou.id), str(to_delete.id), str(to_delete.source_system.id))
        except NotFoundError, e:
            self.fail("Should not throw exception.")

    def test_that_we_can_add_birth_no(self):
        dto = self._create_person()
        person = self.dao.get(dto.id, include_extra=True)

        self.assertEqual(0, len(person.external_ids))

        self.dao.add_birth_no(person.id, "10107936934")

        result = self.dao.get(person.id, include_extra=True)
        self.assertEqual(1, len(result.external_ids))
        extid = result.external_ids[0]

        self.assertEqual("10107936934", extid.value)

    def test_that_we_can_delete_a_person(self):
        person = self._create_person()
        self.dao.delete(person.id)

        self.assertRaises(NotFoundError, self.dao.get, person.id)

    def test_that_we_can_add_a_name(self):
        orig = self.dao.get(TestData.test_testesen_id, include_extra=True)

        name_type = 'DISPLAY'
        self.dao.add_name(orig.id, name_type, "Ole Testus")

        changed = self.dao.get(orig.id, include_extra=True)
        found = False
        for name in changed.names:
            found |= name.value == "Ole Testus" and name.variant.name == "DISPLAY"
        self.assertTrue(found)

    def test_that_we_can_remove_a_name(self):
        orig = self.dao.get(TestData.test_testesen_id, include_extra=True)
        name = orig.names[0]
        source = name.source_systems[0]

        self.dao.remove_name(orig.id, name.variant.id, source.id)

        changed = self.dao.get(orig.id, include_extra=True)
        found = False
        for changed_name in changed.names:
            found |= changed_name.variant.id == name.variant.id and source in changed_name.source_systems
        self.assertFalse(found)


if __name__ == '__main__':
    unittest.main()
