#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2015-2018 University of Oslo, Norway
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

"""Mixin for letting persons approve or deny a proposition.

The main reason for this module is for when the person needs to give an opt-in
or opt-out of some feature, the main examples being:

    * For legal matters, an opt-in may be required before exporting personal
      data to some external system.
    * For security reasons, my account should not be used for some feature

Usage
======

1. Add Cerebrum.modules.Consent/Constants to CLASS_CONSTANTS
2. For each consent in question, add a constant with type
   EntityConsentCode::

        class MyConstants(Constants):
            myconsentcode = Constants.EntityConsentCode(
                'myconsent',
                description="My consent",
                consent_type=Constants.consent_opt_in,
                entity_type=Constants.entity_person)

3. Add Cerebrum.modules.Consent.EntityConsentMixin to CLASS_ENTITY (or
   subclasses thereof)
4. Use the api

Here, consent type is either consent_opt_in or consent_opt_out. When a consent
is set, a check against entity_type is done.

API
====

The API is contained in EntityConsentMixin:

Whenever the user agrees to some proposition, the corresponding consent code
is used to set a consent::

    person.find(xxx)
    person.set_consent(co.myconsentcode, "Given consent in Brukerinfo", None)

set_consent can also be used to update consents, or only one of the two
fields. A consent can also be removed with::

    person.remove_consent(co.myconsentcode)

Neither set_consent() nor remove_consent() has any effect until write_db()
is called.

Change logging
===============

Three events exist: consent_approve, consent_decline, and consent_remove.
The first two corresponds to new or updated consents with opt-in or opt-out
respectively. The last is sent when consent is removed.
"""

from Cerebrum.Entity import Entity
from Cerebrum.Errors import PolicyException
from Cerebrum.Utils import NotSet, argument_to_sql
from ConsentConstants import CLConstants, Constants, _EntityConsentCode

__version__ = "1.1"


