#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2015-2024 University of Oslo, Norway
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
Module used by publisher to convert 'raw' events into exportable messages.

This module contains mappers to turn changelog records into events for
publishing.

General behaviour:

1. :class:`.eventlog.EventLog` uses :class:`.EventFilter` to create an
   :class:`.event.Event` object.

2. The *EventFilter* calls the appropriate filter function for the change type

3. If the filter function returns an Event object, then an event is queued for
   publishing - otherwise the changelog won't result in an event

Note that the individual event may be *merged* with other events, outside the
control of this module.  E.g. an entity *create* followed by an entity *modify*
will be turned into a single entity *create* if it all happens in a single
transaction.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import datetime
import logging
import re
from collections import OrderedDict

import six

from Cerebrum.Utils import Factory
from Cerebrum.utils.date import parse_datetime
from Cerebrum.utils.date_compat import get_datetime_tz

from . import event
from .utils import get_entity_ref

logger = logging.getLogger(__name__)


# Missing event categories
# categories:
#     ac_type -> ?
#     ad_attr -> ad_attribute
#     disk -> ?
#     disk_quota -> ?
#     dlgroup -> distribution_group
#     e_account -> account
#     e_group -> group
#     email_address -> email
#     email_forward -> email
#     email_quota -> email
#     email_scan -> email
#     email_sfilter -> email
#     email_tfilter -> email
#     email_vacation -> email
#     entity_addr -> address
#     entity_cinfo -> contact_info
#     entity_name -> ident?
#     entity_note -> note
#     guest -> wlan_account
#     homedir -> ?
#     ou -> orgunit
#     posix -> account, group
#     quarantine -> ?
#     spread -> ?
#     trait -> ?
#
#     tidy change types:
#         use verbs
#         * add
#         * remove
#         * set
#         * unset
#         * update


class EventFilter(object):
    """ Filter with database. """

    callbacks = OrderedDict()

    def __init__(self, db):
        self.db = db

    def __call__(self, message, change_type, **kwargs):
        """
        Generate an event.

        :param dict message: Message data.
        :param ChangeTypeCode change_type: The change type.

        :return Event:
            Returns an event object, or None if no event should be issued for
            the given change.
        """
        category, change = message['category'], message['change']
        fn = self.get_callback(category, change)
        return fn(message,
                  db=self.db,
                  change_type=change_type,
                  **kwargs)

    @classmethod
    def register(cls, category, change=None):
        """ Register an event generator for a given change type.

        >>> @EventFilter.register('person_aff', 'modify')
        ... def person_aff(msg, **kwargs):
        ...     return event.Event(event.MODIFY)

        >>> @EventFilter.register('person_aff', '(add|remove)')
        ... def person_other(msg):
        ...    return None


        """
        key = re.compile('^{0}:{1}$'.format(category, change or '.*'))

        def wrapper(fn):
            cls.callbacks[key] = fn
            return fn
        return wrapper

    @classmethod
    def get_callback(cls, category, change):
        # TODO: Will change ever be empty? And should we match an empty
        # change value?
        term = '{0}:{1}'.format(category, change or '')
        for key in cls.callbacks:
            if key.match(term):
                return cls.callbacks[key]
        return lambda *a, **kw: None


def _stringify_code(msg, field, code_converter):
    """ Convert a code to a string.

    :type msg: dict
    :param msg: The message to convert
    :type field: basestring
    :param field: The key whose value we'll convert.
    :type code_converter: _CerebrumCode
    :param code_converter: The converter to use for the code.
    """
    code = msg.get('data', {}).get(field)
    if code and isinstance(code, code_converter):
        msg['data'][field] = six.text_type(code)
    elif code:
        msg['data'][field] = six.text_type(code_converter(code))


def _rename_key(msg, field, new_field):
    """Rename a key in the metadata.

    :type msg: dict
    :param msg: The message to convert
    :type field: basestring
    :param field: The key whose key we'll change.
    :type new_key: basestring
    :param new_key: The key we'll change to
    """
    if msg.get('data', {}).get(field):
        msg['data'][new_field] = msg['data'][field]
        del msg['data'][field]


