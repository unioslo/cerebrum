# -*- coding: utf-8 -*-
""" Tests for :mod:`Cerebrum.modules.bofhd_requests.request`. """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import datetime
# import locale
import pytz
import pytest
import six

from Cerebrum import Errors
from Cerebrum import Entity
from Cerebrum.Constants import _EntityTypeCode
from Cerebrum.modules.bofhd.errors import CerebrumError
from Cerebrum.modules.bofhd_requests import constants
from Cerebrum.modules.bofhd_requests import request


OPERATIONS = [
    constants.Constants.bofh_archive_user,
    constants.Constants.bofh_delete_user,
    constants.Constants.bofh_email_convert,
    constants.Constants.bofh_email_create,
    constants.Constants.bofh_email_delete,
    constants.Constants.bofh_email_restore,
    constants.Constants.bofh_homedir_restore,
    constants.Constants.bofh_move_give,
    constants.Constants.bofh_move_request,
    constants.Constants.bofh_move_student,
    constants.Constants.bofh_move_user,
    constants.Constants.bofh_move_user_now,
    constants.Constants.bofh_quarantine_refresh,
    constants.Constants.bofh_sympa_create,
    constants.Constants.bofh_sympa_remove,
]


@pytest.fixture(autouse=True)
def const(database, constant_module):
    # Add BofhdRequests constant mixin
    const_cls = type(
        str("_Constants"),
        (constants.Constants, constant_module.Constants),
        {},
    )
    const = const_cls(database)
    # Ensure constants exists
    for op in OPERATIONS:
        try:
            int(op)
        except Errors.NotFoundError:
            op.insert()
    return const


@pytest.fixture
def br(database, const):
    return request.BofhdRequests(database, const)


def test_request_init(br):
    assert br
    assert br.now
    assert br.batch_time
    assert br.conflicts


def test_get_operations(br, const):
    expected = set(
        (six.text_type(c), c.description)
        for c in OPERATIONS
    )
    ops = set(
        (r['code_str'], r['description'])
        for r in br.get_operations()
    )
    # There may be operations defined in the db that aren't defined in
    # code...
    assert expected - ops == set()


def test_get_conflicts(br, const):
    conflict = br.get_conflicts(const.bofh_move_user)
    assert set(conflict) == set(
        int(code) for code in (
            const.bofh_move_user,
            const.bofh_move_request,
            const.bofh_move_student,
            const.bofh_move_user_now,
            const.bofh_delete_user,
        )
    )


def test_get_conflicts__no_conflict(br, const):
    conflict = br.get_conflicts(const.bofh_quarantine_refresh)
    assert conflict == []


@pytest.fixture
def entity_type(constant_creator):
    return constant_creator(
        _EntityTypeCode,
        "test-entity-36af",
        description="Test entity type for {}".format(__name__),
    )


@pytest.fixture
def entity(database, entity_type):
    """ A simple AdAttributeCleanupMixin entity. """
    obj = Entity.Entity(database)
    obj.populate(entity_type)
    obj.write_db()
    return obj


WHEN_PAST = pytz.timezone("Europe/Oslo").localize(
    datetime.datetime.combine(
        datetime.date.today() - datetime.timedelta(days=2),
        datetime.time(21),
    )
)


WHEN_FUTURE = pytz.timezone("Europe/Oslo").localize(
    datetime.datetime.combine(
        datetime.date.today() + datetime.timedelta(days=2),
        datetime.time(21),
    )
)


@pytest.fixture
def example_request(const, entity, initial_account):
    requestee_id = int(initial_account.entity_id)
    entity_id = int(entity.entity_id)
    destination_id = int(entity.entity_id)
    op_code = int(const.bofh_email_create)
    when = WHEN_FUTURE
    state_data = "test-state"
    return {
        'requestee_id': requestee_id,
        'run_at': when,
        'operation': op_code,
        'entity_id': entity_id,
        'destination_id': destination_id,
        'state_data': state_data,
    }


def _add_request(br, request_data):
    kwargs = dict(request_data)
    kwargs['operator'] = kwargs.pop('requestee_id')
    kwargs['when'] = kwargs.pop('run_at')
    kwargs['op_code'] = kwargs.pop('operation')
    return br.add_request(**kwargs)


def test_add_request(br, example_request):
    request_id = _add_request(br, example_request)
    assert request_id


def test_add_request__conflict(br, const, example_request):
    first = dict(example_request)
    first['op_code'] = const.bofh_email_create
    _add_request(br, first)

    second = dict(example_request)
    second['op_code'] = const.bofh_email_create

    # TODO: This seems wrong - bofhd error on a generic module?
    with pytest.raises(CerebrumError) as exc_info:
        _add_request(br, second)

    error_msg = six.text_type(exc_info.value)
    assert "Conflicting request exists" in error_msg


def test_get_requests(br, example_request):
    request_id = _add_request(br, example_request)
    expected = dict(example_request)
    expected['request_id'] = int(request_id)

    requests = br.get_requests(request_id=request_id)
    assert len(requests) == 1
    assert dict(requests[0]) == expected


def test_get_requests_runnable(br, example_request):
    request_id = _add_request(br, example_request)
    expected = dict(example_request)
    expected['request_id'] = int(request_id)

    requests = br.get_requests(request_id=request_id, only_runnable=True)
    assert len(requests) == 0


def test_delay_request(br, example_request):
    request_id = _add_request(br, example_request)
    original = example_request['run_at']
    expected = original + datetime.timedelta(minutes=30)
    br.delay_request(request_id, minutes=30)

    requests = br.get_requests(request_id=request_id)
    assert requests[0]['run_at'] == expected


def test_delete_request(br, example_request):
    request_id = _add_request(br, example_request)
    br.delete_request(request_id=request_id)
    requests = br.get_requests(request_id=request_id)
    assert len(requests) == 0


def test_delete_request__nonexisting(br, entity):
    br.delete_request(entity_id=int(entity.entity_id))
    assert True
