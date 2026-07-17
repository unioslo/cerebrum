# encoding: utf-8
"""
Unit tests for :mod:`Cerebrum.modules.ou_disk_mapping.mixins`
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest

from Cerebrum import Errors
from Cerebrum.modules.ou_disk_mapping import dbal
from Cerebrum.modules.ou_disk_mapping import mixins


@pytest.fixture
def ou_cls():
    return mixins.OUMixin


@pytest.fixture
def disk_cls():
    return mixins.DiskMixin


@pytest.fixture
def ou(ou_creator):
    ou, _ = next(ou_creator(1))
    return ou


@pytest.fixture
def disk_host(host_creator):
    return host_creator("example-disk-host")


@pytest.fixture
def disk(disk_creator, disk_host):
    return disk_creator(disk_host.entity_id, "default")


@pytest.fixture
def disk_mappings(database, const):
    mappings = dbal.OUDiskMapping(database)
    mappings.const = const  # patch with *our* consts...
    return mappings


def test_delete_disk(disk_mappings, ou, disk, aff_bar, aff_status_bar_x):
    ou_id = int(ou.entity_id)
    disk_id = int(disk.entity_id)
    disk_mappings.add(ou_id, None, None, disk_id)
    disk_mappings.add(ou_id, aff_bar, None, disk_id)
    disk_mappings.add(ou_id, aff_bar, aff_status_bar_x, disk_id)

    assert disk_mappings.get(ou_id, None, None)
    disk.delete()
    with pytest.raises(Errors.NotFoundError):
        disk_mappings.get(ou_id, None, None)


def test_delete_ou(disk_mappings, ou, disk, aff_bar, aff_status_bar_x):
    ou_id = int(ou.entity_id)
    disk_id = int(disk.entity_id)
    disk_mappings.add(ou_id, None, None, disk_id)
    disk_mappings.add(ou_id, aff_bar, None, disk_id)
    disk_mappings.add(ou_id, aff_bar, aff_status_bar_x, disk_id)

    assert disk_mappings.get(ou_id, None, None)
    ou.delete()
    with pytest.raises(Errors.NotFoundError):
        disk_mappings.get(ou_id, None, None)