def _make_common_args(msg):
    """ prepare common data from msg into kwargs for Event. """
    common_args = {}
    for k in ('subject', 'objects', 'context', ):
        if msg.get(k):
            common_args[k] = msg[k]
    try:
        schedule = (msg.get('data') or {}).get('schedule')
    except AttributeError:
        pass
    else:
        if schedule:
            common_args['scheduled'] = schedule
    return common_args


@EventFilter.register('account_password', 'set')
def account_password(msg, **kwargs):
    """Issue a password message."""
    common = _make_common_args(msg)
    return event.Event(event.PASSWORD,
                       attributes=['password'],
                       **common)


@EventFilter.register('account', 'create')
def account_create(msg, **kwargs):
    """account create (by write_db)
    attributes other than _auth_info, _acc_affect_auth_types, password
    """
    common = _make_common_args(msg)
    return event.Event(event.CREATE,
                       attributes=['npType', 'expireDate', 'createDate'],
                       **common)


@EventFilter.register('account', 'delete')
def account_delete(msg, **kwargs):
    common = _make_common_args(msg)
    return event.Event(event.DELETE,
                       **common)


@EventFilter.register('account', 'modify')
def account_mod(msg, **kwargs):
    """account mod (by write_db)
    attributes that have been changed
    """
    common = _make_common_args(msg)
    return event.Event(event.MODIFY,
                       attributes=['npType', 'expireDate', 'createDate'],
                       **common)


@EventFilter.register('spread', 'add')
def spread_add(msg, **kwargs):
    common = _make_common_args(msg)
    return event.Event(event.ADD,
                       **common)


@EventFilter.register('spread', 'delete')
def spread_del(msg, **kwargs):
    common = _make_common_args(msg)
    return event.Event(event.REMOVE,
                       **common)


def _ou(msg, db):
    ou = msg['data'].get('ou_id')
    if ou:
        o = Factory.get("OU")(db)
        o.find(ou)
        msg['data']['ou'] = six.text_type(o)


@EventFilter.register('account_type')
def account_type(msg, **kwargs):
    common = _make_common_args(msg)
    return event.Event(event.MODIFY,
                       attributes=['accountType'],  # TODO: better name?
                       **common)


@EventFilter.register('homedir')
def homedir(msg, **kwargs):
    common = _make_common_args(msg)
    return event.Event(event.MODIFY,
                       attributes=['home'],
                       **common)


# suppress entity, the usually follow something else
@EventFilter.register('entity')
def entity(*args, **kwargs):
    return None


# change entity_name to identifier, as this is easier understood
# (not conflicting with other names)
# TODO: map to account, group, etc?
@EventFilter.register('entity_name')
def entity_name(msg, **kwargs):
    subject_type = getattr(msg.get('subject'), 'entity_type', None)
    attr = {
        'account': ['identifier', ],
        'group': ['identifier', ],
        'person': ['title', ],
    }.get(subject_type)

    if attr:
        common = _make_common_args(msg)
        return event.Event(event.MODIFY,
                           attributes=attr,
                           **common)


@EventFilter.register('entity_cinfo')
def entity_cinfo(msg, db=None, **kwargs):
    """Convert address type and source constants."""
    c = Factory.get('Constants')(db)
    x = c.ContactInfo(msg['data']['type'])
    attr = {
        c.contact_phone: 'phone',
        c.contact_phone_private: 'privatePhone',
        c.contact_fax: 'fax',
        c.contact_email: 'externalEmail',
        c.contact_url: 'homePage',
        c.contact_mobile_phone: 'cellPhone',
        c.contact_private_mobile: 'cellPhone',
        c.contact_private_mobile_visible: 'cellPhone'
    }.get(x) or six.text_type(x).capitalize()

    common = _make_common_args(msg)

    return event.Event(event.MODIFY,
                       attributes=[attr],
                       **common)


@EventFilter.register('entity_addr')
def entity_addr(msg, **kwargs):
    if not msg['subject']:
        # No subject: noop
        return
    common = _make_common_args(msg)
    return event.Event(event.MODIFY,
                       attributes=['address'],
                       **common)


@EventFilter.register('entity_note')
def entity_note(*args, **kwargs):
    # TODO: Should we get the actual note, and send it?
    return None


