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
import sys
from ceresync import syncws as sync
from ceresync.backend.file import SambaFile,PasswdFileCryptHash

from ceresync import config
import omniORB # for the exceptions

log = config.logger

def main():
    config.parse_args()

    log.debug("spread is: %s" , config.get("sync","account_spread"))

    incr = False

    acclist = []
    grouplist = []
    pwdict = {}
    hashtypes = [
                "crypt3-DES",
                "MD4-NT",
                "LANMAN-DES"
                ]
    log.debug("Creating sync object")

    try:
        s = sync.Sync()
    except sync.AlreadyRunningWarning, e:
        log.warning(str(e))
        sys.exit(1)
    except sync.AlreadyRunning, e:
        log.error(str(e))
        sys.exit(255)
    except IOError, e:
        log.error("IOError, shutting down. Error: %s", e)
        sys.exit(255)

    log.debug("Done creating sync object")

    log.info("Fetching hashes for all accounts")

    for hashtype in hashtypes:
        for acc in s.get_accounts(auth_type=hashtype):
            if acc.passwd == None or acc.passwd == '':
                log.warning("account %s mangler passordtype %s", 
                               acc.name, hashtype)
                continue
            # Try save time doing it all in a loop-de-loop
            if not pwdict.has_key(acc.name):
                acclist.append(acc)
                pwdict[acc.name] = { }
            pwdict[acc.name][hashtype] = acc.passwd

    log.debug("Parsing and creating files")

    smbfile = SambaFile( config.get("file","smbpasswd" ) )
    smbfile.begin(incr, unicode=True)

    accounts = PasswdFileCryptHash(filename=config.get("file","passwd") )
    accounts.begin(incr, unicode=True)

    for account in acclist:
        if len(account.quarantines) > 0:
            log.info("Skipping account %s with quarantines: %s", 
                        account.name, account.quarantines)
            continue

        ntlmhash = pwdict[account.name].get('MD4-NT')
        lmhash =   pwdict[account.name].get('LANMAN-DES')

        userhashes = (lmhash, ntlmhash)
        smbfile.add(account, hashes=userhashes )

        if account.posix_uid is not None:
            accounts.add(account)

    smbfile.close()
    accounts.close()

    log.debug("Syncronization done")

if __name__ == "__main__":
    main()
