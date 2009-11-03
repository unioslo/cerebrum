#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

from ceresync import syncws as sync
from ceresync import config

config.parse_args()

def main():
    s= sync.Sync(locking=False)
    print s.get_changelogid() 

if __name__ == "__main__":
    main()