@EventFilter.register('entity_external_id')
def entity_external_id(msg, db=None, **kwargs):
    if not msg['subject']:
        # No subject: noop
        return
    c = Factory.get('Constants')(db)
    x = c.EntityExternalId(msg['data']['id_type'])
    attr = {
        # c.externalid_groupsid: 'sid',
        # c.externalid_accountsid: 'sid',
        c.externalid_fodselsnr: 'nationalIdNumber',
        c.externalid_pass_number: 'passNumber',
        c.externalid_studentnr: 'studentNumber',
        c.externalid_fs_lopenr: 'fsPersonSerialNumber',
        c.externalid_sap_ansattnr: 'employeeNumber',
        c.externalid_sap_ou: 'sapOu',
        c.externalid_uname: 'externalUsername',
    }.get(x) or six.text_type(x).capitalize()

    common = _make_common_args(msg)

    return event.Event(event.MODIFY,
                       attributes=[attr],
                       **common)


@EventFilter.register('consent')
def entity_consent(msg, **kwargs):
    common = _make_common_args(msg)
    return event.Event(event.MODIFY,
                       attributes=['consent'],
                       **common)


_PERSON_ATTRIBUTES = [
    'exportID',
    'birthDate',
    'gender',
    'description',
    'deseasedDate',
]


@EventFilter.register('person', 'create')
def person_create(msg, **kwargs):
    common = _make_common_args(msg)
    return event.Event(event.CREATE,
                       attributes=_PERSON_ATTRIBUTES,
                       **common)


@EventFilter.register('person', 'join')
def person_join(msg, db=None, **kwargs):
    args = {
        'subject': get_entity_ref(db, msg['data']['new']),
        'objects': [get_entity_ref(db, msg['data']['old'])]
    }
    return event.Event(event.JOIN,
                       attributes=['id'],
                       **args)


@EventFilter.register('person', 'modify')
def person_modify(msg, **kwargs):
    common = _make_common_args(msg)
    return event.Event(event.MODIFY,
                       attributes=_PERSON_ATTRIBUTES,
                       **common)


@EventFilter.register('person_name')
def person_name_ops(msg, db=None, **kwargs):
    co = Factory.get('Constants')(db)
    if msg['data']['src'] == co.system_cached:
        common = _make_common_args(msg)
        return event.Event(event.MODIFY,
                           attributes=['name'],
                           **common)
    return None


@EventFilter.register('person_aff')
def person_affiliation_ops(msg, **kwargs):
    common = _make_common_args(msg)
    return event.Event(event.MODIFY,
                       attributes=['affiliation'],
                       **common)


@EventFilter.register('person_aff_src')
def person_affiliation_source_ops(msg, **kwargs):
    common = _make_common_args(msg)
    return event.Event(event.MODIFY,
                       attributes=['affiliation'],
                       **common)


@EventFilter.register('person')
def person(*args, **kwargs):
    return None


def _parse_quarantine_add_start(rawstr):
    # TODO: Fix - *quarantine_add* should log_change with consistent change
    #       params - which should *either* be a date, datetime, or a string
    #       with a consistent format!
    try:
        return parse_datetime(rawstr)
    except ValueError:
        return datetime.datetime.strptime(rawstr, '%Y-%m-%d')


@EventFilter.register('quarantine', 'add')
def quarantine_add(msg, **kwargs):
    common = _make_common_args(msg)
    start = msg['data'].get('start')
    if isinstance(start, six.string_types):
        try:
            start = _parse_quarantine_add_start(start)
        except ValueError:
            raise TypeError('Invalid date/datetime {0} ({1})'.format(
                type(start), repr(start)
            ))
    elif isinstance(start, datetime.date):
        start = get_datetime_tz(start)
    # co = Factory.get('Constants')(args[-1])
    # tp = msg['data']['q_type']
    # TODO: Quarantine handler
    return event.Event(event.DEACTIVATE,
                       scheduled=start,
                       **common)


@EventFilter.register('quarantine', 'remove')
def quarantine_del(msg, **kwargs):
    common = _make_common_args(msg)
    return event.Event(event.ACTIVATE,
                       **common)


