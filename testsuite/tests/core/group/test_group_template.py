# -*- coding: utf-8 -*-
""" Unit tests for :mod:`Cerebrum.group.template`. """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest
import six

from Cerebrum import Errors
from Cerebrum.group import template as group_template
from Cerebrum.testutils import datasource


SPREAD = "c8df4be6b"
VISIBILITY = "8d9cbd5a"
TYPE = "3e94030c"


@pytest.fixture
def group_spread(constant_creator, constant_module, constants):
    """ A new, unique group spread. """
    return constant_creator(
        constant_module._SpreadCode,
        SPREAD,
        entity_type=constants.entity_group,
    )


@pytest.fixture
def group_visibility(constant_creator, constant_module):
    """ A new, unique group visibility setting. """
    return constant_creator(
        constant_module._GroupVisibilityCode,
        VISIBILITY,
    )


@pytest.fixture
def group_type(constant_creator, constant_module):
    """ A new, unique group type setting. """
    return constant_creator(
        constant_module._GroupTypeCode,
        TYPE,
    )


@pytest.fixture
def group_ds():
    """ Data source for creating groups. """
    return datasource.BasicGroupSource()


def test_group_template__init(group_ds):
    entry = next(group_ds(limit=1))
    group_name = entry['group_name']
    group_description = entry['description']
    conflict_resolution = group_template.GroupTemplate.CONFLICT_ERROR

    template = group_template.GroupTemplate(
        group_name,
        group_description,
        group_type=TYPE,
        group_visibility=VISIBILITY,
        conflict=conflict_resolution,
    )

    assert template.group_name == group_name
    assert template.group_description == group_description
    assert template.group_type == TYPE
    assert template.group_visibility == VISIBILITY
    assert template.conflict_resolution == conflict_resolution


def test_group_template__init_bogus_resolution(group_ds):
    entry = next(group_ds(limit=1))
    group_name = entry['group_name']
    group_description = entry['description']
    conflict_resolution = "foo"

    with pytest.raises(ValueError) as exc_info:
        group_template.GroupTemplate(
            group_name,
            group_description,
            group_type=TYPE,
            group_visibility=VISIBILITY,
            conflict=conflict_resolution,
        )

    error_msg = six.text_type(exc_info.value)
    assert error_msg.startswith("invalid conflict resolution:")


@pytest.fixture
def template(group_ds):
    entry = next(group_ds(limit=1))
    group_name = entry['group_name']
    group_description = entry['description']
    conflict_resolution = group_template.GroupTemplate.CONFLICT_ERROR

    return group_template.GroupTemplate(
        group_name,
        group_description,
        group_type=TYPE,
        group_visibility=VISIBILITY,
        conflict=conflict_resolution,
    )


def test_group_template__create(database, template, group_type,
                                group_visibility):
    group = template(database)
    assert group.group_name == template.group_name
    assert group.description == template.group_description
    assert group.group_type == group_type
    assert group.visibility == group_visibility
    assert group.expire_date is None


@pytest.fixture
def group(database, template, group_type, group_visibility):
    return template(database)


def test_group_template__update_error(database, group, template):
    # Change template
    new_description = "Something else"
    template.group_description = new_description

    # Update group should cause an error, because the description is out of
    # date, and conflict_resolution is set to "error"
    with pytest.raises(ValueError) as exc_info:
        template(database)

    error_msg = six.text_type(exc_info.value)
    assert error_msg.startswith("incompatible group")


def test_group_template__update_ignore(database, group, template):
    old_description = group.description
    new_description = "Something else"

    # Change template
    template.conflict_resolution = group_template.GroupTemplate.CONFLICT_IGNORE
    template.group_description = new_description

    # Update group should ignore the changes, because even though the
    # description is out of date, conflict_resolution is set to "ignore"
    new_group = template(database)
    assert new_group.entity_id == group.entity_id
    assert new_group.description == old_description


def test_group_template__update(database, group, template):
    old_description = group.description
    new_description = "Something else"

    # Change template
    template.conflict_resolution = group_template.GroupTemplate.CONFLICT_UPDATE
    template.group_description = new_description

    # Update group should apply the the description change, because
    # conflict_resolution is set to "update"
    new_group = template(database)
    assert new_group.entity_id == group.entity_id
    assert new_group.description != old_description
    assert new_group.description == new_description


def test_group_template__update_no_change(database, group, template):
    # Update group should apply the the description change, because
    # conflict_resolution is set to "update"
    new_group = template(database)
    assert new_group.entity_id == group.entity_id
    assert new_group.description == group.description
    assert new_group.group_type == group.group_type
    assert new_group.visibility == group.visibility


def test_group_template__require_present(database, group, template):
    # Update group should apply the the description change, because
    # conflict_resolution is set to "update"
    new_group = template.require(database)
    assert new_group.entity_id == group.entity_id


def test_group_template__require_missing(database, template):
    # Update group should apply the the description change, because
    # conflict_resolution is set to "update"
    with pytest.raises(Errors.NotFoundError):
        template.require(database)
