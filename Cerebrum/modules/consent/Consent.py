# -*- coding: utf-8 -*-
#
# Copyright 2015-2023 University of Oslo, Norway
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
Mixin for letting persons approve or deny a proposition.

This module stores various opt-in (consents) or opt-out (reservation) settings
for a given person.

Typical settings are:

    * For legal matters, an opt-in may be required before exporting personal
      data to some external system.
    * For security reasons, my account should not be used for some feature

Usage
======
1. Add ``"Cerebrum.modules.consent.ConsentConstants/Constants"`` to
   ``cereconf.CLASS_CONSTANTS``

2. For each consent in question, add a constant with type
   EntityConsentCode::

        class MyConstants(Constants):
            myconsentcode = Constants.EntityConsentCode(
                'myconsent',
                description="My consent",
                consent_type=Constants.consent_opt_in,
                entity_type=Constants.entity_person,
            )

3. Add ``"Cerebrum.modules.consent.Consent/EntityConsentMixin"`` to
   ``cereconf.CLASS_ENTITY`` (or subclasses thereof)

4. Use the `API`_.

Here, consent type is either consent_opt_in or consent_opt_out. When a consent
is set, a check against entity_type is done.


API
====
The API is contained in EntityConsentMixin:

Whenever the user agrees to some proposition, the corresponding consent code
is used to set a consent::

    person.find(xxx)
    person.set_consent(co.myconsentcode, "Given consent in Brukerinfo", None)

``set_consent`` can also be used to update consents, or only one of the two
fields. A consent can also be removed with::

    person.remove_consent(co.myconsentcode)

Neither set_consent() nor remove_consent() has any effect until write_db()
is called.

Changelog
==========
Three changelog events exist: consent_approve, consent_decline, and
consent_remove.  The first two corresponds to new or updated consents with
opt-in or opt-out respectively. The last is sent when consent is removed.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    # TODO: unicode_literals,
)
import six

from Cerebrum.Entity import Entity
from Cerebrum.Errors import PolicyException
from Cerebrum.Utils import NotSet, argument_to_sql

from .ConsentConstants import (
    CLConstants,
    Constants,
    _ConsentTypeCode,
    _EntityConsentCode,
)

__version__ = "1.1"


def assert_consent_code(consent_code):
    """ Turn an int or string value into a consent code object
    :return _EntityConsentCode:
    """
    if isinstance(consent_code, _EntityConsentCode):
        return consent_code
    return _EntityConsentCode(consent_code)


def assert_consent_type(consent_type_code):
    if isinstance(consent_type_code, _ConsentTypeCode):
        return consent_type_code
    return _ConsentTypeCode(consent_type_code)


def get_change_type(consent_code):
    """ Figure out the ChangeType of a EntityConsentCode. """
    if consent_code.consent_type == Constants.consent_opt_in:
        change = CLConstants.consent_approve
    else:
        change = CLConstants.consent_decline
    return change


def sql_insert_consent(db, entity_id, consent_code,
                       description=None, expire=None):
    """ Insert a consent row in the database.

    :param db: a database-like connection or cursor
    :param int entity_id: The entity_id to add ocnsent to
    :param consent_code: The _EntityConsentCode to set
    :param description: A description for the consent
    :param expire: An expire datetime for the consent
    """
    if not isinstance(consent_code, _EntityConsentCode):
        raise ValueError("consent_code must be EntityConsentCode")
    db.execute(
        """
          INSERT INTO [:table schema=cerebrum name=entity_consent]
            (entity_id, consent_code, description)
          VALUES
            (:entity_id, :consent_code, :description)
        """,
        {
            'entity_id': int(entity_id),
            'consent_code': int(consent_code),
            'description': description,
        })

    if hasattr(db, 'log_change'):
        db.log_change(
            subject_entity=entity_id,
            change_type_id=get_change_type(consent_code),
            destination_entity=None,
            change_params={
                'description': description,
                'consent_code': int(consent_code),
                'consent_string': six.text_type(consent_code),
            },
        )


def sql_update_consent(db, entity_id, consent_code,
                       description=NotSet, expire=NotSet):
    """ Update a consent row in the database.

    :param db: a database-like connection or cursor
    :param int entity_id: The entity_id to add ocnsent to
    :param consent_code: The _EntityConsentCode to set
    :param description: A description for the consent
    :param expire: An expire datetime for the consent
    """
    if not isinstance(consent_code, _EntityConsentCode):
        raise ValueError("consent_code must be EntityConsentCode")
    update = """
      UPDATE [:table schema=cerebrum name=entity_consent]
      SET {changes}
      WHERE entity_id=:entity_id AND consent_code=:consent_code
    """
    binds = {
        'entity_id': entity_id,
        'consent_code': consent_code,
    }
    if description is NotSet:
        return

    fields = {'description': description}
    changes = ', '.join('{field}=:{field}'.format(field=field)
                        for field in fields)
    binds.update(fields)
    db.execute(update.format(changes=changes), binds)

    if hasattr(db, 'log_change'):
        db.log_change(
            subject_entity=entity_id,
            change_type_id=get_change_type(consent_code),
            destination_entity=None,
            change_params={
                'description': description,
                'consent_code': int(consent_code),
                'consent_string': six.text_type(consent_code),
            },
        )
    return True


