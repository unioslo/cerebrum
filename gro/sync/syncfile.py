#!/usr/bin/env python

import sync
import file
import config

def main():
    s = sync.Sync()
    passwd = file.PasswdFile(config.sync.get("file", "passwd"))
    shadow = file.ShadowFile(config.sync.get("file", "shadow"))
    passwd.begin()
    shadow.begin()
    try:
        for account in s.get_accounts():
            try:
                passwd.add(account)
                shadow.add(account)
            except file.NotSupportedError:
                pass    
    except Exception, e:
        print "Exception %s occured, aborting" % e
        passwd.abort()
        shadow.abort()            
    else:            
        passwd.close()    
        shadow.close()

    groupfile = file.GroupFile(config.sync.get("file", "group"))
    groupfile.begin()
    try:
        for group in s.get_groups():
            try:
                groupfile.add(group)
            except file.NotSupportedError:
                pass    
    except Exception, e:
        print "Exception %s occured, aborting" % e
        groupfile.abort()
    else:    
        groupfile.close()

if __name__ == "__main__":
    main()

# arch-tag: f5474ade-7356-4cda-95aa-cd6347dc5993
