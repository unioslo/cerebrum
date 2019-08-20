#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2015-2017 University of Oslo, Norway
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
""" Module used by publisher to convert 'raw' events into exportable messages.

General idea: The eventlog module creates a dict containing the message data.
Then the EventFilter is called with the data, and generates Event objects that
can be formatted and published.

"""
from __future__ import absolute_import, print_function

import re
import six
from collections import OrderedDict

from Cerebrum.Utils import Factory
from . import event


"""
General fixes:
categories:
    ac_type -> ?
    ad_attr -> ad_attribute
    disk -> ?
    disk_quota -> ?
    dlgroup -> distribution_group
    e_account -> account
    e_group -> group
    email_address -> email
    email_forward -> email
    email_primary_address -> email
    email_quota -> email
    email_scan -> email
    email_sfilter -> email
    email_tfilter -> email
    email_vacation -> email
    entity_addr -> address
    entity_cinfo -> contact_info
    entity_name -> ident?
    entity_note -> note
    guest -> wlan_account
    homedir -> ?
    ou -> orgunit
    posix -> account, group
    quarantine -> ?
    spread -> ?
    trait -> ?

    tidy change types:
        use verbs
        * add
        * remove
        * set
        * unset
        * update

"""


class EventFilter(object):
    """ Filter with database. """

    callbacks = OrderedDict()

    def __init__(self, db):
        self.db = db

    def __call__(self, message, change_type, **kwargs):
        """ Generate an event.

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

        >>> @EventFilter.register('person', 'aff_mod')
        ... def person_aff(msg, **kwargs):
        ...     return event.Event(event.MODIFY)

        >>> @EventFilter.register('person', 'aff_(add|del)')
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
    common_args = dict()
    for k in ('subject', 'objects', 'context', ):
        if msg.get(k):
            common_args[k] = msg[k]
    schedule = msg.get('data', dict()).get('schedule')
    if schedule:
        common_args['scheduled'] = schedule
    return common_args


"""

    # Account changes

    account_create = _ChangeTypeCode(
        'e_account', 'create', 'created %(subject)s')
    account_delete = _ChangeTypeCode(
        'e_account', 'delete', 'deleted %(subject)s')
    account_mod = _ChangeTypeCode(
        'e_account', 'mod', 'modified %(subject)s',
        ("new owner=%(entity:owner_id)s",
         "new expire_date=%(date:expire_date)s"))
    account_password = _ChangeTypeCode(
        'e_account', 'password', 'new password for %(subject)s')
    account_password_token = _ChangeTypeCode(
        'e_account', 'passwordtoken', 'password token sent for %(subject)s',
        ('phone_to=%(string:phone_to)s',))
    account_destroy = _ChangeTypeCode(
        'e_account', 'destroy', 'destroyed %(subject)s')
    # TODO: account_move is obsolete, remove it
    account_move = _ChangeTypeCode(
        'e_account', 'move', '%(subject)s moved',
        ('from=%(string:old_host)s:%(string:old_disk)s,'
            + 'to=%(string:new_host)s:%(string:new_disk)s,',))



    account_home_updated = _ChangeTypeCode(
        'e_account', 'home_update', 'home updated for %(subject)s',
        ('old=%(homedir:old_homedir_id)s',
         'old_home=%(string:old_home)s',
         'old_disk_id=%(disk:old_disk_id)s',
         'spread=%(spread_code:spread)s'))
    account_home_added = _ChangeTypeCode(
        'e_account', 'home_added', 'home added for %(subject)s',
        ('spread=%(spread_code:spread)s', 'home=%(string:home)s'))
    account_home_removed = _ChangeTypeCode(
        'e_account', 'home_removed', 'home removed for %(subject)s',
        ('spread=%(spread_code:spread)s', 'home=%(string:home)s'))
