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

from SpineLib.Builder import Attribute
from SpineLib.SpineClass import SpineClass
from SpineLib.DatabaseClass import DatabaseAttr, ConvertableAttribute

__all__ = ['CerebrumAttr', 'CerebrumDbAttr', 'CerebrumClass']

class CerebrumAttr(Attribute, ConvertableAttribute):
    """Object attribute from Cerebrum.

    The value of this attribute will be loaded and saved from Cerebrum.

    You can include your own methods for converting to and from cerebrum when
    saving/loading from cerebrum, in the attr 'convert_to' and
    'convert_from'.

    This attribute has no knowledge about the database, and can therefor not be
    used in the generated search classes, without implementing your own
    searchmethod. For that use, use CerebrumDbAttr or DatabaseAttr instead.
    """
    
    def __init__(self, *args, **vargs):
        if 'convert_to' in vargs.keys():
            self.convert_to = vargs['convert_to']
            del vargs['convert_to']
        if 'convert_from' in vargs.keys():
            self.convert_from = vargs['convert_from']
            del vargs['convert_from']

        super(CerebrumAttr, self).__init__(*args, **vargs)

class CerebrumDbAttr(CerebrumAttr, DatabaseAttr):
    """Object attribute from Cerebrum with info about database.
    
    You can include your own methods for converting to and from cerebrum
    when saving/loading from cerebrum, in the attr 'convert_to' and
    'convert_from'. You can also include the same type of methods for
    when converting to and from the database ('convert_to' & 'convert_from).

    Since this attribute has knowledge about the database, you can use
    it with the generic search-method with found in DatabaseClass and
    CerebrumDbClass.
    """

class CerebrumClass(SpineClass):
    """Mixin class which adds support for cerebrum.

    This class adds support for working directly against cerebrum, and
    for easly wrapping methods found in cerebrum.
    """
    
    cerebrum_class = None
    cerebrum_attr_aliases = {}
    
    def _get_cerebrum_obj(self):
        """Returns the cerebrum-obj for this instance.

        Expect and uses the find-method in the cerebrum_class.
        """
        db = self.get_database()
        obj = self.cerebrum_class(db)
        id = self.get_primary_key()[0]
        if not hasattr(obj, 'find'):
            raise Exception("Cerebrum-class %s has no find-method" % obj.__class__)
        obj.find(id)
        return obj
    
    def _get_cerebrum_name(self, attr):
        """Returns the name of the attribute in cerebrum.

        cerebrum_attr_aliases is a dict with mapping over
        spine-attr-name and cerebrum-attr-name.
        """
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
                setattr(self, attr.get_name_private(), attr.convert_from(value))

    def _save_cerebrum_attributes(self):
        """Stores 'attributes' in cerebrum."""
        obj = self._get_cerebrum_obj()
        for attr in self._cerebrum_save_attributes:
            if attr not in self.updated:
                continue
            value = getattr(self, attr.get_name_private())
            setattr(obj, self._get_cerebrum_name(attr), attr.convert_to(value))
        obj.write_db()

    def _delete(self):
        """Generic method for deleting this instance from cerebrum.

        You should implement your own delete method which will
        invalidate the object after this method has been called.
        """
        obj = self._get_cerebrum_obj()
        obj.delete()

    def _create(cls, db, *args, **vargs):
        """Generic method for creating instances in cerebrum.

        This method is "private" because you should check if the needed
        arguments are given, and since you must returned the newly
        created object yourself, which you lock for writing.
        """
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

# arch-tag: fc65fb2e-4bce-44a7-9ea4-8abb3a5654d1
