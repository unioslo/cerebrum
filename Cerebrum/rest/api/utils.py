#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2016-2018 University of Oslo, Norway
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

from __future__ import unicode_literals

from six import text_type

from Cerebrum.rest.api import db

from Cerebrum import Errors
from Cerebrum.Utils import Factory
import Cerebrum.modules.bofhd.auth as bofhd_auth


class EntityLookupError(Exception):
    """Raised when an entity lookup failed for whatever reason.

    This message is passed on to the user when abort()ing.
    """
    pass


def get_account(identifier, idtype=None, actype='Account'):
    """Fetch an account by name, ID or POSIX UID.

    :param text/int identifier:
        The identifier for the account to be retrived
    :param text idtype:
        The identifier type. Can be 'name', 'entity_id' or 'posix_uid'
    :param text actype:
        The wanted account subclass

    :rtype:
        Account or PosixUser
    :return:
        The account object associated with the specified identifier, or an
        exception.
    """
    if actype == 'Account':
        account = Factory.get('Account')(db.connection)
    elif actype == 'PosixUser':
        account = Factory.get('PosixUser')(db.connection)

    try:
        if idtype == 'name':
            account.find_by_name(identifier, db.const.account_namespace)
        elif idtype == 'entity_id':
            if isinstance(identifier, text_type) and not identifier.isdigit():
                raise EntityLookupError("entity_id must be a number")
            account.find(identifier)
        elif idtype == 'posix_uid':
            if isinstance(identifier, text_type) and not identifier.isdigit():
                raise EntityLookupError("posix_uid must be a number")
            if actype != 'PosixUser':
                account = Factory.get('PosixUser')(db.connection)
                account.clear()
            account.find_by_uid(identifier)
        else:
            raise EntityLookupError(
                "Invalid identifier type {}".format(idtype))
    except Errors.NotFoundError:
        raise EntityLookupError(
            "No such {} with {}={}".format(actype, idtype, identifier))

    return account


def get_group(identifier, idtype=None, grtype='Group'):
    """Fetch a group by name, ID or POSIX GID.

    :param text/int identifier:
        The identifier for the group to be retrived
    :param text idtype:
        The identifier type. Can be 'name', 'entity_id' or 'posix_gid'
    :param text actype:
        The wanted group subclass

    :rtype:
        Group or PosixGroup
    :return:
        The group object associated with the specified identifier, or an
        exception.
    """
    group = None
    if grtype == 'Group':
        group = Factory.get('Group')(db.connection)
    elif grtype == 'PosixGroup':
        group = Factory.get('PosixGroup')(db.connection)
    elif grtype == 'DistributionGroup':
        group = Factory.get('DistributionGroup')(db.connection)
    else:
        raise EntityLookupError("Invalid group type {}".format(grtype))

    try:
        if idtype == "name":
            group.find_by_name(identifier)
        elif idtype == "entity_id":
            group.find(identifier)
        elif idtype == "posix_gid" and grtype == 'PosixGroup':
            group.find_by_gid(identifier)
        else:
            raise EntityLookupError(
                "Invalid identifier type '{}'".format(idtype))
    except Errors.NotFoundError:
        raise EntityLookupError("Could not find a {} with {}={}".format(
            grtype, idtype, repr(identifier)))

    return group


def get_entity(identifier=None, entype=None, idtype=None):
    """Fetches an entity.

    :param text/int identifier:
        The identifier for the entity to be retrived
    :param text/None entype:
        The entity type. If None, 'identifier' is assumed to be numeric, and
        the subclassed object is returned.
    :param text idtype:
        The identifier type

    :rtype:
        Entity or one of its subclasses
    :return:
        The entity object
    """
    if identifier is None:
        raise EntityLookupError("Missing identifier")
    if entype == 'account':
        return get_account(idtype=idtype, identifier=identifier)
    # if entype == 'person':
    #     return self._get_person(*self._map_person_id(identifier))
    # if entype == 'group':
    #     return self._get_group(identifier)
    # if entype == 'stedkode':
    #     return self._get_ou(stedkode=identifier)
    # if entype == 'host':
    #     return self._get_host(identifier)
    if entype is None:
        try:
            int(identifier)
        except ValueError:
            raise EntityLookupError("Expected numeric identifier")
        en = Factory.get(b'Entity')(db.connection)
        try:
            return en.get_subclassed_object(identifier)
        except Errors.NotFoundError:
            raise EntityLookupError(
                "Could not find an Entity with {}={}".format(idtype,
                                                             identifier))
    raise EntityLookupError("Invalid entity type {}".format(entype))


