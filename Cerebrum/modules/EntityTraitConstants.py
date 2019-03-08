# coding: utf-8
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
from Cerebrum.Constants import Constants as CereConst
from Cerebrum.Constants import CLConstants as ClConst
from Cerebrum.Constants import (_CerebrumCodeWithEntityType,
                                _ChangeTypeCode)


class _EntityTraitCode(_CerebrumCodeWithEntityType):
    """Code values for entity traits, used in table entity_trait."""
    _lookup_table = '[:table schema=cerebrum name=entity_trait_code]'
    pass


class CLConstants(ClConst):
    trait_add = _ChangeTypeCode("trait", "add",
                                "new trait for %(subject)s",
                                ("%(trait:code)s",
                                 "numval=%(int:numval)s",
                                 "strval=%(string:strval)s",
                                 "date=%(string:date)s",
                                 "target=%(entity:target_id)s"))
    trait_del = _ChangeTypeCode("trait", "del",
                                "removed trait from %(subject)s",
                                ("%(trait:code)s",
                                 "numval=%(int:numval)s",
                                 "strval=%(string:strval)s",
                                 "date=%(string:date)s",
                                 "target=%(entity:target_id)s"))
    trait_mod = _ChangeTypeCode("trait", "mod",
                                "modified trait for %(subject)s",
                                ("%(trait:code)s",
                                 "numval=%(int:numval)s",
                                 "strval=%(string:strval)s",
                                 "date=%(string:date)s",
                                 "target=%(entity:target_id)s"))

    # There are no mandatory EntityTraitCodes


class Constants(CereConst):
    EntityTrait = _EntityTraitCode
