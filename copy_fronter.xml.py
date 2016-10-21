#! /bin/env python

import os
import time
import sys
#import ftplib
#import scp
import cerebrum_path
import cereconf

from Cerebrum.Utils import Factory, read_password
logger = Factory.get_logger("cronjob")

def main():
    # filenames
    path = os.path.join(cereconf.DUMPDIR,"Fronter")
    filename="uit_import%s.xml" % time.strftime("%Y%m%d")
    scp_file=os.path.join(path,filename)
    server_path="/export/"
    export_file=os.path.join(path,"test.xml")
    logger.info("Export file %s, scp file %s" % (export_file, scp_file))
    ret = os.system("mv %s %s" % (export_file, scp_file))
    if ret != 0:
        logger.error("ERROR: unable to execute system command mv in copy_fronter_xml.py.\n")
        sys.exit(-1)

    try:
        scp_location=cereconf.LMS_SCP_LOCATION
        scp_username=cereconf.LMS_SCP_USERNAME
    except AttributeError,m:
        logger.critical("Cereconf var not found. Check cereconf. Error: %s" % m)
        sys.exit(-1)
    except Exception,m:
        logger.critical("Unexpected error: %s" % m)
        sys.exit(-1)
    #scp_password=read_password(ftp_username, ftp_location)
    file_handle = open(scp_file)
    # upload the file
    try:
        os.system("scp "+scp_file+" fronter@stellanova.uit.no:~"+server_path+filename)
    except errors:
        logger.critical("unable to upload scp file: %s" % m)
        sys.exit(-1)

if __name__=='__main__':
    main()
