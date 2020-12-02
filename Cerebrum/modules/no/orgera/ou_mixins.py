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
""" ORG-ERA mixins for OU objects. """
import logging

from Cerebrum.OU import OU

from .job_assignments import delete_assignments

logger = logging.getLogger(__name__)


def clear_assignments_for_ou(db, ou_id):
    """ Remove all org-era assignment roles related to a given ou. """
    for row in delete_assignments(db, ou_id=int(ou_id)):
        logger.info('removed org-era assignment for ou_id=%r (%r)',
                    ou_id, tuple(row))
        # TODO: Any group tied to this ou is no longer maintained, should
        # we mark the group for deletion too?


class OrgEraOuMixin(OU):
    """ ORG-ERA mixin for Org Units.  """

    def __delete__(self):
        clear_assignments_for_ou(self._db, self.entity_id)
        return super(OrgEraOuMixin, self).delete()
