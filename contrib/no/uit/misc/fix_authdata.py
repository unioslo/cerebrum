#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2004 University of Tromsoe, Norway
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





import cerebrum_path
import cereconf
from Cerebrum.Utils import Factory

class process:
    
    def __init__(self):
        db = Factory.get("Database")()
        self.fix_auths(db)
        
    def fix_auths(self,db):
        query = "select account_id,method,auth_data from account_authentication where auth_data like '%%\n';"
        #print "query = %s" % query
        db_row = db.query(query)
        for row in db_row:
            print "Processing *********************"
            print "Acc_id: %d , Method=%d, Auth: %s" % ( row['account_id'], row['method'],row['auth_data'])
            
            new_auth = row['auth_data'].rstrip()

            update_query = "update  account_authentication set auth_data='%s' where account_id=%d and method=%d;" % (new_auth,row['account_id'],row['method'])
            print "query = %s" % update_query
            db_rowx = db.query(update_query)
        db.commit()
            
            
def main():
    
    object = process()
    
    
def usage():
    print """ No parameters are given to this program.
    The program fixes an error in the authentication_data table where an auth_method
    has a trailing \n in its auth_data.
    This causes the LDAP exports to apply an encoding to the userPassord field which
    is not desired."""
    
if  __name__=='__main__':