"""


@EventFilter.register('e_account', 'password')
def account_password(msg, **kwargs):
    """Issue a password message."""
    common = _make_common_args(msg)
    return event.Event(event.PASSWORD,
                       attributes=['password'],
                       **common)


# @EventFilter.register('e_account', 'password_token')
# def password_token(*args, **kwargs):
#    return None


@EventFilter.register('e_account', 'create')
def account_create(msg, **kwargs):
    """account create (by write_db)
    attributes other than _auth_info, _acc_affect_auth_types, password
    """
    common = _make_common_args(msg)
    return event.Event(event.CREATE,
                       attributes=['npType', 'expireDate', 'createDate'],
                       **common)


@EventFilter.register('e_account', 'destroy')
def account_delete(msg, **kwargs):
    common = _make_common_args(msg)
    return event.Event(event.DELETE,
                       **common)


@EventFilter.register('e_account', 'mod')
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


@EventFilter.register('ac_type')
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

"""
    # Disk changes

    disk_add = _ChangeTypeCode('disk', 'add', 'new disk %(subject)s')
    disk_mod = _ChangeTypeCode('disk', 'mod', 'update disk %(subject)s')
    disk_del = _ChangeTypeCode('disk', 'del', "delete disk %(subject)s")

    # Host changes

    host_add = _ChangeTypeCode('host', 'add', 'new host %(subject)s')
    host_mod = _ChangeTypeCode('host', 'mod', 'update host %(subject)s')
    host_del = _ChangeTypeCode('host', 'del', 'del host %(subject)s')

    # OU changes

    ou_create = _ChangeTypeCode(
        'ou', 'create', 'created OU %(subject)s')
    ou_mod = _ChangeTypeCode(
        'ou', 'mod', 'modified OU %(subject)s')
    ou_unset_parent = _ChangeTypeCode(
        'ou', 'unset_parent', 'parent for %(subject)s unset',
        ('perspective=%(int:perspective)s',))
    ou_set_parent = _ChangeTypeCode(
        'ou', 'set_parent', 'parent for %(subject)s set to %(dest)s',
        ('perspective=%(int:perspective)s',))
    ou_del = _ChangeTypeCode(
        'ou', 'del', 'deleted OU %(subject)s')

