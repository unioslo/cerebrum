#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Basic tests for Cerebrum.Entity.EntityQuarantine. """
import pytest
from mx import DateTime as dt


similar_date = lambda a, b: (a.day == b.day
                             and a.month == b.month
                             and a.year == b.year)


@pytest.fixture
def Entity(entity_module):
    return getattr(entity_module, 'EntityQuarantine')


@pytest.fixture
def Quarantine(constant_module):
    return getattr(constant_module, '_QuarantineCode')


@pytest.fixture
def quar_x(Quarantine):
    code = Quarantine('d50ecaee9ada9ec4', description='x', duration=None)
    code.insert()
    return code


@pytest.fixture
def quar_y(Quarantine):
    code = Quarantine('930badececa00f15', description='y', duration=10)
    code.insert()
    return code


@pytest.fixture
def entity_obj(Entity, database):
    return Entity(database)


@pytest.fixture
def entity(entity_obj, entity_type):
    entity_obj.populate(entity_type)
    entity_obj.write_db()
    return entity_obj


def test_quarantine(entity, initial_account, quar_x, quar_y):
    entity.add_entity_quarantine(quar_x, initial_account.entity_id,
                                 start=dt.now() - 1)
    assert len(entity.get_entity_quarantine()) == 1

    start, end = dt.now() - 2, dt.now() + 2
    desc = "because"
    created = dt.now()
    entity.add_entity_quarantine(quar_y, initial_account.entity_id,
                                 start=start,
                                 end=end,
                                 description=desc)
    quar = entity.get_entity_quarantine(qtype=quar_y)
    assert len(quar) == 1
    assert quar[0]['quarantine_type'] == quar_y
    assert quar[0]['description'] == desc
    assert quar[0]['disable_until'] is None
    assert similar_date(quar[0]['start_date'], start)
    assert similar_date(quar[0]['end_date'], end)
    assert similar_date(quar[0]['create_date'], created)


def test_get_quarantine(entity, initial_account, quar_x, quar_y):
    entity.add_entity_quarantine(quar_x,
                                 initial_account.entity_id,
                                 start=dt.now() + 1)

    quars = entity.get_entity_quarantine()
    assert len(quars) == 1
    quars = entity.get_entity_quarantine(qtype=quar_y)
    assert len(quars) == 0

    entity.add_entity_quarantine(quar_y,
                                 initial_account.entity_id,
                                 start=dt.now() - 1)
    entity.disable_entity_quarantine(quar_y, dt.now() + 1)

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
