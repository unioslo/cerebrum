#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

from ceresync import sync
import ceresync.backend.file as filebackend

from ceresync import config
log = config.logger

def main():
    config.parse_args()

    try:
        s = sync.Sync(incr=False)
    except sync.AlreadyRunningWarning, e:
        log.warning(str(e))
        exit(1)
    except sync.AlreadyRunning, e:
        log.error(str(e))
        exit(1)

    aliases = filebackend.AliasFile(filename=config.get("file", "aliases"))
    
    log.debug("Syncronizing aliases")
    aliases.begin(False)

    try:
        for alias in s.view.get_aliases():
            log.debug("Processing account '%s@%s'", alias.local_part, alias.domain)
            aliases.add(alias)
    except IOError,e:
        log.error("Exception %s occured, aborting",e)
        aliases.abort()
    else:
        aliases.close()


if __name__ == "__main__":
    main()
