# encoding: utf-8
"""
Unit tests for :mod:`Cerebrum.modules.ou_disk_mapping.utils`
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest

from Cerebrum import Errors
from Cerebrum.modules.no import Stedkode
from Cerebrum.modules.ou_disk_mapping import dbal
from Cerebrum.modules.ou_disk_mapping import utils


PERSPECTIVE = "test-26ef9914"


@pytest.fixture
def perspective(constant_module, constant_creator):
    return constant_creator(constant_module._OUPerspectiveCode, PERSPECTIVE)


@pytest.fixture
def root(ou_creator, cereconf, perspective):
    ou, _ = next(ou_creator(1))
    ou.set_parent(perspective, None)
    return ou


@pytest.fixture
def ou(ou_creator, cereconf, perspective, root):
    ou, _ = next(ou_creator(1))
    ou.set_parent(perspective, root.entity_id)
    return ou


@pytest.fixture
def disk_host(host_creator):
    return host_creator("example-disk-host")


@pytest.fixture
def disk_default(disk_creator, disk_host):
    return disk_creator(disk_host.entity_id, "default")


@pytest.fixture
def disk_aff(disk_creator, disk_host):
    return disk_creator(disk_host.entity_id, "aff")


@pytest.fixture
def disk_status(disk_creator, disk_host):
    return disk_creator(disk_host.entity_id, "status")


@pytest.fixture
def disk_mappings(database, const):
    mappings = dbal.OUDiskMapping(database)
    mappings.const = const  # patch with *our* consts...
    return mappings


# Sigh, `utils.get_parent_id()` uses Factory.get("OU"), which is usually a
# "Stedkode".  Stedkode requires a location code to be defined for basic
# things like `find()` to work, so we need to promote our org units for this to
# work.
#
# Other than patching the Factory class, there are no good ways to make this
# work for ou_cls with *and* without Stedkode...  Do we even need
# `utils.get_parent_id()`?  If so, we should probably re-implement it using
# `perspective_db.find_parents()`...


@pytest.fixture
def promote_stedkode(cereconf):
    def _promote_ou(ou, faculty, department, group):
        orgno = cereconf.DEFAULT_INSTITUSJONSNR
        sko = Stedkode.Stedkode(ou._db)
        sko.populate(faculty, department, group, institusjon=orgno, parent=ou)
        sko.write_db()
        return sko

    return _promote_ou


@pytest.fixture
def root_sko(promote_stedkode, root):
    return promote_stedkode(root, 89, 99, 90)


@pytest.fixture
def ou_sko(promote_stedkode, ou):
    return promote_stedkode(ou, 89, 99, 91)


#
# tests
#


def test_get_parent_id_root(database, root_sko, perspective):
    root_parent = utils.get_parent_id(database, root_sko.entity_id,
                                      perspective)
    assert root_parent is None


def test_get_parent_id(database, root_sko, ou_sko, perspective):
    ou_parent = utils.get_parent_id(database, ou_sko.entity_id, perspective)
    assert ou_parent == root_sko.entity_id


def test_get_disk_rule_hit(disk_mappings, ou, aff_foo, aff_bar,
                           aff_status_bar_x, aff_status_bar_y,
                           disk_default, disk_aff, disk_status):
    # setup
    disk_mappings.add(ou.entity_id, None, None, disk_default.entity_id)
    disk_mappings.add(ou.entity_id, aff_bar, None, disk_aff.entity_id)
    disk_mappings.add(ou.entity_id, aff_bar, aff_status_bar_x,
                      disk_status.entity_id)

    # test for a specific ou/aff/status match
    row = utils.get_disk_rule(disk_mappings, ou.entity_id, aff_bar,
                              aff_status_bar_x)
    assert row['disk_id'] == disk_status.entity_id

    # test for a specific ou/aff match without status
    row = utils.get_disk_rule(disk_mappings, ou.entity_id, aff_bar, None)
    assert row['disk_id'] == disk_aff.entity_id

    # test for a specific ou match without aff/status
    row = utils.get_disk_rule(disk_mappings, ou.entity_id, None, None)
    assert row['disk_id'] == disk_default.entity_id

    # test ou/aff fallback match for missing ou/aff/status
    row = utils.get_disk_rule(disk_mappings, ou.entity_id, aff_bar,
                              aff_status_bar_y)
    assert row['disk_id'] == disk_aff.entity_id

    # test ou fallback match for missing ou/aff
    row = utils.get_disk_rule(disk_mappings, ou.entity_id, aff_foo, None)
    assert row['disk_id'] == disk_default.entity_id


def test_get_disk_rule_miss(disk_mappings, ou, aff_foo):
    # no setup - shouldn't be any rules for the given ou
    with pytest.raises(Errors.NotFoundError):
        utils.get_disk_rule(disk_mappings, ou.entity_id, aff_foo, None)


def test_resolve_disk_hit(disk_mappings, perspective, root, ou,
                          aff_foo, aff_bar, disk_default, disk_aff):
    # setup
    disk_mappings.add(root.entity_id, None, None, disk_default.entity_id)
    disk_mappings.add(ou.entity_id, aff_foo, None, disk_aff.entity_id)

    # aff should match rule for disk_aff
    row = utils.resolve_disk(disk_mappings, ou.entity_id, aff_foo, None,
                             perspective)
    assert row['ou_id'] == ou.entity_id
    assert row['disk_id'] == disk_aff.entity_id

    # aff should fall back to parent ou rules
    row = utils.resolve_disk(disk_mappings, ou.entity_id, aff_bar, None,
                             perspective)
    assert row['ou_id'] == root.entity_id
    assert row['disk_id'] == disk_default.entity_id


def test_resolve_disk_miss(disk_mappings, perspective, root, ou,
                           aff_foo, aff_bar, disk_default, disk_aff):
    with pytest.raises(Errors.NotFoundError):
        utils.resolve_disk(disk_mappings, ou.entity_id, aff_bar, None,
                           perspective)
