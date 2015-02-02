#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Send changes in LOGFILE to MAILTO if this program has been run before.
# If LOGFILE has become shorter, assume that it was deleted recently
# and that its contents has not been mailed yet.

import os
import sys
import re
import getopt
import time
import cerebrum_path
import cereconf

send_mail_to = "bas-admin@cc.uit.no"


def send_mail(mailto, subject, text):
    sendmail = os.popen("/usr/lib/sendmail -oi -oem -odb -t", "w")
    if mailto.count('cerebrum-logs'):
        sendmail.write("Reply-To: %s\n" % mailto)
    sendmail.write("To: %s\nSubject: %s\n\n" % (mailto, subject))
    sendmail.write(text)
    if sendmail.close():
        raise SystemExit("Sendmail failed!")





def process_logfile(logfile):


    from mx import DateTime
    

    try:
        logf = open(logfile,"r")
    except IOError, e:
        print "IOError: %s Error reading %s" % (e,logfile)
        return 1



    lastfile = "%s.last" % logfile
    laststr = ""
    try:
        lastf = open(lastfile,'r+')
        laststr = lastf.read()
        lastf.close()
    except IOError,e:
        print "IOError: %s Error reading last file %s"% (e,lastfile)


    look_for = "exit_code=1"
    job_runner_path = cereconf.CB_PREFIX + "/var/log/cerebrum/job_runner"
    
    lines = logf.readlines()
    logf.close()

    global_msg = subject = first_lines = ""
    tstamp = None

    for logline in lines:
        try:
            idx = logline.index(look_for)
        except ValueError:
            # fant ikke det vi lette etter i logfila.
            # gå til neste linje
            continue

        now = DateTime.now()
        if (subject == ""):
            subject = "Errors from job_runner %s" % now

        logline = logline.rstrip()
        job_part, output_part = logline.split(",",1)
        job_name = job_part.split(" ")[-1]  # last item in splitlist is job_name
        tstamp = output_part.split(".")[-2:] # timestamp
        tstamp = ".".join(tstamp)

        if (tstamp <= laststr):
            # processed this line before
             continue

        output_path  = output_part[7:]
        std_err_file = "%s/%s/stderr.log" % (job_runner_path,output_path)
        std_out_file = "%s/%s/stdout.log" % (job_runner_path,output_path)
        strTime = time.strftime("%Y%m%d-%H%M",time.localtime(float(tstamp)))
        first_lines += "JOB '%s' returned 1 at %s\n" % (job_name,strTime)
        global_msg += "\n%s\nJOB '%s' returned 1 at %s\n" % ('-'*60,job_name,strTime)
        
        try:
            f_stderr = open(std_err_file,'r')
            std_err_content = f_stderr.readlines()
            f_stderr.close()
            if (len(std_err_content)>0):
                global_msg += "\nSTD ERROR:\n" 
                for i in std_err_content:
                    global_msg += i
        except IOError,e:
            global_msg += "failed to read std err file %s\n" % std_err_file
            
        try:
            f_stdout = open(std_out_file,'r')
            std_out_content = f_stdout.readlines()
            f_stdout.close()
            if (len(std_out_content)>0):
                global_msg += "\nSTD OUT:\n" 
                for i in std_out_content:
                    global_msg += i
        except IOError,e:
            global_msg +=  "failed to read std err file %s\n" % std_out_file
            



    #print global_msg

    if (tstamp):
        # update the log.last file with latest timestamp
        try:
            lastf = open(lastfile,'w+')
            laststr = lastf.write(tstamp)
            lastf.close()
        except IOError,e:
            print "IOError: %s Error writing last file %s"% (e,lastfile)
            
    
    if (global_msg != ""):
        send_mail(send_mail_to, subject, first_lines + global_msg)


def usage(exitcode=0):

    print """
    Usage: check_job_runner_log.py -f log-file
    -f or --file: job_runners log file

    example: check_job_runner_log.py -f /cerebrum/var/log/cerebrum/job_runner.log

    """
    sys.exit(exitcode)



def main():
    try:
        opts,args = getopt.getopt(sys.argv[1:],'f:',['file=',])
    except getopt.GetoptError:
        usage(1)


    logfile = None


    for opt, val in opts:
        if opt in ('-f', '--file'):
            logfile = val


    if not logfile:
        usage(1)


    process_logfile(logfile)



if __name__ == '__main__':
    main()