def get_entity_name(entity):
    """Looks up the name of an entity object.

    If 'entity' is numeric, the object is retrived from the database.

    :param Entity/int/long entity:
        The entity object or its ID

    :return text:
        The name of the entity
    """
    if isinstance(entity, (int, long)):
        entity_obj = Factory.get('Entity')(db.connection)
        try:
            entity_obj.find(entity)
            entity = entity_obj.get_subclassed_object()
        except Errors.NotFoundError:
            return None
    name = None
    if entity.entity_type == db.const.entity_account:
        name = entity.account_name
    elif entity.entity_type == db.const.entity_group:
        name = entity.group_name
    return name


# Used to find auth role owners. Should probably be moved somewhere else.
# For example (entity_id=group_id, target_type='group') will find group
# moderators.
def get_auth_roles(entity, target_type, role_map=None):
    aot = bofhd_auth.BofhdAuthOpTarget(db.connection)
    ar = bofhd_auth.BofhdAuthRole(db.connection)
    aos = bofhd_auth.BofhdAuthOpSet(db.connection)
    targets = []
    for row in aot.list(target_type=target_type, entity_id=entity.entity_id):
        targets.append(int(row['op_target_id']))
    roles = dict()
    names = dict()
    for row in ar.list_owners(targets):
        aos.clear()
        aos.find(row['op_set_id'])
        if role_map and aos.name not in role_map:
            continue
        entity_id = int(row['entity_id'])
        en = Factory.get('Entity')(db.connection).get_subclassed_object(
            entity_id)
        names[en.entity_id] = get_entity_name(en)
        roles.setdefault((en.entity_id, en.entity_type), []).append(aos.name)

    data = []
    for (entity_id, entity_type), r in roles.iteritems():
        data.append({
            'id': entity_id,
            'type': entity_type,
            'name': names[entity_id],
            'roles': [role_map[r_] for r_ in r] if role_map else r,
        })
    return data


def get_opset(opset_name):
    aos = bofhd_auth.BofhdAuthOpSet(db.connection)
    aos.find_by_name(opset_name)
    return aos


def get_op_target(entity, create=True):
    tt_lut = {
        # TODO: More
        # FIXME: Make sure constants exist
        db.const.entity_group: db.const.auth_target_type_group,
        db.const.entity_account: db.const.auth_target_type_group,
        db.const.entity_person: db.const.auth_target_type_person,
    }
    entity_id = entity.entity_id
    target_type = tt_lut[entity.entity_type]
    aot = bofhd_auth.BofhdAuthOpTarget(db.connection)

    op_targets = [t for t in aot.list(entity_id=entity_id,
                                      target_type=target_type)]

    # No target exists, create one
    if not op_targets and create:
        aot.populate(entity_id, target_type)
        aot.write_db()
        return aot

    assert len(op_targets) == 1  # This method will never create more than one
    assert op_targets[0]['attr'] is None  # ... and never populates attr

    # Target exists, return it
    aot.find(op_targets[0]['op_target_id'])
    return aot


def grant_auth(sub, opset, obj):
    """
    :param Entity sub:
        Subject granted auth.
    :param BofhdAuthOpSet opset:
        The opset (role) that is granted.
    :param Entity obj:
        The object that is being controlled.
    """
    ar = bofhd_auth.BofhdAuthRole(db.connection)
    aot = get_op_target(obj)
    ar.grant_auth(sub.entity_id, opset.op_set_id, aot.op_target_id)


def revoke_auth(sub, opset, obj):
    """
    :param Entity sub:
        Subject losing auth.
    :param BofhdAuthOpSet opset:
        The opset (role) that is revoked.
    :param Entity obj:
        The object that is no longer being controlled.
    """
    ar = bofhd_auth.BofhdAuthRole(db.connection)
    aot = get_op_target(obj, create=False)
    roles = list(ar.list(sub.entity_id, opset.op_set_id, aot.op_target_id))

    if len(roles) == 0:
        return False

    ar.revoke_auth(sub.entity_id, opset.op_set_id, aot.op_target_id)

    # If that was the last permission for this op_target, kill op_target
    if len(list(ar.list(op_target_id=aot.op_target_id))) == 0:
        aot.delete()

    return True


def str_to_bool(value):
    """ Convert string bool to bool. """
    if value not in ('true', 'false'):
        raise ValueError('Need true or false; got {}'.format(value))
    return value == 'true'
