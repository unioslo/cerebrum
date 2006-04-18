#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
import os
import time

def main():
    import cerebrum_path
    import cereconf
    
    date = time.localtime()
    year = date[0]
    month = date[1]
    day = date[2]
    time_stamp= "%02d%02d%02d" % (year,month,day)
    sbin_dir = '/cerebrum/sbin'
    log_dir = '/cerebrum/var/log/cerebrum'
    backup_dir ='/cerebrum/var/backup'
    contrib_dir = '/cerebrum/share/cerebrum/contrib/no/uit'

    ret =0
    ret = os.system("%s/job_runner.py --quit"% sbin_dir)
    if(ret != 0):
        print "Error: stopping the job_runner. is it running?"
    try:
        ret = os.system("gzip -9 -c %s/rooterror.log > %s/rooterror.log_%s.gz" % (log_dir,backup_dir,time_stamp))
        if (ret == 0):
            ret = os.system("rm %s/rooterror.log" % log_dir)
            ret = os.system("touch %s/rooterror.log" % log_dir)
            ret = os.system("echo 0 > %s/rooterror.log.pos" % log_dir)    
        ret = os.system("gzip -9 -c %s/rootwarn.log > %s/rootwarn.log_%s.gz" % (log_dir,backup_dir,time_stamp))
        if (ret == 0):
            ret = os.system("rm %s/rootwarn.log" % log_dir)
   except:
        print "error in log rotate"
    

            
if __name__=='__main__':
    main()

# arch-tag: b61dce1a-b426-11da-87e5-b8c76c0d91ee
