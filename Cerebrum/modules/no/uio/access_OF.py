# -*- coding: iso-8859-1 -*-
# Copyright 2002, 2003 University of Oslo, Norway
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
This module provides an interface to the OFPROD database.
"""





class OF(object):
    """
    This class contains methods for accessing the OFPROD database.
    """


    def __init__(self, db):
        self.db = db
    # end __init__



    def list_dbfg_usernames(self, fetchall = False):
        """
        Get all usernames and return them as a sequence of db_rows.
        """

        query = """
                SELECT
                  user_name as username
                FROM
                  applsys.fnd_user
                """
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

# arch-tag: 80106781-3a0a-4f30-8917-ca6c3075e69f
