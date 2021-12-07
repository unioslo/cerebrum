# -*- coding: utf-8 -*-
#
# Copyright 2021 University of Oslo, Norway
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
Import entity matcher utils.

This module provides utils for finding a given entity object in Cerebrum, to
use for later updates.  In imports, it is useful to separate between *match
criterias* and *search criterias*:

Match criterias are (id_type, id_value) pairs that are *good enough* to
identify a matching entity.  These are typically system specific internal ids
(e.g. NO_FSNO, GREG_PID, DFO_PID) and will always point to the *correct*
object, even if a duplicate exists.

Objects found using match criterias should be updated, but we should still
check any other search criterias, and warn if we find another (duplicate)
object.

If we find *multiple* objects using the match criterias, something is
horribly wrong, and we should abort/fail.

Search criterias contain all known identifiers for an object, and should be
used to find a candidate entity if no *match* can be found.

Examples:

::

    # using match criterias
    find_person = PersonMatcher(['GREG_PID', 'DFO_PID'])
    person = find_person([('GREG_PID', '1'), ('NO_PASSNR', '3')])

    # without match criterias
    find_person = PersonMatcher()
    person = find_person([('GREG_PID', '1'), ('NO_PASSNR', '3')])
"""
import logging

import six

from Cerebrum import Errors
from Cerebrum.Utils import Factory

logger = logging.getLogger(__name__)


class EntityMatcher(object):
    """ Generic entity matcher for imports.  """

    factory_type = 'Entity'

    def __init__(self, match_types=None):
        """
        :param match:
            sequence of id_types to use with matching.
        """
        self.match_types = tuple(match_types or ())

    @property
    def type(self):
        return self.factory_type.lower()

    def _find_candidate(self, db, criterias):
        if not criterias:
            raise ValueError('No search criterias given')
        dbobj = Factory.get(self.factory_type)(db)
        id_pairs = tuple((dbobj.const.EntityExternalId(t), v)
                         for t, v in criterias)
        pretty_types = tuple(sorted([six.text_type(t[0]) for t in id_pairs]))

        try:
            dbobj.find_by_external_ids(*id_pairs)
            logger.debug('found %s entity_id=%d from %s',
                         self.type, dbobj.entity_id, pretty_types)
            return dbobj
        except Errors.NotFoundError:
            logger.debug('no %s matches for %s', self.type, pretty_types)
        except Errors.TooManyRowsError:
            logger.debug('multiple %s matches for %s', self.type, pretty_types)
            raise

    def __call__(self, db, s_terms, required=False):
        """ Find an entity by provided search terms.

        :param s_terms:
            a sequence if (id_type, id_value) pairs to search for.

        :param required:
            require a match/search hit.
        """
        m_terms = tuple(t for t in s_terms if t[0] in self.match_types)
        m_hit = s_hit = None

        if m_terms and m_terms != s_terms:
            m_hit = self._find_candidate(db, m_terms)

        try:
            s_hit = self._find_candidate(db, s_terms)
        except Errors.TooManyRowsError as e:
            if m_hit:
                logger.warning('search found multiple entities: %s', e)
            else:
                # no match, but multiple search hits - this is a problem
                raise

        if m_hit and s_hit and m_hit.entity_id != s_hit.entity_id:
            # should never happen - s_terms is always a superset of m_terms
            raise Errors.TooManyRowsError(
                'match/search found multuple %s: %d, %d'
                % (self.type, m_hit.entity_id, s_hit.entity_id))

        # We've handled all issues with multiple hits, and have either:
        # - a match hit (in which case, we don't really care about search hits)
        # - no match hit, but a search hit
        # - no hits at all (typically requires a new entity to be created)
        hit = m_hit or s_hit
        if hit:
            logger.info('found %s (entity_id=%d)', self.type, hit.entity_id)
        else:
            logger.info('no matching %s objects', self.type)
            if required:
                raise Errors.NotFoundError('no matching %s objects' %
                                           (self.type,))
        return hit


class PersonMatcher(EntityMatcher):

    factory_type = 'Person'


class OuMatcher(EntityMatcher):

    factory_type = 'OU'
