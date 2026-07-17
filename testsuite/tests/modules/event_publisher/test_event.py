# encoding: utf-8
""" Unit tests for `Cerebrum.modules.event_publisher.event`. """
import datetime

# import pytest

from Cerebrum.modules.event_publisher import event
from Cerebrum.utils import date as date_utils


#
# EntityType tests
#


def test_event_type_is_singleton():
    """ Two event types with the same verb are actually the same object. """
    first_object = event.EventType("foo", "some description")
    second_object = event.EventType("foo", "some other description")
    assert second_object is first_object


def test_event_type_is_first():
    """ A second event type of the same verb cannot alter the description.  """
    event.EventType("foo", "some description")
    second_object = event.EventType("foo", "some other description")
    assert second_object.description == "some description"


def test_singleton_multiple():
    """ Two event types with different verbs are *not* the same singleton. """
    first_object = event.EventType("foo", "description")
    second_object = event.EventType("bar", "description")
    assert second_object is not first_object


#
# EntityRef tests
#


def test_entity_ref_init():
    ref = event.EntityRef(123, "account", "example")
    assert ref.entity_id == 123
    assert ref.entity_type == "account"
    assert ref.ident == "example"


def test_entity_ref_to_dict():
    ref = event.EntityRef(123, "account", "example")
    assert ref.to_dict() == {
        'entity_id': 123,
        'entity_type': "account",
        'ident': "example",
    }


def test_entity_ref_equal():
    """ Two references with the same entity-id are equal. """
    a = event.EntityRef(123, "account", "foo")
    b = event.EntityRef(123, "group", "bar")
    assert a == b


def test_entity_ref_not_equal():
    """ Two references with different entity-id are not equal. """
    a = event.EntityRef(123, "foo", "bar")
    b = event.EntityRef(321, "foo", "bar")
    assert a != b


def test_entity_ref_hash():
    """ Two references with the same entity-id are the same. """
    a = event.EntityRef(123, "account", "foo")
    b = event.EntityRef(123, "account", "foo")
    assert hash(a) == hash(b)


def test_entity_ref_hash_different_id():
    """ Two references with different entity-id are not the same. """
    a = event.EntityRef(123, "foo", "bar")
    b = event.EntityRef(321, "foo", "bar")
    assert hash(a) != hash(b)


def test_entity_ref_hash_different_ident():
    """ Two references with different ident are not the same. """
    a = event.EntityRef(123, "foo", "bar")
    b = event.EntityRef(123, "foo", "baz")
    assert hash(a) != hash(b)


#
# DateTimeDescriptor tests
#


def test_datetime_descriptor_init():
    obj = event.DateTimeDescriptor("slot")
    assert obj.slot == "slot"


def test_datetime_descriptor_get_cls():
    """ __get__ on a class returns the descriptor itself. """

    class _Container(object):
        attr = event.DateTimeDescriptor("foo")

    desc = _Container.attr
    assert isinstance(desc, event.DateTimeDescriptor)
    assert desc.slot == "foo"


def test_datetime_descriptor_get_empty():
    """ __get__ without a value returns None. """

    class _Container(object):
        attr = event.DateTimeDescriptor("foo")

    obj = _Container()
    assert obj.attr is None


epoch_timestamp = 0
epoch_naive = datetime.datetime(1970, 1, 1, 0)
epoch_aware_utc = date_utils.UTC.localize(epoch_naive)


def test_datetime_descriptor_get():
    """ __get__ returns the referenced attribute """

    class _Container(object):
        attr = event.DateTimeDescriptor("foo")

    obj = _Container()
    obj.foo = epoch_aware_utc
    assert obj.attr == obj.foo


def test_datetime_descriptor_del():
    """ __delete__ removes the referenced attribute. """

    class _Container(object):
        attr = event.DateTimeDescriptor("foo")

    obj = _Container()
    obj.foo = epoch_aware_utc
    del obj.attr
    assert not hasattr(obj, "foo")


def test_datetime_descriptor_del_empty():
    """ __delete__ does not fail if the referenced attribute is missing. """

    class _Container(object):
        attr = event.DateTimeDescriptor("foo")

    obj = _Container()
    del obj.attr


def test_datetime_descriptor_set():
    """ setting a tz-aware datetime results in a tz-aware datetime object. """

    class _Container(object):
        attr = event.DateTimeDescriptor("foo")

    obj = _Container()
    obj.attr = epoch_aware_utc
    assert obj.foo == epoch_aware_utc


