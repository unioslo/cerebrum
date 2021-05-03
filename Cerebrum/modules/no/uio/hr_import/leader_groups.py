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
Leader group module.

This module defines the Cerebrum leader groups, ``adm-leder-<ou>``.  These
groups mirror manager roles from the hr system.
"""
import logging

import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory

from Cerebrum.modules.automatic_group.structure import (
    get_automatic_group,
    update_memberships,
)

logger = logging.getLogger(__name__)

LEADER_GROUP_PREFIX = 'adm-leder-'


def get_leader_group(db, identifier):
    return get_automatic_group(db, identifier, LEADER_GROUP_PREFIX)


class LeaderGroupUpdater(object):
    """
    Update leader groups from affs.
    """

    def __init__(self, db, source_system):
        self.db = db
        self.const = Factory.get('Constants')(self.db)
        self.source_system = source_system

    def _get_current_groups(self, person_id):
        gr = Factory.get('Group')(self.db)

        return (r['group_id'] for r in
                gr.search(member_id=person_id,
                          name=LEADER_GROUP_PREFIX + '*',
                          group_type=self.const.group_type_affiliation,
                          filter_expired=True,
                          fetchall=False))

    def _ou_id2stedkode(self, hr_ou_id):
        """Get stedkode from ou_id given by the hr system"""
        # TODO: can probably be made easier with orgreg
        ou = Factory.get('OU')(self.db)
        if isinstance(hr_ou_id, int):
            hr_ou_id = str(hr_ou_id)

        # if the source is SAP - the hr_ou_id should be a 'stedkode'
        if self.source_system == self.const.system_sap:

            try:
                ou.find_stedkode(
                    hr_ou_id[0:2],
                    hr_ou_id[2:4],
                    hr_ou_id[4:6],
                    cereconf.DEFAULT_INSTITUSJONSNR
                )
                return ou.get_stedkode()
            except Errors.NotFoundError:
                raise LookupError("invalid location code hr_ou_id=%r" %
                                  (hr_ou_id,))

        source_systems = (self.const.system_orgreg, self.const.system_manual)
        for source in source_systems:
            try:
                ou.find_by_external_id(
                    id_type=self.const.externalid_dfo_ou_id,
                    external_id=hr_ou_id,
                    source_system=source
                )
            except Errors.NotFoundError:
                ou.clear()
            else:
                return ou.get_stedkode()

        raise LookupError('invalid external ou_id hr_ou_id=%r' % (hr_ou_id,))

    def get_leader_group_ids(self, hr_ou_ids):
        """Convert a set of OU ids into a set of leader group ids"""
        leader_group_ids = set()
        for hr_ou_id in hr_ou_ids:
            try:
                stedkode = self._ou_id2stedkode(hr_ou_id)
            except LookupError as e:
                logger.error('No such ou: %s', e)
            else:
                leader_group_id = get_leader_group(self.db, stedkode).entity_id
                leader_group_ids.add(leader_group_id)
        return leader_group_ids

    def sync(self, person_id, hr_ou_ids):
        require_memberships = self.get_leader_group_ids(hr_ou_ids)
        current_memberships = set(self._get_current_groups(person_id))

        if require_memberships == current_memberships:
            return

        logger.info('Updating person_id=%r leader groups (add=%r, remove=%r)',
                    person_id,
                    require_memberships - current_memberships,
                    current_memberships - require_memberships)

        update_memberships(Factory.get('Group')(self.db),
                           person_id,
                           current_memberships,
                           require_memberships)
