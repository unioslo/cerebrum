#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
# copyright 2004, 2005, 2006 university of oslo, norway
#
# this file is a part of cerebrum.
#
# cerebrum is free software; you can redistribute it and/or modify it
# under the terms of the gnu general public license as published by
# the free software foundation; either version 2 of the license, or
# (at your option) any later version.
#
# cerebrum is distributed in the hope that it will be useful, but
# without any warranty; without even the implied warranty of
# merchantability or fitness for a particular purpose.  see the gnu
# general public license for more details.
#
# you should have received a copy of the gnu general public license
# along with cerebrum; if not, write to the free software foundation,
# inc., 59 temple place, suite 330, boston, ma 02111-1307, usa.
#
# Author: Lasse Karstensen <lasse.karstensen_aaaat_ntnu.no>
#
import sys, os, getopt
import errors
import sync
from backend.file import SambaFile,PasswdFileCryptHash

import config
import traceback
import omniORB # for the exception
import cPickle


starttime = None
def log(msg):
    global starttime
    import time
    now = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    if not starttime:
        delta = 0.00
        starttime = time.time()
    else:
        delta = float(time.time() - starttime)
    try: 
        logmethod = config.sync.get("log","logmethod")
    except Exception:
        logmethod = 'stderr'
        logdest = sys.stderr

    if logmethod == "file":
        try:
            logdest   = config.sync.get("log","logdest")
            logdest = open(logdest, 'a')
        except:
            logmethod = 'stderr'
            logdest = sys.stderr


    logmsg = "(%.2fs): %s" % (delta, msg)
    if logmethod == "syslog":
        import syslog
        syslog.openlog("%s[%s]" % (os.path.basename(sys.argv[0]), os.getpid()))
        syslog.syslog(logmsg)
        return


    # either stderr or file.
    print >>logdest, "%s %s" % (now, logmsg)
    return

def usage():
    print "Usage: %s -c <config file>"  % os.path.basename(sys.argv[0])
    print "-v be verbose"
    print "-c <config file>"
    return

def main():
    verbose = False
    readcached = False

    try:
        opts, args = getopt.getopt(sys.argv[1:], "vhc:")
    except getopt.GetoptError:
        usage()
        sys.exit(2)

    for o, a in opts:
        if o == "-h":
            usage()
            sys.exit(2)
        if o == "-v":
            verbose = True
        if o == "-c":
            config.sync.read(a)
            if verbose:
                log("reading config file %s" % a )
                log("spread is: %s" % config.sync.get("sync","account_spread"))

    incr = False
    id = -1

    acclist = []
    grouplist = []
    pwdict = {}
    hashtypes = [
                "crypt3-DES",
                "MD4-NT",
                "LANMAN-DES"
                ]
    if verbose: 
        log("Creating sync object")

    try:
        s = sync.Sync(incr, id, hashtypes[0])
    except omniORB.CORBA.TRANSIENT, e:
        log("Server seems down. Error: %s" % e)
        sys.exit(255)
    except IOError, e:
        log("IOError, shutting down. Error: %s" % e)
        sys.exit(255)

    if verbose: 
        log("Done creating sync object")

    if verbose: 
        log("Fetching hashes for all accounts")

    for hashtype in hashtypes:
        s.set_authtype(hashtype)
        for acc in s.get_accounts():
            if acc.passwd == None or acc.passwd == '':
                if verbose:
                    log("account %s mangler passordtype %s" % (acc.name, hashtype))
                continue
            # Try save time doing it all in a loop-de-loop
            if not pwdict.has_key(acc.name):
                acclist.append(acc)
                pwdict[acc.name] = { }
            pwdict[acc.name][hashtype] = acc.passwd
    s.close()

    if verbose: 
        log("Parsing and creating files")

    smbfile = SambaFile( config.conf.get("file","smbpasswd" ) )
    smbfile.begin(incr)

    accounts = PasswdFileCryptHash(filename=config.conf.get("file","passwd") )
    accounts.begin(incr)

    for account in acclist:
        if len(account.quarantines) > 0:
            if verbose:
                #print account.quarantines
                log("Skipping account %s with quarantines: %s" % (account.name, account.quarantines))
            continue

        ntlmhash = pwdict[account.name].get('MD4-NT')
        lmhash =   pwdict[account.name].get('LANMAN-DES')

        userhashes = (lmhash, ntlmhash)
        smbfile.add(account, hashes=userhashes )

        if account.posix_uid >= 0:
            accounts.add(account)

    smbfile.close()
    accounts.close()

    if verbose: 
        log( "Done" )

if __name__ == "__main__":
    main()