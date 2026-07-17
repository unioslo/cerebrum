# -*- coding: utf-8 -*-
""" Tests for :mod:`Cerebrum.modules.feide.ldif_mixins` """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest

import Cerebrum.Person
from Cerebrum.modules.LDIFutils import LdapConfig
from Cerebrum.modules.OrgLDIF import OrgLdifConfig
from Cerebrum.modules.feide import ldif_mixins
from Cerebrum.modules.feide import service
from Cerebrum.testutils import datasource


FEIDE_SERVICE_ID = "af536afafc6dab7f"
FEIDE_SERVICE_NAME = "test-service-9c40ecda"


@pytest.fixture
def ldap_config():
    """ A mock org-ldif config. """
    # Just enough to get past the OrgLdif init
    base = LdapConfig(
        "mock.LDAP",
        {
            'pref_languages': ['en'],
            'output_languages': False,
            # NorEduAuthnLevelMixin is disabled if FEIDE_schema_version < 1.6
            'FEIDE_schema_version': "1.6",
            'FEIDE_obsolete_schema_version': "1.5",
        },
    )
    org = LdapConfig(
        "mock.LDAP_ORG",
        {'dn': "ou=mock,dc=example,dc=org"},
        parent=base,
    )
    ou = LdapConfig(
        "mock.LDAP_OU",
        {'dn': "ou=org,ou=mock,dc=example,dc=org"},
        parent=base,
    )
    person = LdapConfig(
        "mock.LDAP_PERSON",
        {
            'dn': "ou=people,ou=mock,dc=example,dc=org",
            'aliases': False,
            'auth_attr': {
                'userPassword': [
                    ("plaintext", "n/a")
                ],
            }
        },
        parent=base,
    )
    return OrgLdifConfig(org, ou, person, domain_name="example.org", org_id=1)


class _MockOrgLdif(ldif_mixins.NorEduAuthnLevelMixin):

    @property
    def fodselsnrs(self):
        return {}

    @property
    def birth_dates(self):
        return {}


@pytest.fixture
def org_ldif(database, ldap_config):
    return _MockOrgLdif(database, config=ldap_config)


@pytest.fixture
def feide_service(database):
    obj = service.FeideService(database)
    obj.populate(FEIDE_SERVICE_ID, FEIDE_SERVICE_NAME)
    obj.write_db()
    return obj


@pytest.fixture
def person_cls():
    return Cerebrum.Person.Person


@pytest.fixture
def person_creator(database, const, person_cls):
    """
    A helper fixture to create person objects.
    """
    person_ds = datasource.BasicPersonSource()

    def _create_persons(limit=1):
        for person_dict in person_ds(limit=limit):
            person = person_cls(database)
            gender = person_dict.get('gender')
            if gender:
                gender = const.human2constant(gender, const.Gender)
            gender = gender or const.gender_unknown
            person.populate(
                person_dict['birth_date'],
                gender,
                person_dict.get('description'),
            )
            person.write_db()
            person_dict['entity_id'] = person.entity_id
            yield person, person_dict

    return _create_persons


@pytest.fixture
def person(database, person_creator, feide_service):
    person, _ = next(person_creator(1))
    authn_levels = service.FeideServiceAuthnLevelMixin(database)
    authn_levels.add_authn_level(
        service_id=feide_service.entity_id,
        level=2,
        entity_id=person.entity_id,
    )
    return person


def test_org_ldif_init(org_ldif):
    assert org_ldif


def test_org_ldif_authn_levels(org_ldif):
    levels = org_ldif.person_authn_levels
    assert isinstance(levels, dict)


def test_org_ldif_update_person_entry(org_ldif, person):
    person_id = person.entity_id
    mock_entry = {
        'uid': "example-user",
        'cn': "Example User",
        'objectClass': [],
    }
    row = {}

    result = dict(mock_entry)
    org_ldif.update_person_entry(result, row, person_id)

    assert 'norEduPersonServiceAuthnLevel' in result
