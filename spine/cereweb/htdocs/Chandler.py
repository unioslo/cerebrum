#!/usr/bin/env python

import os
import sys
import cgi
import Cookie
import traceback

import cereweb_path
from Cereweb import Error
from Cereweb.Session import Session
from Cereweb.utils import url, redirect
import forgetHTML as html

class Req(object):
    """Request class

    Emulates the mod_python Request object
    """
    def __init__(self):
        self.headers_in = {'referer':os.environ.get('HTTP_REFERER', '')}
        self.headers_out = {}
        self.status = 200

        # FIXME: er det kanskje req.the_request?
        self.unparsed_uri = os.environ['REQUEST_URI']

dirname = os.path.dirname(__file__)

def cgi_main(path):
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
        except KeyError, e:
            id = None

    if not path:
        path = os.environ.get('PATH_INFO', '')[1:]

    try:
        if not path == 'login':
            # check if client is logged in or not
            if id is None or not req.session:
                redirect(req, url('/login?redirect=%s' % req.unparsed_uri))
#                raise Error.Redirected

            # go to /index if client requested root
            elif not path:
                redirect(req, url("/index"))
#                raise Error.Redirected


        doc = '<html><body>not found: %s</body></html>' % path
        if '/' in path:
            module, method = path.split('/', 1)
        else:
            # defaults to example/index -> example.index(req, *args, **kargs)
            module, method = path, 'index'

        # Only allow importing of modules containing a-z A-Z
        if module.isalpha() and os.path.exists(os.path.join(dirname, '%s.py' % module)):
            module = __import__(module)

            # Only allow method calls containing a-z, A-Z and _
            # First character must be a-z or A-Z
            if method[:1].isalpha() and method.replace('_', '').isalnum():
                doc = getattr(module, method)(req, **args)

        # convert doc to a string. This might fail. We want
        # to do this before we start to print headers
        doc = str(doc)

        # old session. Save it
        if req.session:
            req.session.save()

        # new session. Set the cookie
        if id is None and req.session is not None:
            cookie = Cookie.SimpleCookie()
            cookie['cereweb_id'] = req.session.id
            print cookie.output()

        # Print all headers
        for key, value in req.headers_out.items():
            print '%s: %s' % (key, value)
        if req.status is not None:
            print 'Status:', req.status
        print

        # Print document
        print doc

    except Exception, e:
        print 'Content-Type: text/html'
        print 'Pragma: no-cache'
        print 'Cache-Control: max-age=0'
        print
        print Error.handle(req, e)

if __name__ == '__main__': # for cgi
    if sys.argv[1:2]:
        path = sys.argv[1]
    else:
        path = None
    cgi_main(path)

# arch-tag: 203bd6c2-22de-4bf2-9d6f-f7c658e1fc55
