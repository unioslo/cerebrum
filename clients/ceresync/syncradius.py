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
from ceresync import config

log = config.logger

def main():
    sync_options = {}
    config.parse_args(config.make_testing_options())
    config.set_testing_options(sync_options)
    using_test_backend = config.getboolean('args', 'use_test_backend')

    log.debug("spread is: %s" , config.get("sync","account_spread"))

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
        s = sync.Sync(locking=not using_test_backend)
    except sync.AlreadyRunningWarning, e:
        log.error(str(e))
        sys.exit(1)
    except sync.AlreadyRunning, e:
        log.error(str(e))
        sys.exit(1)
    except Exception, e:
        log.error("Exception %s occured, aborting",e)
        sys.exit(1)

    if using_test_backend:
        from ceresync.backend.test import Samba, PasswdWithHash
    else:
        from ceresync.backend.file import Samba, PasswdWithHash

    log.debug("Done creating sync object")

    log.info("Fetching hashes for all accounts")

    try:
        for hashtype in hashtypes:
            for acc in s.get_accounts(auth_type=hashtype, **sync_options):
                if acc.passwd == None or acc.passwd == '':
                    log.warning("account %s missing auth_type %s", 
                                   acc.name, hashtype)
                    continue
                # Try save time doing it all in a loop-de-loop
                if not pwdict.has_key(acc.name):
                    acclist.append(acc)
                    pwdict[acc.name] = { }
                pwdict[acc.name][hashtype] = acc.passwd
    except Exception, e:
        log.error("Exception %s occured, aborting",e)
        sys.exit(1)

    log.info("Parsing and creating files")

    smbfile = Samba()
    smbfile.begin(unicode=True)

    accounts = PasswdWithHash()
    accounts.begin(unicode=True)

    try:
        for account in acclist:
            if len(account.quarantines) > 0:
                log.debug("Skipping account %s with quarantines: %s", 
                            account.name, account.quarantines)
                continue

            log.debug("Processing account %s" % account.name)

            ntlmhash = pwdict[account.name].get('MD4-NT')
            lmhash =   pwdict[account.name].get('LANMAN-DES')

            userhashes = (lmhash, ntlmhash)
            smbfile.add(account, hashes=userhashes )

            if account.posix_uid is not None:
                accounts.add(account)
    except Exception, e:
        log.error("Exception %s occured, aborting",e)
        smbfile.abort()
        accounts.abort()
    else:
        smbfile.close()
        accounts.close()

    log.info("Syncronization done")

if __name__ == "__main__":
    main()
