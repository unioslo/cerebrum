#!/usr/bin/python
# -*- coding: iso-8859-1 -*-

import getopt
import sys
import os
import mx.DateTime

import cerebrum_path
import cereconf
from Cerebrum.Utils import Factory
logger = Factory.get_logger("cronjob")

def ldap_export():
    global_ret = 0
    script_dir = os.path.join(cereconf.CB_PREFIX,'share','cerebrum','contrib')
    tstamp=mx.DateTime.now().Format('%Y%m%d-%H%M%S')
    ou_ldif_file=os.path.join(cereconf.DUMPDIR,"ldap","ou_ldif")
    users_ldif_file=os.path.join(cereconf.DUMPDIR,"ldap","users_ldif")
    fake_ldap_users_file=os.path.join(cereconf.CB_PREFIX,"var","source","ldap","fake_ldap_users.ldif")
    ldif_file=os.path.join(cereconf.DUMPDIR,"ldap","uit_ldif")
    temp_ldif_file=os.path.join(cereconf.DUMPDIR,"ldap","temp_uit_ldif")
    ldif_diff_file=os.path.join(cereconf.DUMPDIR,"ldap","uit_diff")
    ldif_diff_backup_file=os.path.join(cereconf.DUMPDIR,"ldap","uit_diff_%s") % tstamp
    
    logger.info("Starting export of ldap data")
    # 1. create the posix_user_ldif
    script = os.path.join(script_dir,'generate_posix_ldif.py')
    script_arg = "-U ldap@uit -u "+users_ldif_file
    script_cmd = "%s %s %s" % ('python', script, script_arg)
    logger.debug("Running %s" % script_cmd)
    ret = os.system(script_cmd)
    global_ret +=ret
    logger.info("   generate_posix_ldif.py: %s" % ret)

    # 2 create the ou_ldif
    script = os.path.join(script_dir,'generate_org_ldif.py')
    script_arg = "-o "+ou_ldif_file
    script_cmd = "%s %s %s" % ('python', script, script_arg)
    logger.debug("Running %s" % script_cmd)
    ret = os.system(script_cmd)
    global_ret +=ret
    logger.info("   generate_org_ldif.py %s" %ret)

    # 3 concatenate the ldif files into a new called temp_uit_ldif
    script_cmd="/bin/cat %s %s %s > %s" % (ou_ldif_file,users_ldif_file,
                                           fake_ldap_users_file,temp_ldif_file)
    
    logger.debug("Running %s" % script_cmd)
    ret = os.system(script_cmd)
    global_ret +=ret
    logger.info("   cat ou_ldif users_ldif > temp_uit_ldif %s" %ret)

    # 4.create a new ldif file based on the difference between the old and new 
    # data from cerebrum
    script = os.path.join(script_dir,'no','uit','ldif-diff.pl')
    script_arg = "%s %s > %s" % (ldif_file, temp_ldif_file, ldif_diff_file)
    script_cmd = "%s %s %s" % ('perl', script, script_arg)
    logger.debug("Running %s" % script_cmd)
    ret = os.system(script_cmd) 
    global_ret +=ret
    logger.info("   ldif-diff.pl %s" % ret)

    # 5. make a copy of the ldif-diff file for debugging purposes
    if os.path.getsize(ldif_diff_file)==0:
        script_cmd = "cp  %s %s" % (ldif_diff_file, ldif_diff_backup_file)
        logger.debug("Running %s" % script_cmd)
        ret=os.system(script_cmd)
        global_ret +=ret
        logger.info("   ldif-diff backup copy %s" % ret)
    else:
        logger.info("ldif-diff 0 bytes, no backup needed")

    logger.debug("Finished running ldap export: global ret=%s " % global_ret)
    return global_ret

def main():
    try:
        opts,args = getopt.getopt(sys.argv[1:],'h',['help'])
    except getopt.GetoptError,m:
        usage(1,m)
    
    for opt,val in opts:
        if opt in('-h','--help'):
            usage()

    retval = ldap_export()
    if (retval != 0):
        retval=1  
    sys.exit(retval)
    
        
def usage(exit_code=0,msg=""):
    if msg: print msg
    print """
    This scripts creates a set of ldif files.
    These ldif files are used to build a new ldif-diff wfile, and this diff can
    be applied to the LDAP/AT service

    Usage: [options]
    -h | --help : this text
    """
    sys.exit(exit_code)
    
if __name__ == '__main__':
    main()
