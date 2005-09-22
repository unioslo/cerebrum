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
        self.content_type = 'text/html'
        self.status = 200

        # FIXME: er det kanskje req.the_request?
        self.unparsed_uri = os.environ['REQUEST_URI']

    def write(self, txt):
        if self.headers_out is not None:
            # Print all headers
            print 'Content-Type:', self.content_type
            for key, value in self.headers_out.items():
                print '%s: %s' % (key, value)
            if self.status is not None:
                print 'Status:', self.status
            print
            self.headers_out = None
        sys.stdout.write(txt)



dirname = os.path.dirname(__file__)

def cgi_main():
    args = {}
    for key, value in cgi.parse().items():
        args[key] = type(value) == list and len(value) == 1 and value[0] or value
    req = Req()

    req.session = None

    c = Cookie.SimpleCookie()
    c.load(os.environ.get('HTTP_COOKIE', ''))
    id = c.get('cereweb_id')

    path = os.environ.get('PATH_INFO', '')[1:]

    if id:
        try:
            req.session = Session(id.value)
        except KeyError, e:
            id = None

    main(req, id, path, args)

def handler(req):
    req.content_type = 'text/html'
    from mod_python import apache, util
    from mod_python.Cookie import get_cookies, Cookie

    page_cookies = get_cookies(req, Cookie)
    id = page_cookies.get('cereweb_id')
    req.session = None
    if id:
        try:
            req.session = Session(id.value)
        except KeyError, e:
            id = None

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

    path = req.path_info[1:]
            
    main(req, id, path, args)
    return apache.OK

def main(req, id, path, args):
    req.headers_out['Pragma'] = 'no-cache'
    req.headers_out['Cache-Control'] = 'max-age=0'

    try:
        if not path == 'login':
            # check if client is logged in or not
            if id is None or not req.session:
                if path:
                    redirect(req, url('/login?redirect=%s' % req.unparsed_uri), temporary=True)
                else:
                    redirect(req, url('/login'), temporary=True)
                path = 'redirected'
#                raise Error.Redirected

            # go to /index if client requested root
            elif not path:
                redirect(req, url("/index"))
                path = 'redirected'
#                raise Error.Redirected


        doc = None
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
                if hasattr(module, method):
                    doc = getattr(module, method)(req, **args)

        # convert doc to a string. This might fail. We want
        # to do this before we start to print headers
        if not doc:
            raise Error.CustomError("Page not found", "The page '%s' was not found." % path)
        else:
            doc = str(doc)

        # old session. Save it
        if req.session:
            req.session.save()

        # new session. Set the cookie
        if id is None and req.session is not None:
            cookie = Cookie.SimpleCookie()
            cookie['cereweb_id'] = req.session.id
            txt = cookie.output()
            name, data = txt.split(':', 1)
            req.headers_out[name.strip()] = data.strip()

        # write document
        req.write(doc)

    except Exception, e:
        req.write(Error.handle(req, e))

if __name__ == '__main__': # for cgi
    cgi_main()

# arch-tag: 203bd6c2-22de-4bf2-9d6f-f7c658e1fc55
