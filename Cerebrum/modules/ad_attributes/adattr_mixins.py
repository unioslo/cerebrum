# -*- coding: utf-8 -*-
#
# Copyright 2012-2025 University of Oslo, Norway
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
Entity mixins for AD attributes.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import six

from Cerebrum import Constants
from Cerebrum import Errors
from Cerebrum.Entity import Entity
from . import adattr_constants
from . import adattr_db


class AdAttributeCleanupMixin(Entity):

    def delete(self):
        """Delete an entity's AD-attributes."""
        adattr_db.delete_ad_attributes(self._db, entity_id=int(self.entity_id))
        return super(AdAttributeCleanupMixin, self).delete()


class AdAttributeMixin(AdAttributeCleanupMixin):
    """
    EntityMixin to provide access to AD attributes.

    AD attributes are stored per spread, as different AD domains may need
    different values for some attribute.  If the same value should be
    present for multiple spread values,  the value must be duplicated for each
    spread.
    """
    def list_ad_attributes(self, entity_id=None, spread=None, attribute=None):
        """
        List all AD-attributes that matches the given criterias.

        :type entity_id: NoneType, int, list[int]
        :param entity_id: Limit listing to the given entities

        :type spread: NoneType, _SpreadCode, int, list[int]
        :param spread: Limit listing to attributes with the given spread

        :type attribute: NoneType, _ADAttrCode, int, list[int]
        :param attribute: Limit listing to the given attributes

        :returns:
            All matching attribute rows.  See :const:`.DEFAULT_FIELDS` for a
            list of returned columns.
        """
        # Only allow singular int-values, for backwards compatibility
        search_args = {
            k: int(v)
            for k, v in (
                ('entity_id', entity_id),
                ('spread_code', spread),
                ('attr_code', attribute),
            )
            if v is not None
        }
        return adattr_db.search_ad_attributes(self._db, **search_args)

    def delete_ad_attribute(self, spread, attribute, subattr_id=None):
        """
        Delete a given attribute from the current entity.

        :type spread: _SpreadCode
        @param spread: Which spread to remove an attribute for

        @type attribute: _ADAttrCode
        @param attribute: Which attribute to remove

        :type subattr_id: int
        :param subattr_id:
            Optionally limit to a given element (for multivalued attributes)
        """
        attr_code = self.const.get_constant(adattr_constants._ADAttrCode,
                                            attribute)
        spread_code = self.const.get_constant(Constants._SpreadCode, spread)
        subattr_id = int(subattr_id) if subattr_id else None
        if subattr_id and not attr_code.multivalued:
            raise ValueError(
                "invalid subattr_id=%s for single-valued attribute %s"
                % (repr(subattr_id), six.text_type(attr_code)))

        deleted_rows = adattr_db.delete_ad_attributes(
            self._db,
            entity_id=int(self.entity_id),
            spread_code=spread_code,
            attr_code=attr_code,
            subattr_id=subattr_id,
        )

        if len(deleted_rows) < 1:
            params = {
                'entity_id': self.entity_id,
                'spread_code': spread_code,
                'attr_code': attr_code,
                'subattr_id': subattr_id,
            }
            raise Errors.NotFoundError("ad attribute %s" % repr(params))
        return deleted_rows

    def set_ad_attribute(self, spread, attribute, value, subattr_id=0):
        """
        Set an AD attribute for the current entity.

        Note that the entity doesn't need to be registered with the spread, the
        attribute could be stored and then be synced later if the entity gets
        the spread.

        If the attribute is multivalued, you could only add a single element in
        one go. TODO: This might be changed in the future, depending on what we
        need to do.

        @type spread: Constant
        @param spread: The spread that the attribute should be registered for.

        @type attribute: Constant
        @param attribute: The attribute type that should be registered.

        @type value: string
        @param value: The value for the attribute or for a single element in a
            multivalued attribute.

        @type subattr_id: int
        @param subattr_id: The id for a subpart of a multivalued attribute. You
            should start on 0.
            TODO: this might change in the future!

        """
        spread_code = self.const.get_constant(Constants._SpreadCode, spread)
        attr_code = self.const.get_constant(adattr_constants._ADAttrCode,
                                            attribute)

        if not attr_code.multivalued and subattr_id != 0:
            raise ValueError(
                "invalid subattr_id=%s for single-valued attribute %s"
                % (repr(subattr_id), six.text_type(attr_code)))

        adattr_db.set_ad_attribute(self._db, int(self.entity_id), spread_code,
                                   attr_code, subattr_id, value)
