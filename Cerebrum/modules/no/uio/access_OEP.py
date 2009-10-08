# -*- coding: iso-8859-1 -*-
# Copyright 2006 University of Oslo, Norway
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
This module provides an interface to the BasWare database.
"""





class OEP(object):
    """
    This class contains methods for accessing the BasWare database.
    """


    def __init__(self, db):
        self.db = db
        self._from_charset = "utf-16-be"
        self._to_charset = "iso-8859-1"
    # end __init__


    def _recode_row(self, db_row):
        """Enforce certain encoding on db_row.

        Make sure that string keys are in the specific encoding in db_row.

        NB! db_row's content is modified destructively.
        """

        for key, value in db_row.items():
            if isinstance(value, unicode):
                db_row[key] = value.encode(self._to_charset)
            elif (isinstance(value, str) and
                  self._from_charset != self._to_charset):
                db_row[key] = unicode(value,
                                      self._from_charset).encode(self._to_charset)
        return db_row
    # end _recode_row


    def list_dbfg_users(self, fetchall = False):
        """
        Get all users and return them as a sequence of db_rows.
        """

        query = """
                SELECT igu.user_network_name AS username
                FROM basware.ip_group_user igu,
                     basware.eflow_users eu
                WHERE igu.group_name = 'BasWareBrukere' AND
                      upper(igu.DOMAIN) = 'UIO' AND
                      igu.user_network_name = eu.user_network_name AND
                      eu.active = 1
                """
        
        return [self._recode_row(x) for x in self.db.query(query, fetchall = fetchall)]
    # end list_dbfg_usernames



    def list_dbfg_masters(self, fetchall = False):
        """
        Get all privileged users and return them as a sequence of db_rows.
        """

        query = """
                SELECT igu.user_network_name AS username
                FROM basware.ip_group_user igu,
                     basware.eflow_users eu
                WHERE igu.group_name = 'Masterbrukere' AND
                      upper(igu.DOMAIN) = 'UIO' AND
                      igu.user_network_name = eu.user_network_name AND
                      eu.active = 1
                """
        
        return [self._recode_row(x) for x in self.db.query(query, fetchall = fetchall)]
    # end list_applsys_users



    def list_dbfg_monitor(self, fetchall = False):
        """
        Get all privileged users and return them as a sequence of db_rows.
        """

        query = """
                SELECT igu.user_network_name AS username
                FROM basware.ip_group_user igu,
                     basware.eflow_users eu
                WHERE igu.group_name = 'Monitorbrukere' AND
                      upper(igu.DOMAIN) = 'UIO' AND
                      igu.user_network_name = eu.user_network_name AND
                      eu.active = 1
                """
        
        return [self._recode_row(x) for x in self.db.query(query, fetchall = fetchall)]
    # end list_monitor_users



    def list_dbfg_readsoft(self, fetchall = False):
        """
        Get all privileged users and return them as a sequence of db_rows.
        """

        query = """
                SELECT igu.user_network_name AS username
                FROM basware.ip_group_user igu,
                     basware.eflow_users eu
                WHERE igu.group_name = 'Readsoftbrukere' AND
                      upper(igu.DOMAIN) = 'UIO' AND
                      igu.user_network_name = eu.user_network_name AND
                      eu.active = 1
                """
        
        return [self._recode_row(x) for x in self.db.query(query, fetchall = fetchall)]
    # end list_readsoft_users



    def list_dbfg_useradmin(self, fetchall = False):
        """
        Get all privileged users and return them as a sequence of db_rows.
        """

        query = """
                SELECT igu.user_network_name AS username
                FROM basware.ip_group_user igu,
                     basware.eflow_users eu
                WHERE igu.group_name = 'UserAdminbrukere' AND
                      upper(igu.DOMAIN) = 'UIO' AND
                      igu.user_network_name = eu.user_network_name AND
                      eu.active = 1
                """
        
        return [self._recode_row(x) for x in self.db.query(query, fetchall = fetchall)]
    # end list_useradmin_users        
# end OEP
