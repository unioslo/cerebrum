# encoding: utf-8
"""
Tests for mod:`Cerebrum.modules.ou_import.ou_sync`

TODO
----
These are placed in tests/modules/ rather than tests/core/modules/ because they
depend on a certain set of `cereconf` values to work properly:

1. The `ou_sync.OuWriter.find_ou` currently relies on the `Stedkode`
   mixin.  This could be fixed by relying less on `find_stedkode`/`find_sko` as
   the primary org unit identifier, and re-defining location codes as a simple
   external id.

2. The `ou_sync.OuWriter` needs a bunch of optional constants (names, spreads,
   quarantines) that may not exist in all environments.  This could be fixed by
   refactoring and moving more constants into CoreConstants.


If we ever fix these issues, it would be a lot easier to add more tests.  We
should test:

- setting, updating, and clearing values (ids, contact info, addresses, names,
  and spreads)

- finding/matching existing org units on other identifiers

"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest
import six

from Cerebrum.modules.ou_import import ou_model
from Cerebrum.modules.ou_import import ou_sync


@pytest.fixture(autouse=True)
def _patch_cereconf(cereconf):
    # TODO: This won't really work, as these values have already been
    # copied into `ou_sync.OuWriter`...
    cereconf.DEFAULT_INSTITUSJONSNR = 185
    cereconf.OU_USAGE_SPREAD = {}


SOURCE_SYSTEM = "e6ecf1073188eaba"


@pytest.fixture
def source_system(constant_module):
    """ A new, unique source system for tests. """
    code = constant_module._AuthoritativeSystemCode
    sys = code(SOURCE_SYSTEM, description="source system for tests")
    sys.insert()
    constant_module.CoreConstants.test_source_system = sys
    return sys


ID_TYPE = "dec10c1c885f8d72"
ID_VALUE = "1"


@pytest.fixture
def id_type(constant_module):
    code = constant_module._EntityExternalIdCode
    typ = code(ID_TYPE,
               constant_module.CoreConstants.entity_ou,
               description="external id type for tests")
    typ.insert()
    constant_module.CoreConstants.test_id_type = typ
    return typ


CONTACT_TYPE = "fb520cbf7bb3c7ab"
CONTACT_VALUE = "foo@example.org"


@pytest.fixture
def contact_type(constant_module):
    code = constant_module._ContactInfoCode
    ci = code(CONTACT_TYPE,
              description="contact info type for tests")
    ci .insert()
    constant_module.CoreConstants.test_contact_info = ci
    return ci


def test_get_constants(const, id_type, source_system, contact_type):
    # Sanity check that our fixture constants will work with the ou sync
    assert const.get_constant(type(id_type),
                              six.text_type(id_type))
    assert const.get_constant(type(source_system),
                              six.text_type(source_system))
    assert const.get_constant(type(contact_type),
                              six.text_type(contact_type))


# TODO: Hacky - if this location code exists, our tests might fail.  What
# would otherwise be a `ou create` operation becomes an `ou update` if this
# ou already exists.  Furthermore, if the pre-existing ou is quarantined, we'll
# get a bunch of problems with the enable/disable test.


LOCATION_CODE = "899999"


@pytest.fixture
def writer(database, source_system):
    return ou_sync.OuWriter(database, source_system, publish_all=False)


def test_writer_init(database, writer, source_system):
    assert writer.db is database
    assert writer.source_system == source_system
    assert not writer.publish_all


def test_creator_id(writer, initial_account):
    assert writer.creator_id == initial_account.entity_id


@pytest.fixture
def prepared_ou(database, id_type):
    data = ou_model.PreparedOrgUnit(LOCATION_CODE, is_valid=True)
    data.add_external_id(six.text_type(id_type), ID_VALUE)
    return data


def test_find_nonexisting_ou(writer, prepared_ou):
    assert writer.find_ou(prepared_ou) is None


def test_sync_create_ou(writer, source_system, id_type, prepared_ou):
    """ sync_ou() should create non-existing ou. """
    data = prepared_ou
    assert writer.find_ou(data) is None
    ou_obj = writer.sync_ou(data)
    assert ou_obj and ou_obj.entity_id

    # Check that our external id was written as well
    id_rows = list(ou_obj.get_external_id(source_system=source_system,
                                          id_type=id_type))
    assert len(id_rows) == 1
    assert id_rows[0]['external_id'] == ID_VALUE


def test_find_existing_ou(writer, prepared_ou):
    ou = writer.sync_ou(prepared_ou)
    found = writer.find_ou(prepared_ou)
    assert ou.entity_id == found.entity_id


def test_sync_ignore_invalid_ou(writer, prepared_ou):
    """ sync_ou() shouldn't create an invalid ou. """
    data = prepared_ou
    data.is_valid = False
    assert writer.sync_ou(data) is None


@pytest.fixture
def existing_ou(writer, prepared_ou):
    return writer.sync_ou(prepared_ou)


def test_sync_update_ou(writer, prepared_ou, existing_ou,
                        source_system, contact_type):
    data = prepared_ou
    data.add_contact_info(six.text_type(contact_type), CONTACT_VALUE)
    ou_obj = writer.sync_ou(data)
    assert ou_obj.entity_id == existing_ou.entity_id

    # Check that our external id was written as well
    rows = list(ou_obj.get_contact_info(source=source_system,
                                        type=contact_type))
    assert len(rows) == 1
    assert rows[0]['contact_value'] == CONTACT_VALUE


#
# test ou enable/disable
#


@pytest.fixture
def enabled_ou(writer, prepared_ou):
    prepared_ou.is_valid = True
    return writer.sync_ou(prepared_ou)


@pytest.fixture
def disabled_ou(writer, prepared_ou, enabled_ou):
    # Note: enabled_ou is not used directly, but `sync_ou()` won't *create*
    # invalid org unit - we use the enabled_ou fixture to *create* the org unit
    # first.
    prepared_ou.is_valid = False
    return writer.sync_ou(prepared_ou)


def _is_disabled(ou):
    # We may want to specify quarantine types here - but as the org units in
    # these tests are new, they shouldn't have any other quarantines than the
    # enable/disable ones.
    return list(ou.get_entity_quarantine())


def test_enable_valid_ou(enabled_ou):
    """ check that a valid org unit does not get disabled. """
    assert not _is_disabled(enabled_ou)


def test_disable_invalid_ou(disabled_ou):
    """ check that an invalid org unit does not get enabled. """
    assert _is_disabled(disabled_ou)


def test_disable_ou(writer, enabled_ou):
    """ check return value when disabling an enabled ou. """
    ou = enabled_ou
    assert writer.disable_ou(ou)
    assert _is_disabled(ou)


def test_enable_ou(writer, disabled_ou):
    """ check return value when enabling a disabled ou. """
    ou = disabled_ou
    assert writer.enable_ou(ou)
    assert not _is_disabled(ou)


def test_redisable_ou(writer, disabled_ou):
    """ check return value when re-disabling an ou. """
    assert not writer.disable_ou(disabled_ou)
    assert _is_disabled(disabled_ou)


def test_reenable_ou(writer, enabled_ou):
    """ check return value when re-enabling an ou. """
    assert not writer.enable_ou(enabled_ou)
    assert not _is_disabled(enabled_ou)
