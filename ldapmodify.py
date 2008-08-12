#!/usr/bin/python
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

import os
import sys

import cerebrum_path
import cereconf
from Cerebrum.Utils import Factory
logger = Factory.get_logger("cronjob")

def main():
    ldap_server = cereconf.LDAP['server']
    user = cereconf.LDAP['user'] 
    password = cereconf.LDAP['password']
    
    ldif_file=os.path.join(cereconf.DUMPDIR,"ldap","uit_ldif")
    temp_ldif_file=os.path.join(cereconf.DUMPDIR,"ldap","temp_uit_ldif")
    ldif_diff_file=os.path.join(cereconf.DUMPDIR,"ldap","uit_diff")

    ret = 0
    script="/usr/bin/ldapmodify"
    script_args="-x -H ldap://%s -D \"cn=%s,dc=uit,dc=no\" -w %s -v -f %s" % \
        (ldap_server,user,password,ldif_diff_file)
    script_cmd="%s %s" % (script, script_args)
    #update ldap 
    logger.debug("Running %s" % script_cmd)
    ret = os.system(script_cmd)
    if(ret != 0):
        logger.error("unable to update ldap server,  ret=%d" % (ret))
        sys.exit(1)
    # command successful, now move temp file to prod file
    script_cmd="mv %s %s" % (temp_ldif_file,ldif_file)
    logger.debug("Running %s" % script_cmd)
    ret = os.system(script_cmd)
    if(ret != 0):
        logger.error("ldap updated, but move of temp file failed ret=%d"%(ret))
        sys.exit(1)


def usage():
    print """
    This script does an ldap modify towards the ldap server and then updates the
    local ldif file to reflect the status on the server
    """

if __name__=='__main__':
    main()
