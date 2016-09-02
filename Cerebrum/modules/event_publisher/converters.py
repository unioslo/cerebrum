#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2015 University of Oslo, Norway
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

General idea: The event publisher creates a dict containing the message.
Then the filter_message is called with the required arguments.

If filter_message returns some value that is boolean true, it is used as the
message, otherwise it is discarded.
"""

import re
from collections import OrderedDict
from Cerebrum.Utils import Factory

from . import scim

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


def filter_message(msg, subject, dest, change_type, db):
    """Filter a message, converting the data on the way.

    :param msg: Message object
    :type msg: dict

    :param subject: Subject
    :type subject: Entity

    :param dest: Object/destination
    :type dest: Entity or None

    :param db: Database
    :type db: Database

    :param change_type: ChangeType
    :type change_type: Code ChangeType
    """
    category, change = msg['category'], msg['change']
    payload = None
    for key in _dispatch.keys():
        if re.match('^%s$' % key,
                    '%s:%s' % (category, change) if change else category):
            payload = _dispatch.get(key)(
                msg, subject, dest, change_type, db)
            msg['payload'] = payload
    return payload


# Holds the mapping of names, as registred by dispatch().
def _identity(msg, *args):
    return msg
_dispatch = OrderedDict()


def dispatch(cat, change=None):
    """Wrapper registers transform-functions to change-types."""
    def _fix(fn):
        _dispatch['%s:%s' % (cat, change) if change else '%s:.*' % cat] = fn
        return fn
    return _fix


def _stringify_code(msg, field, code_converter):
    """Convert a code to a string.

    :type msg: dict
    :param msg: The message to convert
    :type field: basestring
    :param field: The key whose value we'll convert.
    :type code_converter: _CerebrumCode
    :param code_converter: The converter to use for the code.
    """
    if msg.get('data', {}).get(field):
        msg['data'][field] = str(code_converter(msg['data'][field]))


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


@dispatch('e_account', 'password')
def account_password(msg, subject, *args):
    """Issue a password message."""
    return scim.Event(scim.PASSWORD,
                      subject=subject,
                      attributes=['password'])


# @dispatch('e_account', 'password_token')
# def password_token(*args):
#    return None


@dispatch('e_account', 'create')
def account_create(msg, subject, *args):
    """account create (by write_db)
    attributes other than _auth_info, _acc_affect_auth_types, password
    """
    return scim.Event(scim.CREATE,
                      subject=subject,
                      attributes=['npType', 'expireDate', 'createDate'])


@dispatch('e_account', 'destroy')
def account_delete(msg, subject, *args):
    return scim.Event(scim.DELETE,
                      subject=subject)


@dispatch('e_account', 'mod')
def account_mod(msg, subject, *kws):
    """account mod (by write_db)
    attributes that have been changed
    """
    return scim.Event(scim.MODIFY,
                      subject=subject,
                      attributes=['npType', 'expireDate', 'createDate'])


@dispatch('spread', 'add')
def spread_add(msg, subject, *args):
    return scim.Event(scim.ADD,
                      subject=subject,
                      spreads=[msg['context']])


@dispatch('spread', 'del')
def spread_del(msg, subject, *args):
    return scim.Event(scim.REMOVE,
                      subject=subject,
                      spreads=[msg['context']])


def _ou(msg, db):
    ou = msg['data'].get('ou_id')
    if ou:
        o = Factory.get("OU")(db)
        o.find(ou)
        msg['data']['ou'] = str(o)


@dispatch('ac_type')
def account_type(msg, subject, *args):
    return scim.Event(scim.MODIFY,
                      subject=subject,
                      attributes=['accountType'])  # TODO: better name?


@dispatch('homedir')
def homedir(msg, subj, *args):
    return scim.Event(scim.MODIFY,
                      subject=subj,
                      attributes=['home'])

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
@dispatch('entity')
def entity(*args):
    return None


# change entity_name to identifier, as this is easier understood
# (not conflicting with other names)
# TODO: map to account, group, etc?
@dispatch('entity_name')
def entity_name(msg, subject, *args):
    attr = None
    if msg['subjecttype'] in ('account', 'group'):
        attr = ['identifier']
    elif msg['subjecttype'] == 'person':
        attr = ['title']
    if attr:
        return scim.Event(scim.MODIFY,
                          subject=subject,
                          attributes=attr)


@dispatch('entity_cinfo')
def entity_cinfo(msg, subject, *args):
    """Convert address type and source constants."""
    c = Factory.get('Constants')(args[-1])

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
    }.get(x) or str(x.capitalize())

    return scim.Event(scim.MODIFY,
                      subject=subject,
                      attributes=[attr])


@dispatch('entity_addr')
def entity_addr(msg, subj, *args):
    if subj:
        return scim.Event(scim.MODIFY,
                          subject=subj,
                          attributes=['address'])


@dispatch('entity_note')
def entity_note(msg, *args):
    # TODO: Should we get the actual note, and send it?
    return None


@dispatch('entity', 'ext_id.*')
def entity_external_id(msg, subj, *args):
    if not subj:
        return None
    c = Factory.get('Constants')(args[-1])
    x = c.EntityExternalId(msg['data']['id_type'])
    attr = {
        # c.externalid_groupsid: 'sid',
        # c.externalid_accountsid: 'sid',
        c.externalid_fodselsnr: 'nationalIdNumber',
        c.externalid_pass_number: 'passNumber',
        c.externalid_social_security_number: 'socialSecurityNumber',
        c.externalid_tax_identification_number: 'taxIdNumber',
        c.externalid_value_added_tax_number: 'vatNumber',
        c.externalid_studentnr: 'studentNumber',
        c.externalid_sap_ansattnr: 'employeeNumber',
        c.externalid_sap_ou: 'sapOu',
        c.externalid_uname: 'externalUsername',
        c.externalid_stedkode: 'OuCode',
    }.get(x) or str(x.capitalize())

    return scim.Event(scim.MODIFY,
                      subject=subj,
                      attributes=[attr])


@dispatch('person')
def person(msg, subject, dest, change_type, db):
    return None


@dispatch('person', 'create')
def person_create(msg, subj, *rest):
    return scim.Event(scim.CREATE,
                      subject=subj,
                      attributes='exportID birthDate gender '
                      'description deseasedDate'.split())


@dispatch('person', 'update')
def person_update(msg, subj, *rest):
    return scim.Event(scim.MODIFY,
                      subject=subj,
                      attributes='exportID birthDate gender '
                      'description deseasedDate'.split())


@dispatch('person', 'name_.*')
def person_name_ops(msg, *args):
    co = Factory.get('Constants')(args[-1])
    if msg['data']['src'] == co.system_cached:
        return scim.Event(scim.MODIFY,
                          subject=args[0],
                          attributes=['name'])
    return None


@dispatch('person', 'aff_(add|mod|del)')
def person_affiliation_ops(msg, subj, *args):
    return scim.Event(scim.MODIFY,
                      subject=subj,
                      attributes=['affiliation'])


@dispatch('person', 'aff_src.*')
def person_affiliation_source_ops(msg, *args):
    # TODO: Calculate changes
    return None


@dispatch('quarantine', 'add')
def quarantine_add(msg, subj, *args):
    # co = Factory.get('Constants')(args[-1])
    # tp = msg['data']['q_type']
    # TODO: Quarantine handler
    return scim.Event(scim.ACTIVATE,
                      subject=subj)


@dispatch('quarantine', 'del')
def quarantine_del(msg, subj, *args):
    return scim.Event(scim.DEACTIVATE,
                      subject=subj)


@dispatch('quarantine', 'mod')
def quarantine_mod(msg, subj, *args):
    return scim.Event(scim.DEACTIVATE,
                      subject=subj)

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


@dispatch('e_group')
def group(msg, *rest):
    return None


@dispatch('e_group', 'create')
def group_create(msg, subj, *rest):
    return scim.Event(scim.CREATE,
                      subject=subj,
                      attributes=['description'])


@dispatch('e_group', 'add')
def group_add(msg, subj, dest, *rest):
    return scim.Event(scim.MODIFY,
                      subject=subj,
                      obj=dest,
                      attributes=['member'])


@dispatch('e_group', 'rem')
def group_rem(msg, subj, dest, *rest):
    return scim.Event(scim.MODIFY,
                      subject=subj,
                      obj=dest,
                      attributes=['member'])


@dispatch('ad_attr')
def ad_attr(msg, *rest):
    return None


@dispatch('dlgroup')
def dlgroup(msg, *rest):
    """distribution group roomlist"""
    return None
