#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2012 University of Oslo, Norway
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
"""Mixin module for easier support for Cerebrum entities in Active Directory.

The most important part is the support for storing and administrating
AD-attributes in Cerebrum, to make it easier for various instances to set what
they need and to be able to modify it themselves.

The mixin is then used by the AD-synchronization, to commit any changes to AD.

"""

from Cerebrum.Utils import argument_to_sql, prepare_string
from Cerebrum.Entity import Entity
from Cerebrum.Constants import Constants, _CerebrumCode
from Cerebrum.Constants import _EntityExternalIdCode
from Cerebrum.Constants import _AuthoritativeSystemCode
from Cerebrum.modules.EntityTrait import _EntityTraitCode

class _ADAttrCode(_CerebrumCode):
    """Code values for AD-attributes, used in table ad_attribute."""
    _lookup_table = '[:table schema=cerebrum name=ad_attribute_code]'

    def __init__(self, code, description=None, multivalued=False):
        self.multivalued = bool(multivalued)
        super(_ADAttrCode, self).__init__(code, description)

    def insert(self):
        self.sql.execute("""
            INSERT INTO %(code_table)s
              (%(code_col)s, %(str_col)s, %(desc_col)s, multivalued)
            VALUES
              (%(code_seq)s, :str, :desc, :multivalued)""" % {
                'code_table': self._lookup_table,
                'code_col': self._lookup_code_column,
                'str_col': self._lookup_str_column,
                'desc_col': self._lookup_desc_column,
                'code_seq': self._code_sequence},
                             {'str': self.str,
                              'desc': self._desc,
                              'multivalued': bool(self.multivalued)})

class ConstantsActiveDirectory(Constants):
    """Constants for the Active Directory module, including the basic set of
    AD-attributes that we could administrate.

    Note that some attributes could be administered by the AD-sync, but is based
    on other information in Cerebrum. Surname, DisplayName and GivenName are
    such examples - they all use information from L{person_name}, which is taken
    care of by the AD-sync. Such attributes are therefore not necessary to store
    in the attribute table, at least in general - some instaces might have
    special needs.

    """
    system_ad = _AuthoritativeSystemCode('AD',
                           'Information from Active Directory')
    externalid_groupsid = _EntityExternalIdCode('AD_GRPSID',
                           Constants.entity_group,
                           "Group's SID, fetched from Active Directory")
    externalid_accountsid = _EntityExternalIdCode('AD_ACCSID',
                           Constants.entity_account,
                           "Account's SID, fetched from Active Directory")

    trait_exchange_mdb = _EntityTraitCode(
        'exchange_mdb', Constants.entity_account,
        "The assigned mailbox-database in Exchange for the given account.")

    ### Attributes

    ad_attribute_homedir = _ADAttrCode('HomeDirectory',
                                       'HomeDirectory for an object in AD',
                                       False)

    ad_attribute_homedrive = _ADAttrCode('HomeDrive',
                                         'HomeDrive for an account in AD',
                                         False)

    ad_attribute_scriptpath = _ADAttrCode('ScriptPath',
                                          'ScriptPath for an account in AD',
                                          False)

    # Titles should by default be stored in person_name.
    #ad_attribute_title = _ADAttrCode('Title', 'Title for an account in AD',
    #                                 False)

    # Mail is either handled by its own module, or it is stored as contact_info
    #ad_attribute_mail = _ADAttrCode('Mail', 'Mail address for an account in AD',
    #                                 False)

    # TODO: should we make group scope (global/universal) and group category
    # (security/distribution) be set through attributes?

    ADAttribute = _ADAttrCode

