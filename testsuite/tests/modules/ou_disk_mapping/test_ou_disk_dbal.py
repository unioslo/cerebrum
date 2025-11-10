# encoding: utf-8
"""
Unit tests for :mod:`Cerebrum.modules.ou_disk_mapping.dbal`
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest

from Cerebrum.modules.ou_disk_mapping import dbal


@pytest.fixture
def ou(ou_creator):
    ou, _ = next(ou_creator(1))
    return ou


@pytest.fixture
def person(person_creator):
    person, _ = next(person_creator(1))
    return person


@pytest.fixture
def disk_host(host_creator):
    return host_creator("example-disk-host")


@pytest.fixture
def disk(disk_creator, disk_host):
    return disk_creator(disk_host.entity_id, "default")


@pytest.fixture
def alt_disk(disk_creator, disk_host):
    return disk_creator(disk_host.entity_id, "alt")


@pytest.fixture
def disk_foo(disk_creator, disk_host):
    return disk_creator(disk_host.entity_id, "aff-foo")


@pytest.fixture
def disk_bar_x(disk_creator, disk_host):
    return disk_creator(disk_host.entity_id, "aff-bar-x")


@pytest.fixture
def disk_bar_y(disk_creator, disk_host):
    return disk_creator(disk_host.entity_id, "aff-bar-y")


#
# DBAL tests
#


@pytest.fixture
def disk_mappings(database, const):
    mappings = dbal.OUDiskMapping(database)
    mappings.const = const  # patch with *our* consts...
    return mappings


def test_add_ou_disk_mapping(disk_mappings, ou, aff_status_bar_x, disk):
    disk_mappings.add(ou.entity_id, aff_status_bar_x.affiliation,
                      aff_status_bar_x, disk.entity_id)
    assert True


def test_get_ou_disk_mapping(disk_mappings, ou, aff_status_bar_x, disk):
    disk_mappings.add(ou.entity_id, aff_status_bar_x.affiliation,
                      aff_status_bar_x, disk.entity_id)

    row = disk_mappings.get(ou.entity_id, aff_status_bar_x.affiliation,
                            aff_status_bar_x)
    assert dict(row) == {
        'ou_id': ou.entity_id,
        'aff_code': int(aff_status_bar_x.affiliation),
        'status_code': int(aff_status_bar_x),
        'disk_id': disk.entity_id,
    }


def test_search_ou_disk_mapping(disk_mappings, ou, aff_foo, aff_status_bar_x,
                                disk):
    disk_mappings.add(ou.entity_id, aff_foo, None, disk.entity_id)
    disk_mappings.add(ou.entity_id, aff_status_bar_x.affiliation,
                      aff_status_bar_x, disk.entity_id)

    results = list(
        tuple(row)
        for row in disk_mappings.search(ou_id=int(ou.entity_id))
    )
    assert len(results) == 2
    assert (ou.entity_id, int(aff_foo), None, disk.entity_id) in results
    assert (ou.entity_id, int(aff_status_bar_x.affiliation),
            int(aff_status_bar_x), disk.entity_id) in results


def test_delete_ou_disk_mapping(disk_mappings, ou, aff_status_bar_x,
                                aff_status_bar_y, disk):
    disk_mappings.add(ou.entity_id, aff_status_bar_x.affiliation,
                      aff_status_bar_x, disk.entity_id)
    disk_mappings.add(ou.entity_id, aff_status_bar_y.affiliation,
                      aff_status_bar_y, disk.entity_id)

    before = list(
        tuple(row)
        for row in disk_mappings.search(ou_id=int(ou.entity_id))
    )
    assert len(before) == 2

    disk_mappings.delete(ou.entity_id, aff_status_bar_y.affiliation,
                         aff_status_bar_y)

    after = list(
        tuple(row)
        for row in disk_mappings.search(ou_id=int(ou.entity_id))
    )
    assert len(after) == 1
    assert (ou.entity_id, int(aff_status_bar_x.affiliation),
            int(aff_status_bar_x), disk.entity_id) in after
    assert (ou.entity_id, int(aff_status_bar_y.affiliation),
            int(aff_status_bar_y), disk.entity_id) not in after


def test_update_ou_disk_mapping(disk_mappings, ou, aff_foo, disk, alt_disk):
    disk_mappings.add(ou.entity_id, aff_foo, None, disk.entity_id)

    # change disk:
    disk_mappings.add(ou.entity_id, aff_foo, None, alt_disk.entity_id)

    results = list(
        tuple(row)
        for row in disk_mappings.search(ou_id=int(ou.entity_id))
    )
    assert len(results) == 1
    assert (ou.entity_id, int(aff_foo), None, alt_disk.entity_id) in results
