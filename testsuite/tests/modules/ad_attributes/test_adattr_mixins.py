# -*- coding: utf-8 -*-
""" Tests for :mod:`Cerebrum.modules.ad_attributes.adattr_mixins` """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest

from Cerebrum import Errors
from Cerebrum import Entity
from Cerebrum.Constants import _EntityTypeCode
# from Cerebrum.modules.ad_attributes import adattr_db
from Cerebrum.modules.ad_attributes import adattr_mixins


@pytest.fixture
def entity_type(constant_creator):
    return constant_creator(
        _EntityTypeCode,
        "test-entity-36af",
    )


@pytest.fixture
def adattr_cleanup_obj(database, entity_type):
    """ A simple AdAttributeCleanupMixin entity. """
    obj = adattr_mixins.AdAttributeCleanupMixin(database)
    obj.populate(entity_type)
    obj.write_db()
    return obj


@pytest.fixture
def adattr_obj(database, entity_type):
    """ A simple AdAttributeCleanupMixin entity. """
    obj = adattr_mixins.AdAttributeMixin(database)
    obj.populate(entity_type)
    obj.write_db()
    return obj


def test_adattr_cleanup_entity_delete(database, adattr_cleanup_obj):
    obj = adattr_cleanup_obj
    entity_id = int(obj.entity_id)

    obj.delete()

    entity = Entity.Entity(database)
    with pytest.raises(Errors.NotFoundError):
        entity.find(entity_id)


def test_adattr_entity_delete(database, adattr_obj):
    obj = adattr_obj
    entity_id = int(obj.entity_id)

    obj.delete()

    entity = Entity.Entity(database)
    with pytest.raises(Errors.NotFoundError):
        entity.find(entity_id)
