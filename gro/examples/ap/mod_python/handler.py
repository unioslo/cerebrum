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
