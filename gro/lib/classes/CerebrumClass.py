# -*- coding: iso-8859-1 -*-
# Copyright 2002, 2003 University of Oslo, Norway
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

from Builder import Attribute
import Database

__all__ = ['CerebrumAttr', 'CerebrumEntityAttr', 'CerebrumClass']

class CerebrumAttr(Attribute):
    def __init__(self, name, data_type, cerebrum_name=None,
                 writable=False, from_cerebrum=None, to_cerebrum=None):
        Attribute.__init__(self, name, data_type, writable)

        self.cerebrum_name = cerebrum_name or name
        if to_cerebrum is not None:
            self.to_cerebrum = to_cerebrum
        if from_cerebrum is not None:
            self.from_cerebrum = from_cerebrum

        assert type(self.cerebrum_name) == str

    def to_cerebrum(self, value):
        return value

    def from_cerebrum(self, value):
        return value

class CerebrumEntityAttr(CerebrumAttr):
    def to_cerebrum(self, value):
        return value.get_entity_id()

    def from_cerebrum(self, value):
        import Entity
        return Entity.Entity(value)

class CerebrumTypeAttr(CerebrumAttr):
    def __init__(self, name, data_type, type_class, cerebrum_name=None, writable=False):
        CerebrumAttr.__init__(self, name, data_type, cerebrum_name, writable)
        self.type_class = type_class

    def to_cerebrum(self, value):
        return value.get_id()

    def from_cerebrum(self, value):
        return self.type_class.get_by_id(value)

class CerebrumClass(object):
    cerebrum_class = None

    def _load_cerebrum(self):
        e = self.cerebrum_class(Database.get_database())
        e.find(self.get_entity_id())

        for attr in self.slots:
            if not isinstance(attr, CerebrumAttr):
                continue
            value = getattr(e, attr.cerebrum_name)
            if attr.data_type == 'long':
                value = int(value)

            value = attr.from_cerebrum(value)
            setattr(self, '_' + attr.name, value)

    def _save_cerebrum(self):
        e = self.cerebrum_class(Database.get_database())
        e.find(self.get_entity_id())

        for attr in self.slots:
            if not isinstance(attr, CerebrumAttr):
                continue
            if not attr.writable:
                continue
            value = getattr(self, '_' + attr.name)
            value = attr.to_cerebrum(value)
            setattr(e, attr.cerebrum_name, value)

        e.write_db()

    def build_methods(cls):
        for i in cls.slots:
            setattr(cls, 'load_' + i.name, cls._load_cerebrum)
        for i in cls.slots:
            setattr(cls, 'save_' + i.name, cls._save_cerebrum)

    build_methods = classmethod(build_methods)
