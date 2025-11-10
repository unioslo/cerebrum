# encoding: utf-8
"""
Common fixtures for :mod:`Cerebrum.modules.ou_disk_mapping` tests

These tests need a lot of test setup - the ou disk mappings themselves need org
units, affiliations, hosts and disks.  As we test the mapping, we also need
persons with affiliations.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest

import Cerebrum.Disk
import Cerebrum.OU
from Cerebrum.testutils import datasource


#
# Affiliations - re-used from the import_utils tests
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
# Entity fixtures
#


@pytest.fixture
def ou_cls():
    return Cerebrum.OU.OU


@pytest.fixture
def ou_creator(database, const, ou_cls):
    """
    A helper fixture to create org unit objects.
    """
    ou_ds = datasource.BasicOUSource()

    def _create_org_units(limit=1):
        for ou_dict in ou_ds(limit=limit):
            ou = ou_cls(database)
            ou.populate()
            ou.write_db()
            ou_dict['entity_id'] = ou.entity_id
            yield ou, ou_dict

    return _create_org_units


@pytest.fixture
def host_cls():
    return Cerebrum.Disk.Host


@pytest.fixture
def host_creator(database, host_cls):
    def _create_host(hostname):
        host_obj = host_cls(database)
        host_obj.populate(
            hostname,
            "Test host {}, for tests in {}".format(hostname, __name__),
        )
        host_obj.write_db()
        return host_obj

    return _create_host


@pytest.fixture
def disk_cls():
    return Cerebrum.Disk.Disk


@pytest.fixture
def disk_creator(database, disk_cls):
    def _create_disk(host_id, name):
        disk_obj = disk_cls(database)
        path = "/tests/ou-disk-mapping/{}".format(name)
        disk_obj.populate(
            host_id,
            path,
            "Example disk {}, for test in {}".format(name, __name__),
        )
        disk_obj.write_db()
        return disk_obj

    return _create_disk
