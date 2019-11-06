#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2018 University of Oslo, Norway
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


import Cerebrum.Constants as CereConst
from Cerebrum.Utils import Factory


Entity_class = Factory.get("Entity")


class Constants(CereConst.Constants):
    # Entity type
    entity_feide_service = CereConst._EntityTypeCode('feide_service',
                                                     'Feide service')


class CLConstants(CereConst.CLConstants):
    # Change log
    feide_service_add = CereConst._ChangeTypeCode(
        'feide_service', 'add',
        'added feide service %(subject)s',
        ("feide_id=%(int:feide_id)s", "name=%(string:name)s"))
    feide_service_mod = CereConst._ChangeTypeCode(
        'feide_service', 'modify',
        'modified feide service %(subject)s',
        ("feide_id=%(int:feide_id)s", "name=%(string:name)s"))
    feide_service_del = CereConst._ChangeTypeCode(
        'feide_service', 'remove',
        'deleted feide service %(subject)s',
        ("feide_id=%(int:feide_id)s", "name=%(string:name)s"))

    feide_service_authn_level_add = CereConst._ChangeTypeCode(
        'feide_service_authn_level', 'add',
        'added authn level for %(subject)s, service=%(dest)s',
        "level=%(int:level)s")
    feide_service_authn_level_mod = CereConst._ChangeTypeCode(
        'feide_service_authn_level', 'modify',
        'modified authn level for %(subject)s, service=%(dest)s',
        "level=%(int:level)s")
    feide_service_authn_level_del = CereConst._ChangeTypeCode(
        'feide_service_authn_level', 'remove',
        'deleted authn level for %(subject)s, service=%(dest)s',
        "level=%(int:level)s")
