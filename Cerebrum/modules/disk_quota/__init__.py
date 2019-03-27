# -*- coding: utf-8 -*-
# Copyright 2003-2019 University of Oslo, Norway
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
Implementation of mod_disk_quota.

The disk_quota module provides disk quotas for individual homedirs, as well as
default disk quotas for disks or disk hosts.

Default disk quotas are stored as traits on host or disk entities.
Individual homedir quotas are stored in a separate table, ``disk_quota``.

Configuration
-------------
If mod_disk_quota is in use, the following cereconf-variables needs to be
configured:

CLASS_DISK
    Should be set to/include 'Cerebrum.modules.disk_quota.mixins/DiskQuotaMixin'

CLASS_CONSTANTS
    Should include Cerebrum.modules.disk_quota.constants/Constants

CLASS_CL_CONSTANTS
    Should include 'Cerebrum.modules.disk_quota.constants/CLConstants'

History
-------
This submodule used to live in Cerebrum.modules.no.{uio,uit}.{Disk,DiskQuota}.
It was moved to a separate module after:

    commit b09f87aca4a1b6ed715f863dd7cf8730465391a3
    Merge: e940e928e ddf367002
    Date:  Tue Mar 26 12:18:52 2019 +0100
"""
from Cerebrum import Account
from Cerebrum import Errors
from Cerebrum.DatabaseAccessor import DatabaseAccessor
from Cerebrum.Utils import Factory, NotSet, argument_to_sql

__version__ = '1.0'


class DiskQuota(DatabaseAccessor):
    """
    Methods for maintaining disk-quotas for accounts.

    Typical usage would be something like:

    ::

        dq = DiskQuota(db)

        # Set initial quota (or update)
        dq.set_quota(account_home.homedir_id, quota=50)

        # Set override for quota
        dq.set_quota(
            account_home.homedir_id,
            override_quota=90,
            override_expiration=mx.DateTime.now(),
            description='nice guy')

        # Remove override
        dq.clear_override(account_home.homedir_id)
    """
    def __init__(self, database):
        super(DiskQuota, self).__init__(database)
        self.const = Factory.get('Constants')(database)
        self.clconst = Factory.get('CLConstants')(database)

    def _get_account_id(self, homedir_id):
        ah = Account.Account(self._db)
        row = ah.get_homedir(homedir_id)
        return row['account_id']

    def __insert_disk_quota(self, homedir_id, values):
        binds = {}
        binds.update(values)
        binds.update({'homedir_id': int(homedir_id)})
        query = """
            INSERT INTO [:table schema=cerebrum name=disk_quota]
            ({cols}) VALUES ({params})
        """.format(cols=', '.join(sorted(binds)),
                   params=', '.join(':' + k for k in sorted(binds)))
        self._db.execute(query, binds)

    def __update_disk_quota(self, homedir_id, values):
        binds = {}
        binds.update(values)
        binds.update({'homedir_id': int(homedir_id)})
        query = """
            UPDATE [:table schema=cerebrum name=disk_quota]
            SET {assign}
            WHERE homedir_id=:homedir_id
        """.format(assign=', '.join(k + '=:' + k for k in sorted(values)))
        self._db.execute(query, binds)

    def set_quota(
            self,
            homedir_id,
            quota=NotSet,
            override_quota=NotSet,
            override_expiration=NotSet,
            description=NotSet):
        """
        Insert or update disk_quota for homedir_id.

        Will only affect the columns used as keyword arguments.
        """
        try:
            old_values = self.get_quota(homedir_id)
            is_new = False
        except Errors.NotFoundError:
            old_values = {}
            is_new = True

        new_values = {}

        def update_param(k, v):
            if v is NotSet or (k in old_values and v == old_values[k]):
                return
            new_values[k] = v

        update_param('quota', quota)
        update_param('override_quota', override_quota)
        update_param('override_expiration', override_expiration)
        update_param('description', description)

        if not new_values:
            return

        if is_new:
            self.__insert_disk_quota(homedir_id, new_values)
        else:
            self.__update_disk_quota(homedir_id, new_values)

        # Update change_params
        # TODO: We should really changelog the old_values...
        change_params = dict(new_values)
        change_params['homedir_id'] = homedir_id
        if 'override_expiration' in change_params:
            change_params.update({
                'override_expiration':
                    override_expiration.strftime('%Y-%m-%d'),
             })
        self._db.log_change(
            self._get_account_id(homedir_id),
            self.clconst.disk_quota_set,
            None,
            change_params=change_params)

    def clear_override(self, homedir_id):
        """Convenience method for clearing override settings"""
        self.set_quota(
            homedir_id,
            override_quota=None,
            override_expiration=None,
            description=None,
        )

    def clear(self, homedir_id):
        """Remove the disk_quota entry from the table"""
        try:
            self.get_quota(homedir_id)
            exists = True
        except Errors.NotFoundError:
            exists = False

        if not exists:
            return

        change_entity = self._get_account_id(homedir_id)

        binds = {'homedir_id': int(homedir_id)}
        query = """
            DELETE FROM [:table schema=cerebrum name=disk_quota]
            WHERE homedir_id=:homedir_id
        """
        self._db.execute(query, binds)

        self._db.log_change(
            change_entity,
            self.clconst.disk_quota_clear,
            None,
            change_params=binds)

    def get_quota(self, homedir_id):
        """Return quota information for a given homedir"""
        binds = {'homedir_id': int(homedir_id)}
        query = """
            SELECT * FROM [:table schema=cerebrum name=disk_quota]
            WHERE homedir_id=:homedir_id
        """
        return self._db.query_1(query, binds)

    def list_quotas(self, spread=None, disk_id=None, all_users=False):
        """
        List quota and homedir information for all users that has quota.
        """
        binds = {}
        where = []

        where.append(
            argument_to_sql(
                self.const.account_namespace, 'en.value_domain', binds, int))

        if spread:
            where.append(argument_to_sql(spread, 'ah.spread', binds, int))

        if disk_id:
            where.append(argument_to_sql(disk_id, 'di.disk_id', binds, int))

        query = """
        SELECT
            dq.homedir_id, ah.account_id, hi.home, en.entity_name, di.path,
            dq.quota, dq.override_quota, dq.override_expiration, ah.spread
        FROM
            [:table schema=cerebrum name=disk_info] di,
            [:table schema=cerebrum name=account_home] ah,
            [:table schema=cerebrum name=account_info] ai,
            [:table schema=cerebrum name=entity_name] en,
            [:table schema=cerebrum name=homedir] hi
        {if_left} JOIN
            [:table schema=cerebrum name=disk_quota] dq
        ON
            dq.homedir_id = hi.homedir_id
        WHERE
            hi.disk_id=di.disk_id AND
            hi.homedir_id=ah.homedir_id AND
            ah.account_id=en.entity_id AND
            ai.account_id=en.entity_id AND
            (ai.expire_date IS NULL OR
             ai.expire_date > [:now]) AND
            {where}
        """.format(
             if_left=('LEFT' if all_users else ''),
             where=' AND '.join(where),
        )

        return self._db.query(query, binds)