class EntityConsentMixin(Entity):
    """Mixin for approve/deny propositions.
    """
    def __init__(self, *rest, **kw):
        super(EntityConsentMixin, self).__init__(*rest, **kw)
        self.__consents = {}

    def clear(self):
        """Clear this object"""
        super(EntityConsentMixin, self).clear()
        self.__consents = {}

    def list_consents(self, consent_code=None, entity_type=None,
                      consent_type=None, entity_id=None,
                      filter_expired=True):
        """List all entities filtered by argument.

        Note: consent_code, entity_type, consent_type and entity_id can also be
        a tuple, set or list of the type specified below.

        :type consent_code: Constants.EntityConsent
        :param consent_code: The consent code(s) corresponding to proposition.

        :type entity_type: Constants.EntityType
        :param entity_type: Filter for entity_type(s) (part of consent code).

        :type consent_type: Constants.ConsentType
        :param consent_type: The type(s) of consents to list.

        :type entity_id: int
        :param entity_id: List consents for given entity(ies).

        :type filter_expired: Bool
        :param filter_expired: Iff true, remove expired consents.

        :returns: List of db rows.
        """
        filters = set()
        args = {}
        if consent_code:
            filters.add(
                argument_to_sql(consent_code, 'consent_code', args, int))
        if entity_type:
            filters.add(
                argument_to_sql(entity_type, 'entity_type', args, int))
        if consent_type:
            filters.add(
                argument_to_sql(consent_type, 'consent_type', args, int))
        if entity_id:
            filters.add(
                argument_to_sql(entity_id, 'entity_id', args))
        if filter_expired:
            filters.add('(expiry is null or expiry < [:now])')
        sql = """SELECT entity_consent.*
        FROM [:table schema=cerebrum name=entity_consent]
        INNER JOIN [:table schema=cerebrum name=entity_consent_code]
        ON consent_code = code"""
        if filters:
            sql += " WHERE " + " AND ".join(filters)
        return self.query(sql, args)

    def get_consent_status(self, consent_code):
        """Returns a row for self and consent_code, or None.

        :type consent_code: Constants.EntityConsent
        :param consent_code: The corresponding consent code.

        :returns: Db row or None
        """
        ret = self.list_consents(consent_code=consent_code,
                                 entity_id=self.entity_id)
        if ret:
            return ret[0]

    def set_consent(self, consent_code, description=NotSet, expiry=NotSet):
        """Set/update consent status for self and this consent_code.

        For description and expiry params, NotSet yields null in new consents,
        and no change in existing database entries. (Be careful in the event
        of expired consents.) None will always beget a null.

        :type consent_code: Constants.EntityConsent
        :param consent_code: Corresponding consent

        :type description: string, NotSet or None (=Null)
        :param description: Description.

        :type expiry: mx.DateTime, NotSet or None (=Null)
        :param description: expiry.
        """
        if not isinstance(consent_code, _EntityConsentCode):
            consent_code = _EntityConsentCode(consent_code)
        if consent_code.consent_type == Constants.consent_opt_in:
            change = CLConstants.consent_approve
        else:
            change = CLConstants.consent_decline
        if consent_code.entity_type != self.entity_type:
            # raise PolicyException("Consent {type} not compatible"
            #                       " with {etype}".format(
            #                            type=consent_code,
            #                            etype=self.entity_type))
            raise PolicyException("Consent %(type)s not compatible"
                                  " with %(etype)s" % {
                                      'type': consent_code,
                                      'etype': self.entity_type})
        code = int(consent_code)
        if code not in self.__consents:
            self.__consents[code] = {
                'consent_code': consent_code
            }
        elif 'deleted' in self.__consents[code]:
            del self.__consents[code]['deleted']
        if description is not NotSet:
            self.__consents[code]['description'] = description
        if expiry is not NotSet:
            self.__consents[code]['expiry'] = expiry
        change_params = self.__consents[code].copy()
        change_params['consent_code'] = code
        change_params['consent_string'] = str(consent_code)
        self._db.log_change(self.entity_id, change, None,
                            change_params=change_params)

    def remove_consent(self, consent_code):
        """Removes a consent of given type"""
        code = int(consent_code)
        if code in self.__consents:
            self.__consents[code]['deleted'] = True
        else:
            self.__consents[code] = {'deleted': True}
        self._db.log_change(self.entity_id, CLConstants.consent_remove, None,
                            change_params={
                                'consent_code': code,
                                'consent_string': str(consent_code)})

    def write_db(self):
        """Write changes to database."""
        super(EntityConsentMixin, self).write_db()
        if not self.__consents:
            return
        insert = """
        INSERT INTO [:table schema=cerebrum name=entity_consent]
        (entity_id, consent_code, description, time_set, expiry)
        VALUES (:entity_id, :consent_code, :description, now(), :expiry)
        """
        # update = """
        # UPDATE [:table schema=cerebrum name=entity_consent]
        # SET {field} = :value
        # """
        update = """
        UPDATE [:table schema=cerebrum name=entity_consent]
        SET %(field)s = :value
        """
        delete = """DELETE FROM [:table schema=cerebrum name=entity_consent]
        WHERE entity_id=:entity_id AND consent_code=:consent_code"""
        consents = [int(x['consent_code'])
                    for x in self.list_consents(entity_id=self.entity_id,
                                                filter_expired=False)]
        for c, obj in self.__consents.items():
            if 'deleted' in obj:
                self.execute(delete, {
                    'entity_id': self.entity_id,
                    'consent_code': c
                })
            elif c in consents:
                for field in ['description', 'expiry']:
                    if field in obj:
                        # self.execute(update.format(field=field),
                        #              {'value': obj[field]})
                        self.execute(update % {'field': field},
                                     {'value': obj[field]})
            else:
                self.execute(insert, {
                    'entity_id': self.entity_id,
                    'consent_code': c,
                    'description': obj.get('description'),
                    'expiry': obj.get('expiry')
                })
        self.__consents = dict()
