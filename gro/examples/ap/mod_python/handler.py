# -*- coding: iso-8859-1 -*-

# Copyright 2004 University of Oslo, Norway
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

from mod_python import apache,util

def getArgs(req):
    fs = util.FieldStorage(req, keep_blank_values=1)

    args = {}
    for field in fs.list:
        if field.filename:
            val = File(field)
        else:
            val = field.value
        if args.has_key(field.name):
            j = args[field.name]
            if type(j) == list:
                j.append(val)
            else:
                args[field.name] = [j,val]
        else:
            args[field.name] = val
    return args

import Cerebrum.gro.ServerConnection
from omniORB.any import from_any, to_any

gro = None
def getAP():
    try:
        gro.test()
    except:
        print 'will try to connect to gro'
        gro = Cerebrum.gro.ServerConnection.connect()
    return gro.get_ap_handler('testuser', 'secretpassword')

def printer(obj):
    if hasattr(obj, '__iter__') or type(obj) == list: # teite gamle python. oppgrader!
        return '%s' % ', '.join([printer(i) for i in obj])
    if hasattr(obj, 'getPrimaryKey'):
        try:
            cId = obj.getLong('id')
        except:
            cId = 'None'
        return '<a href=?className=%s&id=%s>%s</a>(%s)' % (obj.getClassName(), cId, obj.getClassName(), printer(from_any(obj.getPrimaryKey())))
#        return '%s(%s)' % (obj.getClassName(), ', '.join([printer(i) for i in from_any(obj.getPrimaryKey())]))
    return str(obj)

def getNode(className, id):
    ap = getAP()

    node = ap.getNode(className, to_any([int(id)]))
    node.begin()
    txt = ''

    txt += 'Information for %s(id=%s):<br>' % (node.getClassName(), id)
    for var in node.getReadAttributes():
        txt += '%s: %s<br>' % (var, printer(from_any(node.get(var))))
    txt += '<br>'
    for i, j in ('Parents', node.getParents()), ('Children', node.getChildren()):
        txt += '%s:<br>' % i
        for i in j:
            try:
                cId = i.getLong('id')
            except:
                cId = 'None'
            txt += '<a href=?className=%s&id=%s>[%s</a>(%s)]<br>' % (i.getClassName(), cId, i.getClassName(), printer(from_any(i.getPrimaryKey())))
        txt += '<br>'
    node.rollback()
    return txt

def handler(req):
    req.content_type = 'text/html'

    args = getArgs(req)

    req.write('<html><body>\n')
    req.write(getNode(**args))
    req.write('</html></body>\n')
    
    return apache.OK

# arch-tag: 2e2043eb-37ee-4f93-a4c4-d6fa3fa64dc0
