# encoding: utf-8
#
# Copyright 2016-2023 University of Oslo, Norway
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
"""
Basic tests for ``Cerebrum.Entity.EntityQuarantine``
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import datetime

import pytest

from Cerebrum.utils import date_compat


today = datetime.date.today()
tomorrow = today + datetime.timedelta(days=1)
yesterday = today - datetime.timedelta(days=1)


@pytest.fixture
def entity_cls(entity_module):
    return getattr(entity_module, 'EntityQuarantine')


@pytest.fixture
def quarantine_cls(constant_module):
    return getattr(constant_module, '_QuarantineCode')


@pytest.fixture
def quar_x(quarantine_cls):
    code = quarantine_cls('d50ecaee9ada9ec4', description='x', duration=None)
    code.insert()
    return code


@pytest.fixture
def quar_y(quarantine_cls):
    code = quarantine_cls('930badececa00f15', description='y', duration=10)
    code.insert()
    return code


@pytest.fixture
def entity_obj(entity_cls, database):
    return entity_cls(database)


@pytest.fixture
def entity(entity_obj, entity_type):
    entity_obj.populate(entity_type)
    entity_obj.write_db()
    return entity_obj


def test_quarantine(entity, initial_account, quar_x, quar_y):
    entity.add_entity_quarantine(quar_x, initial_account.entity_id,
                                 start=yesterday)
    assert len(entity.get_entity_quarantine()) == 1
    start, end = yesterday, tomorrow
    desc = "because"
    entity.add_entity_quarantine(quar_y, initial_account.entity_id,
                                 start=start, end=end,
                                 description=desc)
    rows = entity.get_entity_quarantine(qtype=quar_y)
    assert len(rows) == 1
    row = rows[0]
    assert row['quarantine_type'] == quar_y
    assert row['description'] == desc
    assert row['disable_until'] is None
    assert date_compat.get_date(row['start_date']) == start
    assert date_compat.get_date(row['end_date']) == end
    assert date_compat.get_date(row['create_date']) == today


def test_get_quarantine(entity, initial_account, quar_x, quar_y):
    entity.add_entity_quarantine(quar_x,
                                 initial_account.entity_id,
                                 start=tomorrow)

    quars = entity.get_entity_quarantine()
    assert len(quars) == 1
    quars = entity.get_entity_quarantine(qtype=quar_y)
    assert len(quars) == 0

    entity.add_entity_quarantine(quar_y,
                                 initial_account.entity_id,
                                 start=yesterday)
    entity.disable_entity_quarantine(quar_y, tomorrow)

    quars = entity.get_entity_quarantine()
    assert len(quars) == 2

    quars = entity.get_entity_quarantine(qtype=quar_x)
    assert len(quars) == 1
    assert quars[0]['quarantine_type'] == quar_x

    quars = entity.get_entity_quarantine(qtype=quar_x, only_active=True)
    assert len(quars) == 0

    quars = entity.get_entity_quarantine(qtype=quar_y,
                                         filter_disable_until=True)
    assert len(quars) == 0
