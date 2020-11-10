# -*- coding: utf-8 -*-
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
"""
Matcher

Used for getting Cerebrum person matching some external ids
"""
from __future__ import unicode_literals

import logging

import six

from Cerebrum.modules.hr_import import mapper as _base
from Cerebrum import Errors
from Cerebrum.Utils import Factory

logger = logging.getLogger(__name__)


def match_entity(external_ids, source_system, database):
    """Find matching Cerebrum entity for the given external_ids

    :type external_ids: set(HRExternalId)
    :type source_system: AuthoritativeSystem
    :param database: Cerebrum database
    """
    db_object = Factory.get('Person')(database)
    const = Factory.get('Constants')(database)

    match_ids = tuple(
        (const.EntityExternalId(i.id_type), i.external_id, source_system)
        for i in external_ids
    )

    try:
        db_object.find_by_external_ids(*match_ids)
        logger.info('match_entity: found existing person, id=%r',
                    db_object.entity_id)
    except Errors.NotFoundError:
        logger.debug(
            'match_entity: could not find existing person, id_type=%s',
            tuple(six.text_type(i[0]) for i in match_ids))
        raise _base.NoMappedObjects('no matching persons')
    except Errors.TooManyRowsError as e:
        raise _base.ManyMappedObjects(
            'Person mismatch: found multiple matches: {}'.format(e))
    return db_object
