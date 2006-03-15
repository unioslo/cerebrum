#!/usr/bin/env python

import time
import ftplib
import cerebrum_path
import os

from Cerebrum.Utils import Factory
def main():
    db = Factory.get('Database')()
    logger = Factory.get_logger("cronjob")
    date = time.localtime()
    year = date[0]
    month = date[1]
    day = date[2]
    # lets create the filename
    file_path = "/cerebrum/var/dumps/Fronter/"
    filename = "uit_import%02d%02d%02d.xml" % (year,month,day)
    ret = os.system("mv /cerebrum/var/dumps/Fronter/test.xml /cerebrum/var/dumps/Fronter/%s" % filename)
    if ret != 0:
        logger.error("ERROR: unable to execute system command mv in copy_fronter_xml.py.\n")

    file_handle = open("%s%s"% (file_path,filename))
    # lets ftp the file to ftp.uit.no
    try:
        ftp = ftplib.FTP("ftp.uit.no","lmseksport","Fr0nt3r")
        #ftp.set_debuglevel(1)
        ftp.storlines("STOR %s" % filename,file_handle)
        
    except ftplib.all_errors:
        print "% unable to ftp file: %s" % ftplib.all_errors




if __name__=='__main__':
    main()
    
