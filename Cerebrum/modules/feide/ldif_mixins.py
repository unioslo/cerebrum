# -*- coding: utf-8 -*-
#
# Copyright 2016-2022 University of Oslo, Norway
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
Feide-related OrgLDIF mixins.
"""
from __future__ import unicode_literals

import logging

from Cerebrum.Utils import make_timer
from Cerebrum.modules.LDIFutils import attr_unique, normalize_string
from Cerebrum.modules.feide.service import FeideService
from Cerebrum.modules.no.OrgLDIF import NorEduOrgLdifMixin


logger = logging.getLogger(__name__)


class NorEduAuthnLevelMixin(NorEduOrgLdifMixin):
    """
    Mixin to provide Feide service MFA requirements.

    This mixin adds support for the norEduPersonServiceAuthnLevel attribute.

    The py:mod:`Cerebrum.modules.feide.service` module provides individual
    MFA requirements for (person_id, feide_id) pairs.

    .. note::
       This is for providing custom MFA requirements for individual users at
       individual services.

       No support for the special service ``all`` (require MFA for all services
       for a given user/person).

       No support to require MFA for *all* users of a *given* service - this
       should be configured in the Feide customer portal.
    """

    feide_service_authn_level_fmt = (
        'urn:mace:feide.no:spid:{feide_id} '
        'urn:mace:feide.no:auth:level:fad08:{level}')

    @property
    def person_authn_levels(self):
        """ Returns a authentication level mapping for update_person_authn.

        Initializes self.person_authn_levels with a dict that maps person_id to
        a set of service authentication levels:

            person_id -> set([
              (feide_service_id, authentication_level),
              ...
            ]),

        """
        if not hasattr(self, '_person_authn_levels'):
            timer = make_timer(logger,
                               'Fetching authentication levels...')
            fse = FeideService(self.db)
            self._person_authn_levels = fse.get_person_to_authn_level_map()
            timer("...authentication levels done.")
        return self._person_authn_levels

    def _get_service_authn_levels(self, person_id):
        """ Get norEduPersonServiceAuthnLevel values for a person.  """
        authn_levels = []
        for feide_id, level in self.person_authn_levels.get(person_id, []):
            value = self.feide_service_authn_level_fmt.format(
                feide_id=feide_id,
                level=level,
            )
            authn_levels.append(value)

        return attr_unique(authn_levels, normalize=normalize_string)

    def update_person_entry(self, entry, row, person_id):
        super(NorEduAuthnLevelMixin, self).update_person_entry(
            entry, row, person_id)

        # norEdu 1.6 introduces two-factor auth:
        if self.FEIDE_schema_version < '1.6':
            return

        # If parent didn't add norEduPerson, we can't add norEduPerson
        # attributes
        if 'norEduPerson' not in entry['objectClass']:
            return

        authn_levels = self._get_service_authn_levels(person_id)
        if authn_levels:
            entry['norEduPersonServiceAuthnLevel'] = authn_levels
