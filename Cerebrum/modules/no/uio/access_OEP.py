# -*- coding: utf-8 -*-
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


    def __init__(self, db, db_charset=None):
        self.db = db
        self._to_charset = "iso-8859-1"
        self._from_charset = db_charset and db_charset or self._to_charset
    # end __init__


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
        
        return self.db.query(query, fetchall = fetchall)
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
        
        return self.db.query(query, fetchall = fetchall)
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
        
        return self.db.query(query, fetchall = fetchall)
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
        
        return self.db.query(query, fetchall = fetchall)
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
        
        return self.db.query(query, fetchall = fetchall)
    # end list_useradmin_users        
# end OEP
