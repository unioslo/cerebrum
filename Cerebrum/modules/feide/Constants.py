# -*- coding: utf-8 -*-
#
# Copyright 2018-2022 University of Oslo, Norway
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
"""Constants for the feide service"""

import Cerebrum.Constants
from Cerebrum.modules.bofhd.bofhd_constants import _AuthRoleOpCode


class Constants(Cerebrum.Constants.Constants):

    entity_feide_service = Cerebrum.Constants._EntityTypeCode(
        'feide_service',
        'Feide service',
    )

    auth_feide_commands = _AuthRoleOpCode(
        'feide_commands',
        "Grant access to Feide commands",
    )


class CLConstants(Cerebrum.Constants.CLConstants):

    feide_service_add = Cerebrum.Constants._ChangeTypeCode(
        'feide_service', 'add',
        'added feide service %(subject)s',
        ("feide_id=%(int:feide_id)s", "name=%(string:name)s"),
    )

    feide_service_mod = Cerebrum.Constants._ChangeTypeCode(
        'feide_service', 'modify',
        'modified feide service %(subject)s',
        ("feide_id=%(int:feide_id)s", "name=%(string:name)s"),
    )

    feide_service_del = Cerebrum.Constants._ChangeTypeCode(
        'feide_service', 'remove',
        'deleted feide service %(subject)s',
        ("feide_id=%(int:feide_id)s", "name=%(string:name)s"),
    )

    feide_service_authn_level_add = Cerebrum.Constants._ChangeTypeCode(
        'feide_service_authn_level', 'add',
        'added authn level for %(subject)s, service=%(dest)s',
        "level=%(int:level)s",
    )

    feide_service_authn_level_mod = Cerebrum.Constants._ChangeTypeCode(
        'feide_service_authn_level', 'modify',
        'modified authn level for %(subject)s, service=%(dest)s',
        "level=%(int:level)s",
    )

    feide_service_authn_level_del = Cerebrum.Constants._ChangeTypeCode(
        'feide_service_authn_level', 'remove',
        'deleted authn level for %(subject)s, service=%(dest)s',
        "level=%(int:level)s",
    )