@EventFilter.register('quarantine', 'modify')
def quarantine_mod(msg, **kwargs):
    # TODO: This should be re-worked.  Depending on the previous value and the
    # current disable date, this could be any combination of:
    #
    # - no event:  E.g. the user was deactivated, still is deactivated
    # - one event:  E.g. deactivate because we remove a disable-until date
    # - two events:  E.g. activate because we set disable-until, and schedule
    #                a deactivate because of the future disable-until date
    common = _make_common_args(msg)
    return event.Event(event.ACTIVATE,
                       **common)


@EventFilter.register('group', 'create')
def group_create(msg, **kwargs):
    common = _make_common_args(msg)
    return event.Event(event.CREATE,
                       attributes=['description'],
                       **common)


@EventFilter.register('group_member', 'add')
def group_add(msg, **kwargs):
    common = _make_common_args(msg)
    return event.Event(event.ADD,
                       attributes=['member'],
                       **common)


@EventFilter.register('group_member', 'remove')
def group_rem(msg, **kwargs):
    common = _make_common_args(msg)
    return event.Event(event.REMOVE,
                       attributes=['member'],
                       **common)


@EventFilter.register('group', 'modify')
def group_mod(msg, **kwargs):
    common = _make_common_args(msg)

    attrs = set()
    for key in (msg.get('data') or {}):
        # TODO: Because of how the `Group.write_db()` calls `log_change`, the
        # attributes are named `old_*`, where `*` is the actual attribute.  We
        # should probably fix this, but we don't know if any consumer is built
        # to look at these incorrectly named attributes:
        #
        # if key != "old_" and key.startswith("old_"):
        #     attrs.add(key[4:])
        # else:
        #     attrs.add(key)
        #
        attrs.add(key)

    return event.Event(event.MODIFY,
                       attributes=attrs,
                       **common)


@EventFilter.register('group', 'delete')
def group_destroy(msg, db=None, **kwargs):
    co = Factory.get('Constants')(db)
    common = _make_common_args(msg)

    # We may be missing some data here, as we build the subject part from
    # potentially deleted data.  However, we know the entity type, and the
    # `log_change` call usually includes the actual group name:
    #
    group_name = msg.get('data', {}).get('name', None)
    common['subject'] = event.EntityRef(
        common['subject'].entity_id,
        six.text_type(co.entity_group),
        group_name or common['subject'].ident,
    )

    return event.Event(event.DELETE,
                       **common)


#
# Cerebrum.modules.Email
#
# We may want to move email stuff into its own module, as they will have their
# own implementation pattern (e.g. map subject from email target to
# entity_target_type, entity_target_id)
#
def _fix_email_target_subject(db, common_args):
    """ set subject to *email_target_entity_id* for email target events.

    We generally want events on email targets to apply to their target id, so
    that e.g. an email address change for an account results in an email modify
    event on the account object.
    """
    new_args = dict(common_args)
    target_ref = new_args.pop('subject')

    # TODO: or empty out objects? error if objects are present?
    new_args['objects'] = list(common_args.get('objects') or ())

    new_args['objects'].append(target_ref)

    from Cerebrum.modules.Email import EmailTarget
    et = EmailTarget(db)
    try:
        et.find(target_ref.entity_id)
    except Exception:
        logger.debug('event email-target: unable to find target %s',
                     repr(target_ref))
    entity_id = getattr(et, 'email_target_entity_id', None)

    if entity_id:
        new_args['subject'] = get_entity_ref(db, et.email_target_entity_id)
    else:
        logger.debug('event email-target: no target entity for %s (entity=%s)',
                     repr(target_ref), repr(entity_id))
    return new_args


@EventFilter.register('email_primary_address')
def user_primary_addr_mod(msg, db=None, **kwargs):
    common = _fix_email_target_subject(db, _make_common_args(msg))
    if not common.get('subject'):
        # ignore - no subject to bind this event to
        return None

    return event.Event(event.MODIFY,
                       attributes=['email'],
                       **common)


# python -m Cerebrum.modules.event_publisher.converters

def main():
    """ Print the registered handler regexes. """
    for key in EventFilter.callbacks:
        print(key.pattern)


if __name__ == '__main__':
    raise SystemExit(main())
