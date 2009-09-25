# -*- coding: iso-8859-1 -*-

# Copyright 2004, 2005 University of Oslo, Norway
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
#

class DTO(object):
    def __repr__(self):
        return str(self.__dict__)

    def __eq__(self, other):
        if other is None: return False
        return self.__dict__ == other.__dict__

    @classmethod
    def from_row(cls, row):
        dto = cls()
        for key, value in row.items():
            setattr(dto, key, value)
        return dto

    @classmethod
    def from_obj(cls, obj):
        dto = cls()
        for attr in obj.__read_attr__ + obj.__write_attr__:
            if attr.startswith("_"):
                continue

            value = getattr(obj, attr, '')
            setattr(dto, attr, value)
        return dto
