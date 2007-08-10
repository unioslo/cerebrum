#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Send changes in LOGFILE to MAILTO if this program has been run before.
# If LOGFILE has become shorter, assume that it was deleted recently
# and that its contents has not been mailed yet.

import os
import sys
import re
import getopt

def process_logfile(logfile, pos_file=None, uninter=None):
    if not pos_file:
        pos_file = "%s.pos" % logfile
    try:
        logf = open(logfile, "r")
    except IOError, e:
        return "IOError: %s" % e, "Error reading %s" % logfile

    logf.seek(0, 2) # Seek to end of file
    new_pos = logf.tell()
    old_pos = 0
    text = ""
    try:
        posf = open(pos_file, "r")
    except IOError:
        subject = "Starting to mail changes in %s" % logfile
        text    = "First run.  Old log messages are ignored.\n"
        old_pos = new_pos
        open(pos_file, "w").write("%d\n" % new_pos)
    else:
        subject = "Changes in %s" % logfile
        old_pos = int(posf.read())
        posf.close()

    if new_pos < old_pos:
        truncated = 1
        logf.seek(0)
    else:
        truncated = 0
        logf.seek(old_pos)
    text += logf.read()
    if text != "" and text[-1] != "\n":
        text += "\n"
    if uninter:
        text = filter_uninteresting(text, uninter)
    if truncated:
        text = ("The file has been truncated to %d lines.\n\n%s"
                % (text.count("\n"), text))
    new_pos = logf.tell()

    if new_pos != old_pos:
        open(pos_file, "w").write("%d\n" % new_pos)

    return text, subject

def usage(exitcode=0):
    print """maillog.py [options]
    -f | --file filename : logfile to check
    -u | --uninteresting filename : dated patterns to ignore
    -m | --mailto address : recipients of change notice
    --no-filter : do not try to include contents of std{out,err}.log
    [-p | --pos-file filename] : optional pos filename, otherwise .pos
        is appended to the logfile name
    --group-jobs : parse lines from logger and group by process name
    """
    sys.exit(exitcode)

def extract_from_file(name):
    ret = "---------- Tail of %s ----------\n" % name
    try:
        f = file(name)
    except IOError:
        return ""
    lines = f.readlines()
    if not lines:
        return ""
    ret += "".join(lines[-10:])
    return ret[:65535]             # Prevent very long lines

def filter_log(text):
    ret = []
    failed_jobnames = []
    for t in text.split("\n"):
        ret.append(t)
        m = re.search(r"ERROR .*for (\S+), check (\S+)", t)
        if m:
            dirname = m.group(2)
            tmp = extract_from_file("%s/stderr.log" % dirname)
            if not tmp:
                tmp = extract_from_file("%s/stdout.log" % dirname)
            failed_jobnames.append(m.group(1))
            ret.append(tmp)
            
    return "\n".join(ret), failed_jobnames

def build_uninteresting(pattern_file):
    """Read patterns from file.  The format of the file is line based.
    Each line has three fields separated by whitespace: an expire date
    in the form YYYY-MM-DD, a job name, and a pattern in regular
    expression notation.  The job name '*' matches any job.  Comments
    are allowed, but # must be the first character of the line.
    Returns a dict of compiled regexpes with jobname as key.
    """

    from mx import DateTime
    patterns = {}
    now = DateTime.now()
    f = open(pattern_file)
    for line in f.readlines():
        if line.startswith('#'):
            continue
        if line.strip() == "":
            continue
        date, job, patt = line.split(None, 2)
        patt = patt[:-1]   # Remove trailing newline.  Why not use strip?
        if DateTime.strptime(date, "%Y-%m-%d") > now:
            if job in patterns:
                patterns[job].append(patt)
            else:
                patterns[job] = [patt]
    f.close()

    ret = {}
    for job in patterns:
        if len(patterns[job]) == 1:
            ret[job] = re.compile(patterns[job][0])
        else:
            # construct one big RE.  we don't try to make it optimal,
            # leave that to the RE engine.
            ret[job] = re.compile('(?:' + ")|(?:".join(patterns[job]) + ')')
    return ret

def filter_uninteresting(text, uninter, jobname=None):

    ret = []
    orgJobName = jobname
    for t in text.split("\n"):
        #print "*********************************"
        #print "0ORGjobname=%s" %(orgJobName)
        if (t == ''):
            continue
        #print "1jobname=%s  t='%s', uinter=%s" %(jobname,t,uninter)
        if (orgJobName == None):
             re_entry = re.compile(r'^\d+-\d+-\d+ \d+:\d+:\d+ ([^\[]+)\[(\d+)\]:')
             m=re_entry.match(t)
             if m:
                 jobname=m.group(1)
        #print "2jobname=%s" %(jobname)
        if jobname in uninter and re.search(uninter[jobname], t):
            #print "filtering %s" % t
            continue
        if '*' in uninter and re.search(uninter['*'], t):
            #print "filtereing %s" % t
            continue
        #print "accepting %s" % t
        ret.append(t)
    return "\n".join(ret)