def test_datetime_descriptor_set_timestamp():
    """ setting a timestamp results in a tz-aware datetime object. """

    class _Container(object):
        attr = event.DateTimeDescriptor("foo")

    obj = _Container()
    obj.attr = epoch_timestamp
    assert obj.foo == epoch_aware_utc


#
# Event tests
#


def test_event_init_min():
    event_type = event.EventType("add", "description")
    ev = event.Event(event_type)
    assert ev
    assert ev.event_type == event_type
    assert not ev.subject
    assert not ev.timestamp
    assert not ev.scheduled
    assert not ev.objects
    assert not ev.context
    assert not ev.attributes


def test_event_init_all():
    event_type = event.EventType("add", "description")
    subject = event.EntityRef(1, "account", "foo")
    objects = [event.EntityRef(2, "group", "bar")]
    context = ["ctx-foo", "ctx-bar", "ctx-foo"]
    attrs = ["attrFoo", "attrBar", "attrFoo"]

    ev = event.Event(
        event_type,
        subject=subject,
        timestamp=epoch_aware_utc,
        scheduled=epoch_timestamp,
        objects=objects,
        context=context,
        attributes=attrs,
    )
    assert ev
    assert ev.event_type == event_type
    assert ev.subject == subject
    assert ev.timestamp == epoch_aware_utc
    assert ev.scheduled == epoch_aware_utc
    assert ev.objects == set(objects)
    assert ev.context == set(context)
    assert ev.attributes == set(attrs)


# Test basic merge-ability
# TODO: This should be tested more extensively


def test_mergeable_modify_account_twice():
    ref = event.EntityRef(1, "account", "foo")
    a = event.Event(event.MODIFY, subject=ref)
    b = event.Event(event.MODIFY, subject=ref)
    assert a.mergeable(b)


def test_not_mergeable_modify_two_accounts():
    ref_a = event.EntityRef(1, "account", "foo")
    ref_b = event.EntityRef(2, "account", "bar")
    a = event.Event(event.MODIFY, subject=ref_a)
    b = event.Event(event.MODIFY, subject=ref_b)
    assert not a.mergeable(b)


def test_merge_modify_account_twice():
    ref = event.EntityRef(1, "account", "foo")
    a = event.Event(event.MODIFY, subject=ref, attributes=["foo"])
    b = event.Event(event.MODIFY, subject=ref, attributes=["bar"])
    merge_list = a.merge(b)
    assert len(merge_list) == 1
    c = merge_list[0]
    assert c.event_type == event.MODIFY
    assert c.subject == ref
    assert c.attributes == set(("foo", "bar"))


def test_mergeable_create_and_modify_account():
    ref = event.EntityRef(1, "account", "foo")
    a = event.Event(event.CREATE, subject=ref)
    b = event.Event(event.MODIFY, subject=ref)
    assert a.mergeable(b)


def test_merge_create_and_modify_account():
    ref = event.EntityRef(1, "account", "foo")
    a = event.Event(event.CREATE, subject=ref, attributes=["foo"])
    b = event.Event(event.MODIFY, subject=ref, attributes=["bar"])
    merge_list = a.merge(b)
    assert len(merge_list) == 1
    c = merge_list[0]
    assert c.event_type == event.CREATE
    assert c.subject == ref
    assert c.attributes == set(("foo", "bar"))


def test_merge_event_list():
    account_a = event.EntityRef(1, "account", "foo")
    account_b = event.EntityRef(2, "account", "bar")
    events = [
        # create a
        event.Event(event.CREATE, subject=account_a, attributes=["foo"]),
        # modify b
        event.Event(event.MODIFY, subject=account_b, attributes=["bar"]),
        # modify b again
        event.Event(event.MODIFY, subject=account_b, attributes=["baz"]),
        # modify a
        event.Event(event.MODIFY, subject=account_a, attributes=["quux"]),
    ]

    merged = event.merge_events(events)

    # should merge to two events: [CREATE a, MODIFY b]
    assert len(merged) == 2

    # events for a single subject has a defined order, but the subject-order is
    # non-deterministic.  Let's sort, so we know our event for *account_a* is
    # the first one
    merged.sort(key=lambda e: e.subject.entity_id)

    # should be CREATE account_a with attrs [foo, quux]
    first = merged[0]
    assert first.event_type == event.CREATE
    assert first.attributes == set(("foo", "quux"))
    assert first.subject == account_a

    # should be MODIFY account_b with attrs [bar, baz]
    second = merged[1]
    assert second.event_type == event.MODIFY
    assert second.attributes == set(("bar", "baz"))
    assert second.subject == account_b
