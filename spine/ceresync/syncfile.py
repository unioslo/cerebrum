#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2004, 2005 University of Oslo, Norway
#
# This file is part of Cerebrum.
#
# Cerebrum is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Cerebrum is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Cerebrum; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.

import errors
import sync
import file
import config
import traceback

def main():
    last_update = file.LastUpdate(config.sync.get("spine", "last_change"))
    if last_update.exists():
        incr = True
        id = last_update.get()
    else:
        incr = False
        id = -1

    s = sync.Sync(incr, id)

    passwd = file.PasswdFile(config.sync.get("file", "passwd"))
    shadow = file.ShadowFile(config.sync.get("file", "shadow"))
    groupfile = file.GroupFile(config.sync.get("file", "group"))

    backend_map = {
        'account':[passwd, shadow],
        'group':[groupfile]
    }
    backends = [passwd, shadow, groupfile]


    for i in backends:
        i.begin(incr)

    try:
        for operation, obj in s.get_objects():
            if obj is None:
                continue # the object is not supported yet
            try:
                config.apply_default(obj, obj.type)
                config.apply_override(obj, obj.type)
                config.apply_quarantine(obj, obj.type)
                for i in backend_map[obj.type]:
                    if operation == 'add':
                        i.add(obj)
                    elif operation == 'delete':
                        i.delete(obj)
                    elif operation == 'update':
                        i.update(obj)
            except errors.NotSupportedError:
                pass    
    except Exception, e:
        traceback.print_exc()
        print "Exception %s occured, aborting" % e
        for i in backends:
            i.abort()
    else:            
        for i in backends:
            i.close()

        last_update.set(s.last_change)
        s.close()

if __name__ == "__main__":
    main()

# arch-tag: f5474ade-7356-4cda-95aa-cd6347dc5993
