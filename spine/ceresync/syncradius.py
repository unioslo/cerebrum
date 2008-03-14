#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
# Copyright 2004 - 2008 university of oslo, norway
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
from ceresync import errors
from ceresync import sync
from ceresync.backend.file import SambaFile,PasswdFileCryptHash

from ceresync import config
import traceback
import omniORB # for the exception

log= config.logger

def usage():
    print "Usage: %s -c <config file>"  % os.path.basename(sys.argv[0])
    print "-v be verbose"
    print "-c <config file>"
    return

def main():
    verbose = False

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
            log.debug("reading config file %s" , a )
            log.debug("spread is: %s" , config.sync.get("sync","account_spread"))

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
    log.info("Creating sync object")

    try:
        s = sync.Sync(incr, id, hashtypes[0])
    except omniORB.CORBA.TRANSIENT, e:
        log.error("Server seems down. Error: %s",e)
        sys.exit(255)
    except IOError, e:
        log.error("IOError, shutting down. Error: %s", e)
        sys.exit(255)

    log.debug("Done creating sync object")

    log.info("Fetching hashes for all accounts")

    for hashtype in hashtypes:
        s.set_authtype(hashtype)
        for acc in s.get_accounts():
            if acc.passwd == None or acc.passwd == '':
                log.warning("account %s mangler passordtype %s", 
                               acc.name, hashtype)
                continue
            # Try save time doing it all in a loop-de-loop
            if not pwdict.has_key(acc.name):
                acclist.append(acc)
                pwdict[acc.name] = { }
            pwdict[acc.name][hashtype] = acc.passwd
    s.close()

    log.info("Parsing and creating files")

    smbfile = SambaFile( config.conf.get("file","smbpasswd" ) )
    smbfile.begin(incr)

    accounts = PasswdFileCryptHash(filename=config.conf.get("file","passwd") )
    accounts.begin(incr)

    for account in acclist:
        if len(account.quarantines) > 0:
            log.info("Skipping account %s with quarantines: %s", 
                        account.name, account.quarantines)
            continue

        ntlmhash = pwdict[account.name].get('MD4-NT')
        lmhash =   pwdict[account.name].get('LANMAN-DES')

        userhashes = (lmhash, ntlmhash)
        smbfile.add(account, hashes=userhashes )

        if account.posix_uid >= 0:
            accounts.add(account)

    smbfile.close()
    accounts.close()

    log.info("Syncronization done")

if __name__ == "__main__":
    main()
