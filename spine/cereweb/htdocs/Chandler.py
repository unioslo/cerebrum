#!/usr/bin/env python

import os
import sys
import cgi
import Cookie
import traceback
import cereweb_path

from Cereweb.Session import Session

class Req(object):
    def __init__(self):
        self.headers_out = {}
        self.status = 200

dirname = os.path.dirname(__file__)

def cgi_main():
    args = {}
    for key, value in cgi.parse().items():
        args[key] = type(value) == list and len(value) == 1 and value[0] or value

    req = Req()
    req.session = None
    req.headers_out['Content-Type'] = 'text/html'
    req.headers_out['Pragma'] = 'no-cache'
    req.headers_out['Cache-Control'] = 'max-age=0'

    c = Cookie.SimpleCookie()
    c.load(os.environ.get('HTTP_COOKIE', ''))
    id = c.get('cereweb_id')

    if id:
        try:
            req.session = Session(id.value)
        except IOError, e:
            pass

    path = os.environ.get('PATH_INFO', '')[1:]

    if not path:
        path = 'index/index'

    if req.session is None:
        path = 'login/index'

    try:
        doc = '<html><body>not found: %s</body></html>' % path
        if '/' in path:
            module, method = path.split('/', 1)
        else:
            module, method = path, 'index'


        if os.path.exists(os.path.join(dirname, '%s.py' % module)):
            module = __import__(module)

            if method[:1].isalpha() and method.isalnum():
                doc = getattr(module, method)(req, **args)

        if req.session is not None:
            req.session.save()
            cookie = Cookie.SimpleCookie()
            cookie['cereweb_id'] = req.session.id
            print cookie.output()

        for key, value in req.headers_out.items():
            print '%s: %s' % (key, value)
        if req.status is not None:
            print 'Status:', req.status
        print
        print doc
    except:
        print
        print '<html><pre>'
        traceback.print_exc(file=sys.stdout)
        print os.environ
        print '</pre></html>'

if __name__ == '__main__': # for cgi
    cgi_main()
