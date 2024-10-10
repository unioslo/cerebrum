# encoding: utf-8
"""
Tests for :class:`Cerebrum.modules.import_utils.syncs.AffiliationSync`
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import datetime

import pytest
import six

from Cerebrum.modules.import_utils import syncs
from Cerebrum.modules.no import Stedkode


@pytest.fixture(autouse=True)
def _patch_cereconf(cereconf):
    cereconf.DEFAULT_INSTITUSJONSNR = 185


#
# Constants
#


SOURCE_SYSTEM = "sys-1f073188eaba"
AFF_FOO = "FOO"
AFF_FOO_X = "foo-x-62c28012f1"
AFF_FOO_Y = "foo-y-e2ef2cccd9"
AFF_BAR = "BAR"
AFF_BAR_X = "bar-x-62c28012f1"
AFF_BAR_Y = "bar-y-e2ef2cccd9"


@pytest.fixture
def source_system(constant_module, constant_creator):
    return constant_creator(constant_module._AuthoritativeSystemCode,
                            SOURCE_SYSTEM)


@pytest.fixture
def aff_foo(constant_module, constant_creator):
    return constant_creator(constant_module._PersonAffiliationCode, AFF_FOO)


@pytest.fixture
def aff_status_foo_x(constant_module, constant_creator, aff_foo):
    return constant_creator(constant_module._PersonAffStatusCode,
                            aff_foo, AFF_FOO_X)


@pytest.fixture
def aff_status_foo_y(constant_module, constant_creator, aff_foo):
    return constant_creator(constant_module._PersonAffStatusCode,
                            aff_foo, AFF_FOO_Y)


@pytest.fixture
def aff_bar(constant_module, constant_creator):
    return constant_creator(constant_module._PersonAffiliationCode, AFF_BAR)


@pytest.fixture
def aff_status_bar_x(constant_module, constant_creator, aff_bar):
    return constant_creator(constant_module._PersonAffStatusCode,
                            aff_bar, AFF_BAR_X)


@pytest.fixture
def aff_status_bar_y(constant_module, constant_creator, aff_bar):
    return constant_creator(constant_module._PersonAffStatusCode,
                            aff_bar, AFF_BAR_Y)


#
# Helper
#


class _AffHelper(object):

    def __init__(self, source_system):
        self.source = source_system

    def add_aff(self, person, status, ou, last_date=None):
        person.add_affiliation(
            ou_id=ou.entity_id,
            affiliation=status.affiliation,
            source=self.source,
            status=status,
        )
        if last_date:
            person._db.execute(
                """
                UPDATE [:table schema=cerebrum name=person_affiliation_source]
                SET last_date=:last_date
                WHERE
                  person_id=:person_id AND
                  ou_id=:ou_id AND
                  affiliation=:affiliation AND
                  source_system=:source
                """,
                {
                    'person_id': int(person.entity_id),
                    'ou_id': int(ou.entity_id),
                    'affiliation': int(status.affiliation),
                    'source': int(self.source),
                    'last_date': last_date,
                },
            )

    def get_aff(self, person, status, ou):
        for row in person.list_affiliations(
                person_id=person.entity_id,
                source_system=self.source,
                affiliation=status.affiliation,
                status=status,
                ou_id=ou.entity_id,
                include_deleted=False):
            return dict(row)
        return None


#
# Other fixtures
#


@pytest.fixture
def affs(source_system,
         aff_foo, aff_status_foo_x, aff_status_foo_y,
         aff_bar, aff_status_bar_x, aff_status_bar_y):
    """ A collection of affiliation types. """
    aff_types = _AffHelper(source_system)
    aff_types.foo = aff_foo
    aff_types.foo_x = aff_status_foo_x
    aff_types.foo_y = aff_status_foo_y
    aff_types.bar = aff_bar
    aff_types.bar_x = aff_status_bar_x
    aff_types.bar_y = aff_status_bar_y
    return aff_types


@pytest.fixture
def person(person_creator):
    person, _ = next(person_creator(1))
    return person


@pytest.fixture
def ou(ou_creator, cereconf):
    ou, _ = next(ou_creator(1))
    # This is a bit hacky, but AffiliationSync validates that the given ou_id
    # exists with Factory.get("OU"), which in most cases means Stedkode.  Let's
    # upgrade the OU to a Stedkode object here.
    sko = Stedkode.Stedkode(ou._db)
    sko.populate(89, 99, 99,
                 institusjon=cereconf.DEFAULT_INSTITUSJONSNR,
                 parent=ou)
    sko.write_db()
    return sko


@pytest.fixture
def sync(database, source_system):
    return syncs.AffiliationSync(database, source_system)


#
# Tests
#


def test_helpers(person, ou, affs):
    """ check that our helper can set and get affs. """
    assert not affs.get_aff(person, affs.foo_x, ou)
    affs.add_aff(person, affs.foo_x, ou)
    assert affs.get_aff(person, affs.foo_x, ou)


def test_sync_init(sync, source_system):
    assert sync.source_system == source_system


def test_sync_text(affs, sync, person, ou):
    """ check that sync can deal with affiliation strval. """
    ou_id = int(ou.entity_id)
    new = [(AFF_FOO + "/" + AFF_FOO_X, ou_id)]
    added, updated, removed = sync(person, new)
    assert affs.get_aff(person, affs.foo_x, ou)


def test_sync_add_remove(affs, sync, person, ou):
    """ check that sync can add and remove affs. """
    affs.add_aff(person, affs.foo_x, ou)
    ou_id = int(ou.entity_id)

    new = [(affs.bar_y, ou_id)]
    added, updated, removed = sync(person, new)

    # Check add/update/remove return value
    assert added == set([(ou_id, affs.bar, affs.bar_y)])
    assert updated == set()
    assert removed == set([(ou_id, affs.foo, affs.foo_x)])

    # Check that our affs are set as expected
    assert affs.get_aff(person, affs.bar_y, ou)
    assert not affs.get_aff(person, affs.foo_x, ou)


def test_sync_change_status(affs, sync, person, ou):
    """ check that sync can change aff status. """
    affs.add_aff(person, affs.foo_x, ou)
    ou_id = int(ou.entity_id)

    new = [(affs.foo_y, ou_id)]
    added, updated, removed = sync(person, new)

    # Check add/update/remove return value
    assert added == set([(ou_id, affs.foo, affs.foo_y)])
    assert updated == set()
    assert removed == set([(ou_id, affs.foo, affs.foo_x)])

    # Check that our affs are set as expected
    assert affs.get_aff(person, affs.foo_y, ou)
    assert not affs.get_aff(person, affs.foo_x, ou)


def test_sync_update_last_seen(affs, sync, person, ou):
    """ Check that aff sync "touches" affiliations for each sync. """
    last_date = datetime.date.today() - datetime.timedelta(days=3)
    affs.add_aff(person, affs.foo_x, ou, last_date=last_date)
    ou_id = int(ou.entity_id)
    old_aff = affs.get_aff(person, affs.foo_x, ou)

    new = [(affs.foo_x, ou_id)]
    added, updated, removed = sync(person, new)

    assert not added
    assert updated == set([(ou_id, affs.foo, affs.foo_x)])
    assert not removed

    new_aff = affs.get_aff(person, affs.foo_x, ou)
    assert old_aff['last_date'] < new_aff['last_date']


def test_sync_no_affs(affs, sync, person, ou):
    """ Check that aff sync "touches" affiliations for each sync. """
    added, updated, removed = sync(person, [])
    assert not added
    assert not updated
    assert not removed


def test_sync_invalid_aff(affs, sync, person, ou):
    """ Check that sync can change aff status. """
    ou_id = int(ou.entity_id)
    new = [("BAZ/invalid", ou_id)]
    with pytest.raises(ValueError) as exc_info:
        sync(person, new)
    error_msg = six.text_type(exc_info.value)
    assert error_msg.startswith("invalid aff")


def test_sync_invalid_ou(affs, sync, person):
    """ Check that sync can change aff status. """
    ou_id = -1
    new = [(affs.foo_x, ou_id)]
    with pytest.raises(ValueError) as exc_info:
        sync(person, new)
    error_msg = six.text_type(exc_info.value)
    assert error_msg.startswith("invalid ou")