class EntityADMixin(Entity):
    """Mixin class for Active Directory, giving entities the possibility to have
    AD-attributes stored for them.

    All AD-attributes is stored per spread to be able to sync different
    attribute values for different AD domains. If the same value should be
    synced to different AD domains that is connected by different spreads, you
    need to populate the attribute for each spread.

    """

    def delete(self):
        """Delete an entity's AD-attributes."""
        for row in self.list_ad_attributes(entity_id=self.entity_id):
            self.delete_ad_attribute(spread=row['spread'],
                                     attribute=row['attribute'])
        return self.__super.delete()

    def list_ad_attributes(self, entity_id=None, spread=None, attribute=None):
        """List all stored AD-attributes that matches the given criterias.

        :type entity_id: int or list/tuple thereof
        :param entity_id: If the list of attributes should be limited to given
            entitites.

        :type spread: constant, int or list/tuple thereof
        :param spread: If the list of attributes should be limited to given
            spread types.

        :type attribute: constant, int or list/tuple thereof
        :param attribute: If given, the result would be limited to only the
            given attribute types.

        :rtype: iterable of db-rows
        :return:
            All the attributes from the database, limited to the input
            variables. The row elements are:

            - `entity_id`: What entity the attribute is registered for
            - `attr_code`: The attribute's attribute code
            - `spread_code`: What spread the attribute is set up for
            - `subattr_id`: Number for separating multivalued elements.
            - `value`: The string with the attribute value.

        """
        binds = dict()
        where = list()
        for var, name, transform in (("entity_id", "entity_id", int),
                                     ("spread", "spread_code", int),
                                     ("attribute", "attr_code", int)):
            if locals()[var] is not None:
                where.append(argument_to_sql(locals()[var], "at." + name, binds,
                                             transform))
        where = " AND ".join(where)
        if where:
            where = "WHERE " + where
        return self.query("""
            SELECT DISTINCT at.*
            FROM  [:table schema=cerebrum name=ad_attribute] at
            %s""" % (where,), binds)

    def delete_ad_attribute(self, spread, attribute, subattr_id=None):
        """Remove an attribute from the active entity.

        @type spread: constant
        @param spread: From what spread the attribute should be removed from.

        @type attribute: constant
        @param attribute: What attribute type that should be removed.

        @type subattr_id: int
        @param subattr_id: The sub element of a multivalued attribute to remove.
            If not set, all the elements of the given attribute is removed.

        """
        # TODO: check if the attribute exists first?
        cols = [('entity_id', ':e_id'),
                ('spread_code', ':spread'),
                ('attr_code', ':attr')]
        values = {'e_id': self.entity_id,
                  'spread': int(spread),
                  'attr': int(attribute)}
        if subattr_id is not None:
            if not attribute.multivalued:
                raise RuntimeError('attribute is not multivalued')
            cols.append(('subattr_id', ':subid'))
            values['subid'] = int(subattr_id)
        self.execute("""
            DELETE FROM [:table schema=cerebrum name=ad_attribute]
            WHERE %s""" % ' AND '.join('%s=%s' % (x[0], x[1]) for x in cols),
                values)
        self._db.log_change(self.entity_id, self.clconst.ad_attr_del, None,
                            change_params={'spread': str(spread),
                                           'attr': str(attribute)})

    def set_ad_attribute(self, spread, attribute, value, subattr_id=0):
        """Set a given AD-attribute for a given spread for the entity. Note that
        the entity does not need to be registered with the spread, the attribute
        could be stored and then be synced later if the entity gets the spread.

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
        # TODO: change this by putting it in write_db instead?
        if not attribute.multivalued and subattr_id != 0:
            raise RuntimeError("subattr_id is only for multivalued attributes")
        cols = [('entity_id', ':e_id'),
                ('spread_code', ':spread'),
                ('attr_code', ':attr'),
                ('subattr_id', ':subid'),
                ('value', ':value')]
        values = {'e_id': self.entity_id,
                  'spread': int(spread),
                  'attr': int(attribute),
                  'subid': int(subattr_id),
                  'value': value}
        exists = self.list_ad_attributes(entity_id=self.entity_id,
                                         spread=spread,
                                         attribute=attribute)
        # TODO: check if the value(s) is/are equal too?
        if exists:
            self.execute("""
            UPDATE [:table schema=cerebrum name=ad_attribute]
            SET value = :value
            WHERE entity_id = :e_id AND
                  spread_code = :spread AND
                  attr_code = :attr AND
                  subattr_id = :subid""", values)
        else:
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=ad_attribute] (%(tcols)s)
            VALUES (%(binds)s)""" % {'tcols': ", ".join([x[0] for x in cols]),
                                     'binds': ", ".join([x[1] for x in cols])},
                    values)
        self._db.log_change(self.entity_id, self.clconst.ad_attr_add, None,
                            change_params={'spread': str(spread),
                                           'attr': str(attribute),
                                           'value': str(value)})
