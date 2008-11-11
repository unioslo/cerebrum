#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

from ceresync import sync

import config
log = config.logger

def main():
    config.parse_args()
    s= sync.Sync(incr=False)
    print s.cmd.get_last_changelog_id() 
    aa=s.view.get_aliases()
    for a in aa:
        if a.address_id == a.primary_address_id:
            print "%s@%s: <> %s@%s" % (
                a.local_part, a.domain,
                a.account_name, a.server_name )
	else:
	    print "%s@%s: %s@%s" % (
                a.local_part, a.domain,
                a.primary_address_local_part, a.primary_address_domain )

if __name__ == "__main__":
    main()
