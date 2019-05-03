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

from Cerebrum import Errors
from Cerebrum.Utils import Factory


def is_expired(db, entity_id, expired_before=None):
    """ Will check if an entity has expired or not.

    :param db: Cerebrum.database object

    :param entity_id: Will be used instead of C{self.entity_id} if
              C{entity_id is not None}. This function may therefore
              be used to check the expired status of any entity, not
              only the current one.
    :type entity_id: Integer.
    :param expired_before: Date for which the query should be done.
              If C{expire_date} of an entity is C{20070101} and
              C{expired_before > 20070101}, the entity  will be
              considered expired. Otherwise, the entity will be
              considered non-expired. If expired_before is None,
              B{current time} will be used. Note, this also includes
              hours and minutes, so immediately after midnight,
              any entity with C{expire_date} set to that day will be
              considered expired.
    :type expired_before: String (YYYYMMDD), or DateTime var.
    :return: Bolean.
        - True if expired.
        - False otherwise.

    """
    tables = []
    where = []
    tables.append("[:table schema=cerebrum name=entity_expire] ee")
    where.append("ee.entity_id=:entity_id")

    if expired_before is None:
        where.append("(ee.expire_date < [:now])")
    else:
        where.append("(ee.expire_date < :date)")

    where_str = ""
    if where:
        where_str = "WHERE " + " AND ".join(where)

    try:
        db.query_1("""
                SELECT ee.entity_id
                FROM %s %s""" %
                   (','.join(tables), where_str),
                   {'entity_id': entity_id,
                    'date': expired_before})
        return True
    except Errors.NotFoundError:
        return False


def get_expire_date(db, entity_id):
    """ Obtains the expire_date of the given entity.

    :param db: Cerebrum.database object

    :param entity_id: Will be used instead of C{self.entity_id} if
              C{entity_id is not None}. This function may
              therefore be used to get the expire date of any
              entity, not only the current one.
    :type entity_id: Integer.

    :return: DateTime.
        - Current 'expire_date'.
        - None if no date is set.

    """

    try:
        res = db.query_1(
            """
            SELECT expire_date
            FROM [:table schema=cerebrum name=entity_expire]
            WHERE entity_id=:e_id""",
            {'e_id': entity_id})
        return res  # ('expire_date')
    except Errors.TooManyRowsError:
        raise Errors.TooManyRowsError
    except Errors.NotFoundError:
        return None


def set_expire_date(db, entity_id, expire_date=None):
    """ Will set C{expire_date} on an entity.

    C{expire_date} should not be set for entitites that do not have a defined
    date on which they seize to exist.

    :param db: Cerebrum database object
    :type db: Cerebrum.DatabaseAccessor.DatabaseAccessor or similar

    :param entity_id: Cerebrum.Entity entity_id
    :type entity_id: int

    :param expire_date: If expire_date is None, [:now] is assumed.
    :type expire_date: String on format YYYYMMDD or Date/Time.

    """
    clconst = Factory.get('CLConstants')(db)

    try:
        expiry_set = db.query_1(
            """SELECT expire_date
            FROM [:table schema=cerebrum name=entity_expire]
            WHERE entity_id=:e_id""", {'e_id': entity_id})
    except Errors.TooManyRowsError:
        raise Errors.TooManyRowsError
    except Errors.NotFoundError:
        expiry_set = None

    parameters = {}
    if expiry_set is not None:
        db.execute("""
            UPDATE [:table schema=cerebrum name=entity_expire]
            SET expire_date=:exp_date
            WHERE entity_id=:e_id""",
                   {'exp_date': expire_date,
                    'e_id': entity_id})
        parameters['old_expire_date'] = str(expiry_set)
        parameters['new_expire_date'] = str(expire_date)
        db.log_change(entity_id,
                      clconst.entity_expire_mod,
                      None,
                      change_params=parameters)
    else:
        db.execute("""
            INSERT INTO
                [:table schema=cerebrum name=entity_expire]
            (entity_id, expire_date) VALUES (:e_id, :exp_date)""",
                   {'e_id': entity_id,
                    'exp_date': expire_date})
        parameters['new_expire_date'] = str(expire_date)
        db.log_change(entity_id,
                      clconst.entity_expire_add,
                      None,
                      change_params=parameters)


def delete_expire_date(db, entity_id):
    """ Removes expire_date for current entity."""
    clconst = Factory.get('Constants')(db)

    try:
        expiry_set = db.query_1(
            """SELECT expire_date
            FROM [:table schema=cerebrum name=entity_expire]
            WHERE entity_id=:e_id""", {'e_id': entity_id})
    except Errors.TooManyRowsError:
        raise Errors.TooManyRowsError
    except Errors.NotFoundError:
        expiry_set = None

    db.execute("""
        DELETE FROM [:table schema=cerebrum name=entity_expire]
        WHERE entity_id=:e_id""",
               {'e_id': entity_id})
    parameters = dict()
    parameters['old_expire_date'] = str(expiry_set)
    db.log_change(entity_id,
                  clconst.entity_expire_del,
                  None,
                  change_params=parameters)


def list_expired(db, entity_type=None, expired_before=None):
    """ Obtains a list over expired entities.

    :param db: Cerebrum.database object

    :param entity_type: The type of entities one wishes to be
              returned from the function. If C{entity_type is None},
              entities of all kinds will be listed.
    :type entity_type: Integer (C{entity_type_code}).

    :param expired_before: See L{is_expired}
    :type expired_before:

    :return: List of Tuples C{[(entity_id, DateTime),]}
        A list with C{entity_id}s and their C{expire_date}s. Note
        That the list only will include entities with expire
        dates before C{[:now]} or C{expired_before}.

    """

    tables = []
    where = []
    tables.append("[:table schema=cerebrum name=entity_expire] ee")

    if entity_type is not None:
        tables.append("[:table schema=cerebrum name=entity_info] ei")
        where.append("ee.entity_id=ei.entity_id")
        where.append("ei.entity_type=:entity_type")

    if expired_before is None:
        where.append("(ee.expire_date < [:now])")
    else:
        where.append("(ee.expire_date < :date)")

    where_str = ""
    if where:
        where_str = "WHERE " + " AND ".join(where)

    return db.query("""
                    SELECT ee.entity_id, ee.expire_date
                    FROM %s %s""" %
                    (','.join(tables), where_str),
                    {'entity_type': entity_type,
                     'date': expired_before})
