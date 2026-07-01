"""
Unit tests for `Cerebrum.modules.event_publisher.converters`.

Only tests for account changes.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import pytest

from Cerebrum.modules.event_publisher import converters
from Cerebrum.modules.event_publisher import event


@pytest.fixture()
def account_password_msg(database, clconst):
    change_type = clconst.account_password

    # Param value depends on cereconf.PASSWORD_PLAINTEXT_IN_CHANGE_LOG
    # params = None
    params = {'password': "hunter2"}

    subject = event.EntityRef(123, "account", "example-name")

    # TODO: the context (spreads) doesn't actually have to exist from this
    # point onwards, unless the filter function does any lookups.
    context = ['foo', 'bar']

    return {
        'category': change_type.category,
        'change': change_type.type,
        'context': context,
        'subject': subject,
        'objects': [],
        'data': params,
        'payload': None,
    }


def test_account_password(database, clconst, account_password_msg):
    ev = converters.account_password(
        account_password_msg,
        db=database,
        change_type=clconst.account_password,
    )
    assert ev
    assert ev.event_type == event.PASSWORD
    assert ev.subject == event.EntityRef(123, "account", "example-account")
    assert ev.timestamp is None  # not sent yet
    assert ev.scheduled is None  # not a scheduled event
    assert not ev.objects   # no related objects
    assert ev.context == set(("foo", "bar"))
    assert ev.attributes == set(("password",))
