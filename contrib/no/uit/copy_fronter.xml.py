#! /bin/env python

import os
import time
import sys
import ftplib
import cerebrum_path
import cereconf

from Cerebrum.Utils import Factory, read_password
logger = Factory.get_logger("cronjob")

def main():
    # filenames
    path = os.path.join(cereconf.DUMPDIR,"Fronter")
    filename="uit_import%s.xml" % time.strftime("%Y%m%d")
    ftp_file=os.path.join(path,filename)
    export_file=os.path.join(path,"test.xml")
    logger.info("Export file %s, ftp file %s" % (export_file, ftp_file))
    
    ret = os.system("mv %s %s" % (export_file, ftp_file))
    if ret != 0:
        logger.error("ERROR: unable to execute system command mv in copy_fronter_xml.py.\n")
        sys.exit(-1)

    try:
        ftp_location=cereconf.LMS_FTP_LOCATION
        ftp_username=cereconf.LMS_FTP_USERNAME
    except AttributeError,m:
        logger.critical("Cereconf var not found. Check cereconf. Error: %s" % m)
        sys.exit(-1)
    except Exception,m:
        logger.critical("Unexpected error: %s" % m)
        sys.exit(-1)
    ftp_password=read_password(ftp_username, ftp_location)
    file_handle = open(ftp_file)
    # upload the file
    try:
        ftp = ftplib.FTP(ftp_location,ftp_username,ftp_password)
        ftp.storlines("STOR %s" % filename,file_handle)        
    except ftplib.all_errors:
        logger.critical("unable to upload ftp file: %s" % ftplib.all_errors)
        sys.exit(-1)

if __name__=='__main__':
    main()
