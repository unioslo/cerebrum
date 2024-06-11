# -*- coding: utf-8 -*-
"""
Basic tests for :mod:`Cerebrum.modules.consent`
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest
import six

from Cerebrum.modules.consent import Consent
from Cerebrum.modules.consent import ConsentConstants


@pytest.fixture
def entity_obj(database):
    return Consent.EntityConsentMixin(database)


@pytest.fixture
def entity(entity_obj, entity_type):
    entity_obj.populate(entity_type)
    entity_obj.write_db()
    return entity_obj


def test_assert_consent_code(consent_foo):
    for v in (consent_foo, int(consent_foo), six.text_type(consent_foo)):
        assert Consent.assert_consent_code(v) == consent_foo


def test_assert_consent_type(opt_in):
    for v in (opt_in, int(opt_in), six.text_type(opt_in)):
        assert Consent.assert_consent_type(v) == opt_in


def test_get_change_type_opt_in(consent_foo):
    # opt in -> change-type approve
    expect = ConsentConstants.CLConstants.consent_approve
    assert Consent.get_change_type(consent_foo) == expect


def test_get_change_type_opt_out(consent_bar):
    expect = ConsentConstants.CLConstants.consent_decline
    assert Consent.get_change_type(consent_bar) == expect


def test_insert_consent(database, entity, consent_foo):
    Consent.sql_insert_consent(database, entity.entity_id, consent_foo)
    assert True  # reached


def test_update_consent(database, entity, consent_foo):
    Consent.sql_insert_consent(database, entity.entity_id, consent_foo)
    Consent.sql_update_consent(database, entity.entity_id, consent_foo,
                               description="test consent update")
    assert True  # reached


def test_delete_consent(database, entity, consent_foo):
    Consent.sql_insert_consent(database, entity.entity_id, consent_foo)
    Consent.sql_delete_consent(database, entity.entity_id, consent_foo)
    assert True  # reached


def test_select_consents(database, entity, consent_foo, consent_bar):
    Consent.sql_insert_consent(database, entity.entity_id, consent_foo)
    Consent.sql_insert_consent(database, entity.entity_id, consent_bar)

    rows = Consent.sql_select_consents(database,
                                       entity_type=entity.entity_type,
                                       fetchall=True)
    assert len(rows) == 2

    rows = Consent.sql_select_consents(database,
                                       entity_id=entity.entity_id,
                                       fetchall=True)
    assert len(rows) == 2

    rows = Consent.sql_select_consents(database,
                                       consent_code=consent_foo,
                                       fetchall=True)
    assert len(rows) == 1

    rows = Consent.sql_select_consents(database,
                                       consent_type=consent_bar.consent_type,
                                       entity_type=entity.entity_type,
                                       fetchall=True)
    assert len(rows) == 1


def test_mixin_get_consent_status_missing(database, entity, consent_foo):
    status = entity.get_consent_status(consent_foo)
    assert status is None


def test_mixin_get_consent_status(database, entity, consent_foo):
    Consent.sql_insert_consent(database, entity.entity_id, consent_foo)
    status = entity.get_consent_status(consent_foo)
    data = dict(status)
    assert data['entity_id'] == entity.entity_id
    assert data['consent_code'] == int(consent_foo)
    assert data['set_at']
    assert 'description' in data


def test_mixin_set_consent(database, entity, consent_foo):
    entity.set_consent(consent_foo, description="test mixin.set_consent()")
    assert entity.get_consent_status(consent_foo) is None
    entity.write_db()
    assert entity.get_consent_status(consent_foo) is not None


def test_mixin_remove_consent(database, entity, consent_foo):
    Consent.sql_insert_consent(database, entity.entity_id, consent_foo)
    entity.remove_consent(consent_foo)
    assert entity.get_consent_status(consent_foo) is not None
    entity.write_db()
    assert entity.get_consent_status(consent_foo) is None
