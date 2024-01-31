# -*- coding: utf-8 -*-
#
# Copyright 2016-2023 University of Oslo, Norway
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
Utils for the Cerebrum REST API.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import six
from flask import url_for

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.rest.api import db


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
            if (isinstance(identifier, six.text_type)
                    and not identifier.isdigit()):
                raise EntityLookupError("entity_id must be a number")
            account.find(identifier)
        elif idtype == 'posix_uid':
            if (isinstance(identifier, six.text_type)
                    and not identifier.isdigit()):
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
    if entype == 'group':
        return get_group(identifier, idtype=idtype, grtype=entype)
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

    :param Entity/int entity:
        The entity object or its ID

    :return text:
        The name of the entity
    """
    if isinstance(entity, six.integer_types):
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


def str_to_bool(value):
    """ Convert string bool to bool. """
    if value not in ('true', 'false'):
        raise ValueError('Need true or false; got {}'.format(value))
    return value == 'true'


def href_from_entity_type(entity_type, entity_id, entity_name=None):
    """Generate an href matching the type of an entity

    :param int entity_type: int value entity type constant
    :param int entity_id: The entity id of the entity
    :param str entity_name: Name if we already have
    :return: None or href pointing to entity
    """
    if entity_type == db.const.entity_person:
        return url_for('.person', id=entity_id)
    elif entity_type == db.const.entity_group:
        return url_for('.group',
                       name=entity_name or get_entity_name(entity_id))
    elif entity_type == db.const.entity_account:
        return url_for('.account',
                       name=entity_name or get_entity_name(entity_id))
    return None
