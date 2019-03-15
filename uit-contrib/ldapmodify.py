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

# Copied from Leetah

import cerebrum_path
import cereconf
import os
import sys
import time

from Cerebrum.Utils import Factory
logger_name = cereconf.DEFAULT_LOGGER_TARGET

def main():
    logger = Factory.get_logger(logger_name)
    date = time.localtime()
    year = date[0]
    month = date[1]
    day = date[2]
    ldap_server = cereconf.LDAP['server']
    user = cereconf.LDAP['user'] 
    password = cereconf.LDAP['password']
    ldap_dump_dir = cereconf.DUMPDIR + "/ldap/"
    ldap_temp_file = "temp_uit_ldif"
    ldap_diff = "uit_ldif"

    ret = 0
    ret = os.system("/usr/bin/ldapmodify -x -H ldaps://%s -D \"cn=%s,dc=uit,dc=no\" -w %s -f %s/uit_diff_%02d%02d%02d" % (ldap_server,user,password,ldap_dump_dir,year,month,day))
    if(ret != 0):
        logger.error("unable to update ldap server")
        sys.exit(1)
    ret = os.system("mv %s/%s %s/%s" % (ldap_dump_dir,ldap_temp_file,ldap_dump_dir,ldap_diff))
         

def usage():
    print """
    This script does an ldap modify towards the ldap server and then updates the local ldif
    file to reflect the status on the server
    """

if __name__=='__main__':
    main()

# arch-tag: b68a0396-b426-11da-9abf-db31addc6818