def sql_delete_consent(db, entity_id, consent_code):
    """ Update a consent row in the database.

    :param db: a database-like connection or cursor
    :param int entity_id: The entity_id to add ocnsent to
    :param consent_code: The _EntityConsentCode to set
    """
    if not isinstance(consent_code, _EntityConsentCode):
        raise ValueError("consent_code must be EntityConsentCode")
    db.execute(
        """
          DELETE FROM [:table schema=cerebrum name=entity_consent]
          WHERE entity_id=:entity_id AND consent_code=:consent_code
        """,
        {
            'entity_id': int(entity_id),
            'consent_code': int(consent_code),
        })

    if hasattr(db, 'log_change'):
        db.log_change(
            subject_entity=entity_id,
            change_type_id=CLConstants.consent_remove,
            destination_entity=None,
            change_params={
                'consent_code': int(consent_code),
                'consent_string': six.text_type(consent_code),
            },
        )


def sql_select_consents(db,
                        consent_code=None,
                        consent_type=None,
                        entity_id=None,
                        entity_type=None,
                        fetchall=True):
    """ Get consents from the database. """
    filters = []
    args = {}
    query = """
      SELECT entity_consent.*
      FROM [:table schema=cerebrum name=entity_consent]
      INNER JOIN [:table schema=cerebrum name=entity_consent_code]
      ON consent_code = code
    """
    for value, field in (
            (consent_code, 'consent_code'),
            (consent_type, 'consent_type'),
            (entity_id, 'entity_id'),
            (entity_type, 'entity_type')):
        if value is not None:
            filters.append(argument_to_sql(value, field, args, int))

    if filters:
        query += " WHERE " + " AND ".join(filters)
    return db.query(query, args, fetchall=fetchall)


class EntityConsentMixin(Entity):
    """ Mixin for approve/deny propositions.  """

    def __init__(self, *rest, **kw):
        super(EntityConsentMixin, self).__init__(*rest, **kw)
        self.__consents = {}

    def clear(self):
        """Clear this object"""
        super(EntityConsentMixin, self).clear()
        self.__consents = {}

    def list_consents(self, **kwargs):
        """
        List all entities filtered by argument.

        See :func:`.sql_select_consents` for more info.
        """
        # No longer supported:
        kwargs.pop('filter_expired', None)
        return sql_select_consents(self._db, **kwargs)

    def get_consent_status(self, consent_code):
        """Returns a row for self and consent_code, or None.

        :type consent_code: Constants.EntityConsent
        :param consent_code: The corresponding consent code.

        :returns: Db row or None
        """
        ret = self.list_consents(consent_code=consent_code,
                                 entity_id=int(self.entity_id))
        if ret:
            return ret[0]

    def set_consent(self, consent_code, description=NotSet):
        """Set/update consent status for self and this consent_code.

        For description param, NotSet yields null in new consents,
        and no change in existing database entries. (Be careful in the event
        of expired consents.) None will always beget a null.

        :type consent_code: Constants.EntityConsent
        :param consent_code: Corresponding consent

        :type description: string, NotSet or None (=Null)
        :param description: Description.
        """
        consent_code = assert_consent_code(consent_code)
        if consent_code.entity_type != self.entity_type:
            raise PolicyException(
                "Consent %(type)s not compatible with %(etype)s"
                % {'type': consent_code, 'etype': self.entity_type})
        code = int(consent_code)
        if code not in self.__consents:
            self.__consents[code] = {'consent_code': consent_code}
        elif 'deleted' in self.__consents[code]:
            del self.__consents[code]['deleted']
        if description is not NotSet:
            self.__consents[code]['description'] = description

    def remove_consent(self, consent_code):
        """Removes a consent of given type"""
        code = int(consent_code)
        if code in self.__consents:
            self.__consents[code]['deleted'] = True
        else:
            self.__consents[code] = {'deleted': True}

    def write_db(self):
        """Write changes to database."""
        super(EntityConsentMixin, self).write_db()
        if not self.__consents:
            return
        consents = [int(x['consent_code'])
                    for x in self.list_consents(entity_id=self.entity_id,
                                                filter_expired=False)]
        for c, obj in self.__consents.items():
            code = assert_consent_code(c)
            if 'deleted' in obj:
                sql_delete_consent(self._db, int(self.entity_id), code)
            elif c in consents:
                kwargs = {}
                if 'description' in obj:
                    kwargs['description'] = obj['description']
                sql_update_consent(self._db, self.entity_id, code, **kwargs)
            else:
                sql_insert_consent(self._db, self.entity_id, code,
                                   description=obj.get('description'))
        self.__consents = dict()
