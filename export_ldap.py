#!/usr/bin/python
# -*- coding: iso-8859-1 -*-

import cerebrum_path
import cereconf
import string
import getopt
import sys
import os
import time

from Cerebrum.Utils import Factory



def ldap_export():

    #logger = Factory.get_logger("console")   
    logger = Factory.get_logger("cronjob")
    global_ret = 0
    date = time.localtime()
    year = date[0]
    month = date[1]
    day = date[2]
    script_dir = os.path.join(cereconf.CB_PREFIX,'share','cerebrum','contrib')
    
    #logger.info("Starting export of ldap data")


    # 1. create the posix_user_ldif
    script = os.path.join(script_dir,'generate_posix_ldif.py')
    script_arg = "-U fronter@uit,AD_account,NIS_user@uit,SUT@uit,fd@uit -u /cerebrum/var/dumps/ldap/users_ldif"
    script_cmd = "%s %s %s" % ('python', script, script_arg)
    #logger.debug("Running %s" % script_cmd)
    ret = os.system(script_cmd)
    global_ret +=ret
    #logger.info("   generate_posix_ldif.py: %s" % ret)

    # 2 create the ou_ldif
    script = os.path.join(script_dir,'generate_org_ldif.py')
    script_arg = "-o /cerebrum/var/dumps/ldap/ou_ldif"
    script_cmd = "%s %s %s" % ('python', script, script_arg)
    #logger.debug("Running %s" % script_cmd)
    ret = os.system(script_cmd)
    global_ret +=ret
    #logger.info("   generate_org_ldif.py %s" %ret)

    # 3 concatenate the two files into a third called temp_uit_ldif
    my_dump = os.path.join(cereconf.DUMPDIR , "ldap")
    
    script_cmd = "/bin/cat %s/ou_ldif %s/users_ldif > %s/temp_uit_ldif" %(my_dump,my_dump,my_dump)
    #logger.debug("Running %s" % script_cmd)
    ret = os.system(script_cmd)
    global_ret +=ret
    #logger.info("   cat ou_ldif users_ldif > temp_uit_ldif %s" %ret)

    # 4.create a new ldif file based on the difference between the old and new data from cerebrum
    # 
    script = os.path.join(script_dir,'no','uit','ldif-diff.pl')
    script_arg = "/cerebrum/var/dumps/ldap/uit_ldif /cerebrum/var/dumps/ldap/temp_uit_ldif > /cerebrum/var/dumps/ldap/uit_diff_%02d%02d%02d" % (year,month,day)
    script_cmd = "%s %s %s" % ('perl', script, script_arg)
    #logger.debug("Running %s" % script_cmd)
    ret = os.system(script_cmd) 
    global_ret +=ret
    #logger.info("   ldif-diff.pl %s" % ret)

    #logger.debug("Finished running ldap export: global ret=%s " % global_ret)
    return global_ret




def main():
    try:
        opts,args = getopt.getopt(sys.argv[1:],'h',['help'])
    except getopt.GetoptError:
        usage()


    help = 0
    for opt,val in opts:
        if opt in('-h','--help'):
            help = 1


    if (help == 1):
        usage()
        sys.exit(0)

    retval = ldap_export()
    sys.exit(retval)
    
    
        
def usage():
    print """This scripts exports creates a ldif file for the LDAP/AT service

    Usage: [options]
    -h | --help : this text """


if __name__ == '__main__':
    main()