def group_log(text, uninter=None):
    """Group log by the name of the job that generated the log
    message.

    Note that a new job-name is only used if the pid differs from the
    previous log-entry."""
    
    ret = {}
    re_entry = re.compile(r'^\d+-\d+-\d+ \d+:\d+:\d+ ([^\[]+)\[(\d+)\]:')
    job_id = prev_pid = None
    for line in text.split("\n"):
        m = re_entry.match(line)
        line += "\n"
        if m:
            if m.group(2) == prev_pid:
                pass
            else:
                job_id = m.group(1)
                prev_pid = m.group(2)
            if not ret.has_key(job_id):
                ret[job_id] = ''
            ret[job_id] += line
        else:
            if job_id is None:
                pass   # Ignore junk before first log-entry.  TBD: correct?
            else:
                ret[job_id] += line
    if uninter:
        for job_id in ret:
            ret[job_id] = filter_uninteresting(ret[job_id], uninter,
                                               job_id)
    return ret

def shrink_name(name, lvl):
    # Shrink a name while trying to preserve readability
    parts = name.split("_")
    p = 0
    while lvl > 0:
        tmp = parts[p]
        if len(tmp) > 1:
            if tmp.find("*") != -1:
                parts[p] = tmp[:tmp.find("*")-1] + tmp[tmp.find("*"):]
            else:
                parts[p] = tmp[:-1]
        p += 1
        if p >= len(parts):
            p = 0
            if len(parts[0]) <= 3:  # Shorter than this is pretty unreadable
                break
        lvl -= 1
    return "_".join(parts)

def build_subject(msg, jobnames, max_len=65):
    lvl = 0
    prev_shortform = None
    num_skipped = 0
    # Count duplicate jobnames
    tmp = {}
    for n in jobnames:
        if tmp.has_key(n):
            tmp[n] += 1
        else:
            tmp[n] = 1
    jobnames = []
    for v in tmp.keys():
        if tmp[v] > 1:
            jobnames.append("%s*%i" % (v, tmp[v]))
        else:
            jobnames.append(v)
    # Shrink names until it is short enough
    while True:
        shortform = " ".join([shrink_name(n, lvl) for n in jobnames])
        if prev_shortform == shortform:
            num_skipped += 1
            jobnames = jobnames[:-1]
            if not jobnames:
                break
            prev_shortform = None
            lvl = 0
            continue
        prev_shortform = shortform
        lvl += 1
        ret = "%s %s" % (msg, shortform)
        if num_skipped:
            ret += " +%i" % num_skipped
        if len(ret) < max_len:
            break
    return ret

def send_mail(mailto, subject, text):
    sendmail = os.popen("/usr/lib/sendmail -oi -oem -odb -t", "w")
    if mailto.count('cerebrum-logs'):
        sendmail.write("Reply-To: %s\n" % mailto)
    sendmail.write("To: %s\nSubject: %s\n\n" % (mailto, subject))
    sendmail.write(text)
    if sendmail.close():
        raise SystemExit("Sendmail failed!")

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'f:u:m:p:',
                                   ['file=', 'mailto=', 'pos-file=',
                                    'uninteresting=', 'no-filter', 'group-jobs',
                                    'stdin', 'subject='])
    except getopt.GetoptError:
        usage(1)

    logfile = uninter = mailto = pos_file = None
    do_filter = True
    group_jobs = False
    stdin = False
    override_subject = None
    for opt, val in opts:
        if opt in ('-f', '--file'):
            logfile = val
        elif opt in ('-p', '--pos-file'):
            pos_file = val
        elif opt in ('-u', '--uninteresting'):
            uninter = build_uninteresting(val)
        elif opt in ('-m', '--mailto'):
            mailto = val
        elif opt in ('--no-filter',):
            do_filter = False
        elif opt in ('--group-jobs',):
            group_jobs = True
        elif opt in ('--subject',):
            override_subject = val
        elif opt in ('--stdin',):
            stdin = True

    if not mailto or (not logfile and not stdin):
        usage(1)
    if stdin:
        subject = 'Subject not set'
        text = sys.stdin.read()
    else:
        text, subject = process_logfile(logfile, pos_file=pos_file,
                                        uninter=uninter)
    if group_jobs:
        for jobname, text in group_log(text, uninter=uninter).items():
            if len(text) > 0:
                send_mail(mailto, 'Errors from %s' % jobname, text)
    else:
        if do_filter:
            text, failed_jobnames = filter_log(text)
            if failed_jobnames:
                subject = build_subject("Error from", failed_jobnames)
        if text:
            if override_subject:
                subject = override_subject
            send_mail(mailto, subject, text)

if __name__ == '__main__':
    main()

