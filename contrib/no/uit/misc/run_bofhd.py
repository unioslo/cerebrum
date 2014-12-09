#!/usr/bin/env python

import os
import time
import sys

MAX_RESTARTS = 3
RESTART_INTERVAL = 30


def mail_error(subject, message):
    # this function sends an email to the system administrator in case
    # of an error in bofhd

    email_address = "bjorn.torsteinsen@cc.uit.no"
    SENDMAIL = "/usr/sbin/sendmail" # sendmail location
    p = os.popen("%s -t" % SENDMAIL, "w")
    p.write("From: cerebrum@bas.uit.no\n")
    p.write("To: %s\n" % email_address)
    p.write("subject: %s\n" % subject)
    p.write("\n")
    p.write("%s" % message)
    sts = p.close()
    if sts != None:
        print "Sendmail exit status", sts
        sys.exit(1)


def main():

    num_errors = 0
    do_while = True
    crashtime = 0
    while do_while:
        starttime = time.time()
        if ((crashtime != 0) and (crashtime - starttime) < RESTART_INTERVAL):   # less than 30 secs since last restart!
            num_errors += 1
            print "crash within RESTART_INTERVAL. upping counter=%d" % num_errors
        else:
            num_errors = 0
            print "crash outside RESTART_INTERVAL. (%s - %s <  %s) reset counter=%d" % (crashtime,starttime,RESTART_INTERVAL,num_errors)

        if (num_errors > MAX_RESTARTS):
            print "Too many restarts: QUIT"
            subject = "BOFHD: Too many restarts in %s secs. Bofhd dying..." % RESTART_INTERVAL
            message = "WARNING\nBofhd shutdown due to too many restarts. Checklogs!"
            mail_error(subject, message)
            sys.exit(2)
        
        try:
            print "Starting BOFHd"
            os.system("/cerebrum/sbin/bofhd.py -c /cerebrum/etc/cerebrum/config.dat -p 8000")
        except KeyboardInterrupt:
            print "Keyboard interrupt caught: Quitting cleanly"
            do_while = false
        except Exception,msg:
            print "BOFHD died"
            crashtime = time.time()
            datestring = time.strftime("%Y-%m-%d %H:%M:%S")
            subject = "BOFHD stopped at %s: return code: %s" % (datestring, ret)
            message = "BOFHD exception caught:\n%s " % msg
            mail_error(subject, message)
        else:
            print "WARN: uncaught exception:"




if __name__=='__main__':
    main()

