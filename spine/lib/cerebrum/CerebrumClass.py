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

import pyPgSQL
from SpineLib.Builder import Attribute
from SpineLib.SpineClass import SpineClass
from SpineLib.DatabaseClass import DatabaseClass, DatabaseAttr

__all__ = ['CerebrumAttr', 'CerebrumDbAttr', 'CerebrumClass']

class CerebrumAttr(Attribute):
    """Object attribute from Cerebrum.

    The value of this attribute will be loaded and saved from Cerebrum.

    You can include your own methods for converting to and from cerebrum when
    saving/loading from cerebrum, in the attr 'to_cerebrum' and
    'from_cerebrum'.

    This attribute has no knowledge about the database, and can therefor not be
    used in the generated search classes, without implementing your own
    searchmethod. For that use, use CerebrumDbAttr or DatabaseAttr instead.
    """
    
    def __init__(self, *args, **vargs):
        if 'to_cerebrum' in vargs.keys():
            self.to_cerebrum = vargs['to_cerebrum']
            del vargs['to_cerebrum']
        if 'from_cerebrum' in vargs.keys():
            self.from_cerebrum = vargs['from_cerebrum']
            del vargs['from_cerebrum']

        super(CerebrumAttr, self).__init__(*args, **vargs)

    def to_cerebrum(self, value):
        if isinstance(value, SpineClass):
            key = value.get_primary_key()
            assert len(key) == 1
            return key[0]
        else:
            return value

    def from_cerebrum(self, value):
        if isinstance(value, pyPgSQL.PgSQL.PgNumeric):
            value = int(value)
        return self.data_type(value)

class CerebrumDbAttr(CerebrumAttr, DatabaseAttr):
    """Object attribute from Cerebrum with info about database.
    
    You can include your own methods for converting to and from cerebrum
    when saving/loading from cerebrum, in the attr 'to_cerebrum' and
    'from_cerebrum'. You can also include the same type of methods for
    when converting to and from the database ('to_db' & 'from_db).

    Since this attribute has knowledge about the database, you can use
    it with the generic search-method with found in DatabaseClass and
    CerebrumDbClass.
    """

class CerebrumClass(SpineClass):

    cerebrum_class = None
    cerebrum_attr_aliases = {}
    
    def _get_cerebrum_obj(self):
        db = self.get_database()
        obj = self.cerebrum_class(db)
        id = self.get_primary_key()[0]
        if not hasattr(obj, 'find'):
            raise Exception("Cerebrum-class %s has no find-method" % obj.__class__)
        obj.find(id)
        return obj
    
    def _get_cerebrum_name(self, attr):
        if attr.name in self.cerebrum_attr_aliases.keys():
            return self.cerebrum_attr_aliases[attr.name]
        else:
            return attr.name
    
    def _load_cerebrum_attributes(self):
        """Loads 'attributes' from cerebrum."""
        obj = self._get_cerebrum_obj()
        for attr in self._cerebrum_load_attributes:
            if not hasattr(self, attr.get_name_private()):
                value = getattr(obj, self._get_cerebrum_name(attr))
                setattr(self, attr.get_name_private(), attr.from_cerebrum(value))

    def _save_cerebrum_attributes(self):
        """Stores 'attributes' in cerebrum."""
        obj = self._get_cerebrum_obj()
        for attr in self._cerebrum_save_attributes:
            if i not in self.updated:
                continue
            value = getattr(self, attr.get_name_private())
            setattr(obj, self._get_cerebrum_name(attr), attr.to_cerebrum(value))
        obj.write_db()

    def _delete(self):
        # FIXME: invalidate? må vel gjøre noe mer.
        obj = self._get_cerebrum_obj()
        obj.delete()

    def _create(cls, db, *args, **vargs):
        # FIXME: skal ikke denne returnere noe?
        obj = self.cerebrum_class(db)
        obj.populate(*args, **vargs)
        obj.write_db()

    _create = classmethod(_create)

    def build_methods(cls):
        if '_db_load_attributes' not in cls.__dict__:
            cls._cerebrum_load_attributes = []
            cls._cerebrum_save_attributes = []

        for attr in cls.slots:
            # We only care about CerebrumAttr's
            if not isinstance(attr, CerebrumAttr):
                continue

            # Only pure CerebrumAttrs gets a load methods
            if not isinstance(attr, DatabaseAttr) and not hasattr(cls, attr.get_name_load()):
                cls._cerebrum_load_attributes.append(attr)
                setattr(cls, attr.get_name_load(), cls._load_cerebrum_attributes)
            # Every writable CerebrumAttr gets save methods
            if attr.write and not hasattr(cls, attr.get_name_save()):
                cls._cerebrum_save_attributes.append(attr)
                setattr(cls, attr.get_name_save(), cls._save_cerebrum_attributes)

        super(CerebrumClass, cls).build_methods()

    build_methods = classmethod(build_methods)
