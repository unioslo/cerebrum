# coding: utf-8
#
# Copyright 2018-2024 University of Oslo, Norway
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
Base constant types and constants related to traits
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import Cerebrum.Constants


class _EntityTraitCode(Cerebrum.Constants._CerebrumCodeWithEntityType):
    """
    Code values for entity traits, used in table entity_trait
    """
    _lookup_table = '[:table schema=cerebrum name=entity_trait_code]'


class CLConstants(Cerebrum.Constants.CLConstants):
    """
    Mixin to provide entity change types.
    """

    trait_add = Cerebrum.Constants._ChangeTypeCode(
        "entity_trait", "add",
        "new trait for %(subject)s",
        (
            "%(trait:code)s",
            "numval=%(int:numval)s",
            "strval=%(string:strval)s",
            "date=%(string:date)s",
            "target=%(entity:target_id)s",
        )
    )

    trait_del = Cerebrum.Constants._ChangeTypeCode(
        "entity_trait", "remove",
        "removed trait from %(subject)s",
        (
            "%(trait:code)s",
            "numval=%(int:numval)s",
            "strval=%(string:strval)s",
            "date=%(string:date)s",
            "target=%(entity:target_id)s",
        )
    )

    trait_mod = Cerebrum.Constants._ChangeTypeCode(
        "entity_trait", "modify",
        "modified trait for %(subject)s",
        (
            "%(trait:code)s",
            "numval=%(int:numval)s",
            "strval=%(string:strval)s",
            "date=%(string:date)s",
            "target=%(entity:target_id)s",
        )
    )


class Constants(Cerebrum.Constants.Constants):
    """
    Mixin to provide entity trait type as ``Constants.EntityTrait``.
    """
    EntityTrait = _EntityTraitCode