"""


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


@EventFilter.register('entity', 'ext_id.*')
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


@EventFilter.register('person', 'update')
def person_update(msg, **kwargs):
    common = _make_common_args(msg)
    return event.Event(event.MODIFY,
                       attributes=_PERSON_ATTRIBUTES,
                       **common)


@EventFilter.register('person', 'name_.*')
def person_name_ops(msg, db=None, **kwargs):
    co = Factory.get('Constants')(db)
    if msg['data']['src'] == co.system_cached:
        common = _make_common_args(msg)
        return event.Event(event.MODIFY,
                           attributes=['name'],
                           **common)
    return None


@EventFilter.register('person', 'aff_(add|mod|del)')
def person_affiliation_ops(msg, **kwargs):
    common = _make_common_args(msg)
    return event.Event(event.MODIFY,
                       attributes=['affiliation'],
                       **common)


@EventFilter.register('person', 'aff_src.*')
def person_affiliation_source_ops(msg, **kwargs):
    common = _make_common_args(msg)
    return event.Event(event.MODIFY,
                       attributes=['affiliation'],
                       **common)


@EventFilter.register('person')
def person(*args, **kwargs):
    return None


@EventFilter.register('quarantine', 'add')
def quarantine_add(msg, **kwargs):
    common = _make_common_args(msg)
    start = msg['data'].get('start')
    # co = Factory.get('Constants')(args[-1])
    # tp = msg['data']['q_type']
    # TODO: Quarantine handler
    return event.Event(event.DEACTIVATE,
                       scheduled=start,
                       **common)


@EventFilter.register('quarantine', 'del')
def quarantine_del(msg, **kwargs):
    common = _make_common_args(msg)
    return event.Event(event.ACTIVATE,
                       **common)


@EventFilter.register('quarantine', 'mod')
def quarantine_mod(msg, **kwargs):
    # TBD: Is this really ACTIVATE? Or is it DEACTIVATE? Is this relative to
    # the point in time the quarantine should be enforced?
    common = _make_common_args(msg)
    return event.Event(event.ACTIVATE,
                       **common)

# TODO: What to translate to?

"""
    # TBD: Is it correct to have posix_demote in this module?

    posix_demote = _ChangeTypeCode(
        'posix', 'demote', 'demote posix %(subject)s',
        ('uid=%(int:uid)s, gid=%(int:gid)s',))
    posix_group_demote = _ChangeTypeCode(
        'posix', 'group-demote', 'group demote posix %(subject)s',
        ('gid=%(int:gid)s',))
    posix_promote = _ChangeTypeCode(
        'posix', 'promote', 'promote posix %(subject)s',
        ('uid=%(int:uid)s, gid=%(int:gid)s',))
    posix_group_promote = _ChangeTypeCode(
        'posix', 'group-promote', 'group promote posix %(subject)s',
        ('gid=%(int:gid)s',))

    # Guest functionality

    guest_create = _ChangeTypeCode(
        'guest', 'create', 'created guest %(dest)s',
        ('mobile=%(string:mobile)s, name=%(string:name)s,
        owner_id=%(string:owner)s',))


    # AD functionality
    ad_attr_add = CLConstants._ChangeTypeCode(
        'ad_attr', 'add', 'added AD-attribute for %(subject)s',
        ('spread=%(string:spread)s, attr=%(string:attr)s,
        value=%(string:value)s',))

    ad_attr_del = CLConstants._ChangeTypeCode(
        'ad_attr', 'del', 'removed AD-attribute for %(subject)s',
        ('spread=%(string:spread)s, attr=%(string:attr)s',))


"""


"""
   # Group changes

    group_add = _ChangeTypeCode(
        'e_group', 'add', 'added %(subject)s to %(dest)s')
    group_rem = _ChangeTypeCode(
        'e_group', 'rem', 'removed %(subject)s from %(dest)s')
    group_create = _ChangeTypeCode(
        'e_group', 'create', 'created %(subject)s')
    group_mod = _ChangeTypeCode(
        'e_group', 'mod', 'modified %(subject)s')
    group_destroy = _ChangeTypeCode(
        'e_group', 'destroy', 'destroyed %(subject)s')
"""


@EventFilter.register('e_group')
def group(*args, **kwargs):
    return None


@EventFilter.register('e_group', 'create')
def group_create(msg, **kwargs):
    common = _make_common_args(msg)
    return event.Event(event.CREATE,
                       attributes=['description'],
                       **common)


@EventFilter.register('e_group', 'add')
def group_add(msg, **kwargs):
    common = _make_common_args(msg)
    return event.Event(event.MODIFY,
                       attributes=['member'],
                       **common)


@EventFilter.register('e_group', 'rem')
def group_rem(msg, **kwargs):
    common = _make_common_args(msg)
    return event.Event(event.MODIFY,
                       attributes=['member'],
                       **common)


@EventFilter.register('e_group', 'mod')
def group_mod(msg, **kwargs):
    common = _make_common_args(msg)
    return event.Event(event.MODIFY,
                       attributes=msg.get('data', []),
                       **common)


@EventFilter.register('e_group', 'destroy')
def group_destroy(msg, *kwargs):
    common = _make_common_args(msg)
    # We may be missing some data here, as it has been deleted, so let's
    # manipulate the 'subject' part of our message.
    common['subject'].ident = msg.get('data', {}).get('name', None)
    common['subject'].entity_type = 'group'
    return event.Event(event.DELETE,
                       **common)


#   @EventFilter.register('ad_attr')
#   def ad_attr(*args, **kwags):
#       return None


#   @EventFilter.register('dlgroup')
#   def dlgroup(msg, *rest):
#       """distribution group roomlist"""
#       return None


# python -m Cerebrum.modules.event_publisher.converters

def main():
    """ Print the registered handler regexes. """
    for key in EventFilter.callbacks:
        print(key.pattern)


if __name__ == '__main__':
    raise SystemExit(main())
