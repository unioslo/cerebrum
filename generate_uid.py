#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
# Copyright 2002, 2003 University of Tromsø, Norway
import getopt
import sys
import cerebrum_path
import cereconf
from Cerebrum.Utils import Factory
from Cerebrum import Errors
from Cerebrum.modules import PosixUser

def main():
    db = Factory.get('Database')()
    posix_user = PosixUser.PosixUser(db)
    logger = Factory.get_logger("cronjob")
    try:
        opts,args = getopt.getopt(sys.argv[1:],'u:',['uid_file='])
    except getopt.GetoptError:
        usage()

    uid_file =0
    for opt,val in opts:
        if opt in ('-u','--uid_file'):
            uid_file = val

    if(uid_file !=0):    
        file_handle = open(uid_file,"w")
        posix_user_list = posix_user.list_posix_users()
        for user in posix_user_list:
            posix_user.clear()
            posix_user.find(user[0])
            file_handle.writelines("%s:%s\n" % (posix_user.account_name,user[1]))
        file_handle.close()
    else:
        usage()
        

def usage():
    print """Usage: python generate_sut_uid_list -u <filename>
    -u  | --uid_file : filename to store the uid's in
    """

if __name__=='__main__':
    main()
