# -*- coding: utf-8 -*-

# Copyright 2019 University of Oslo, Norway
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

from Cerebrum import Constants


class EntityExpireConstants(Constants.CLConstants):
    """Constants specific for C{EntityExpire}."""
    entity_expire_add = Constants._ChangeTypeCode(
        "entity_expire", "add",
        "added expire date for %(subject)s",
        ("new_expire_date=%(new_expire_date)s",))
    entity_expire_del = Constants._ChangeTypeCode(
        "entity_expire", "del",
        "deleted expire date for %(subject)s",
        ("old_expire_date=%(old_expire_date)s",))
    entity_expire_mod = Constants._ChangeTypeCode(
        "entity_expire", "mod",
        "modified expire date for %(subject)s",
        ("old_expire_date=%(old_expire_date)s",
         "new_expire_date=%(new_expire_date)s"))
