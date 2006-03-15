#!/usr/bin/python
# -*- coding: iso-8859-1 -*-

import cerebrum_path
import cereconf
import os
import sys
import time

from Cerebrum.Utils import Factory

def main():
    logger = Factory.get_logger("console")
    date = time.localtime()
    year = date[0]
    month = date[1]
    day = date[2]
    ldap_server ="ldap.uit.no"
    user = "Manager"
    password = "Fl4pDap"
    ldap_dump_dir ="/cerebrum/var/dumps/ldap/"
    ldap_temp_file = "temp_uit_ldif"
    ldap_diff = "uit_ldif"

    ret = 0;
        
    ret = os.system("/usr/bin/ldapmodify -x -H ldap://%s -D \"cn=%s,dc=uit,dc=no\" -w %s -v -f %s/uit_diff_%02d%02d%02d" % (ldap_server,user,password,ldap_dump_dir,year,month,day))
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
