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
"""
Deletes users permanently from the database and keeps a record of their
username, name, and norwegian fnr in the legacy_users table in case they return
at a later point.

TODO: This should really be implemented as mixins for every database table this
 touches. Currently used by the bofh command user_delete_permanent at UiT, and
 contrib/no/uit/misc/delete_account.py.
"""
import datetime

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules import legacy_users


def delete(db, ac):
    """
    Delete every entry containing the entity_id of the account from the
    database

    :param db: Cerebrum.Database connection
    :param ac: Cerebrum.Account object
    :return: Information about account and account owner
    :rtype: dict
    :raise Errors.NotFoundError: if the owner id of an account is not a Person
        object
    """

    co = Factory.get('Constants')(db)
    pe = Factory.get('Person')(db)
    pe.find(ac.owner_id)
    # Build legacy info dict
    legacy_info = {'username': ac.account_name}
    try:
        legacy_info['ssn'] = pe.get_external_id(
            id_type=co.externalid_fodselsnr)[0]['external_id']
    except IndexError:
        legacy_info['ssn'] = None
    legacy_info.update(
        {
            'source': 'MANUELL',  # TODO: Should this be something else?
            'type': 'P',
            'comment': (
                    '%s - Deleted by user_delete bofh command.' %
                    datetime.datetime.today().date().strftime('%Y%m%d')),
            'name': pe.get_name(co.system_cached,
                                co.name_full),

        }
    )
    # Find email target of the account
    etarget = Factory.get('EmailTarget')(db)
    try:
        etarget.find_by_target_entity(ac.entity_id)
        target_id = etarget.entity_id
    except Errors.NotFoundError:
        target_id = None

    # Clean up bofhd_session
    stmt = """
    DELETE FROM [:table schema=cerebrum name=bofhd_session]
    WHERE account_id = :account_id
    """
    binds = {'account_id': ac.entity_id}
    db.execute(stmt, binds)

    # Clean up mail tables
    delete_mail_tables = [
        ('mailq', 'entity_id'),
        ('email_forward', 'target_id'),
        ('email_primary_address', 'target_id'),
        ('email_address', 'target_id'),
        ('email_target', 'target_id'),
    ]

    if target_id:
        binds = {'value': target_id}
        for key, value in delete_mail_tables:
            stmt = """
            DELETE FROM [:table schema=cerebrum name={table}]
            WHERE {column} = :value
            """.format(table=key, column=value)
            db.execute(stmt, binds)

    # Clean up everything else
    delete_tables = [
        ('change_log', 'change_by'),
        ('entity_name', 'entity_id'),
        ('account_home', 'account_id'),
        ('account_type', 'account_id'),
        ('account_authentication', 'account_id'),
        ('posix_user', 'account_id'),
        ('homedir', 'account_id'),
        ('group_member', 'member_id'),
        ('bofhd_session', 'account_id'),
        ('account_info', 'account_id'),
        ('spread_expire', 'entity_id'),
        ('entity_spread', 'entity_id'),
        ('entity_quarantine', 'entity_id'),
        ('entity_trait', 'entity_id'),
        ('entity_contact_info', 'entity_id'),
        ('mailq', 'entity_id'),
        ('email_target', 'target_entity_id'),
        ('entity_info', 'entity_id'),
        ('entity_contact_info', 'entity_id'),
    ]

    for key, value in delete_tables:
        binds = {'value': ac.entity_id}
        stmt = """
        DELETE FROM [:table schema=cerebrum name={table}]
        WHERE {column} = :value
        """.format(table=key, column=value)
        db.execute(stmt, binds)

    returndict = {'account_name': ac.account_name,
                  'owner_name': pe.get_name(co.system_cached, co.name_full),
                  'primary_account_name': 'None',
                  }

    # Done deleting, now writing legacy info after trying to find (new)
    # primary account for person
    lu = legacy_users.LegacyUsers(db)
    try:
        ac.clear()
        aux = pe.entity_id
        pe.clear()
        pe.find(aux)
        aux = pe.get_accounts(filter_expired=False)[0]['account_id']
        ac.find(aux)
        legacy_info['comment'] = (
                '%s - Duplicate of %s' %
                (datetime.datetime.today().date().strftime('%Y%m%d'),
                 ac.account_name))
        returndict.update({'primary_account_name': ac.account_name})
    except Exception:
        pass
    finally:
        lu.set(**legacy_info)

    return returndict
