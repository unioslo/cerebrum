#! /usr/bin/env python
# encoding: utf-8
#
# Copyright 2020 University of Oslo, Norway
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
""" Utils for various event publisher related things"""
import six

from Cerebrum.Errors import NotFoundError
from Cerebrum.Utils import Factory
from Cerebrum.modules.event_publisher.event import EntityRef
from Cerebrum.Entity import EntityName

try:
    from cereconf import ENTITY_TYPE_NAMESPACE
except ImportError:
    ENTITY_TYPE_NAMESPACE = dict()


def get_entity_ref(db, entity_id):
    """ Make an EntityRef by looking up the entity_id in the database.

    entity_id -> EntityRef(<entity_id>, <entity_type>, <entity_name>)
    """
    # TODO: Include entity names in change_params, so that we don't have to
    #       look them up.
    constants = Factory.get("Constants")(db)
    entity = EntityName(db)
    entity_ident = entity_type = None

    # Lookup type
    try:
        entity.find(entity_id)
        entity_type = six.text_type(constants.EntityType(entity.entity_type))
    except NotFoundError:
        pass

    # lookup name
    if entity_type in ENTITY_TYPE_NAMESPACE:
        try:
            entity_ident = entity.get_name(
                constants.ValueDomain(
                    ENTITY_TYPE_NAMESPACE[entity_type]))
        except (AttributeError, TypeError, NotFoundError):
            pass

    # We *have* entity_id, *should have* entity_type,
    # and *may* have an entity_ident.
    return EntityRef(
        entity_id,
        entity_type,
        entity_ident or six.text_type(entity_id))
