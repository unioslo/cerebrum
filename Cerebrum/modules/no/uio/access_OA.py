# -*- coding: utf-8 -*-
# Copyright 2002, 2003, 2012 University of Oslo, Norway
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
This module provides an interface to the OAPRD database
"""





class OA(object):
    """
    This class contains methods for accessing the OAPRD database.
    """

    def __init__(self, db):
        self.db = db
    # end __init__

    def list_dbfg_usernames(self, fetchall = False):
        """Get all usernames and return them as a sequence of db_rows."""

        query = """
            SELECT
                LOWER(user_name) as username
            FROM
                applsys.fnd_user
            WHERE
                NVL(end_date, SYSDATE) >= SYSDATE AND
                (email_address IS NULL OR
                 LOWER(email_address) LIKE '%@%.uio.no' OR
                 LOWER(email_address) = 'uio')"""
        return self.db.query(query, fetchall = fetchall)
    # end list_usernames



    def list_applsys_usernames(self, fetchall = False):
        """
        """

        query = """
                SELECT 
                  lower(user_name) as username
                FROM
                  applsys.fnd_user
                WHERE
                  (lower(email_address) LIKE '%.uio.%' OR
                   lower(email_address) = 'uio') AND
                  NVL(end_date, SYSDATE) >= SYSDATE
                """

        return self.db.query(query, fetchall = fetchall)
    # end list_applsys_users
# end OF

