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

import cherrypy

import os
import sys
import traceback
import urllib
import config
from utils import redirect
from templates.ErrorTemplate import ErrorTemplate

class SessionError(Exception):
    """Indicates a problem with the connection
    """

class NotFoundError(Exception):
    """A non existing resource was requested
    """

class CustomError(Exception):
    """Used as a shortcut to display an error-page with a title and message.

    The first argument should be the title of the error, and the
    seccond should be its message. Both must be included.
    """

class Redirected(Exception):
    pass # presentere en side for browsere som ikke støtter redirect?


def handle(error):
    title, message, tracebk = None, None, None
    path = cherrypy.request.path
    referer = cherrypy.request.headerMap.get('Referer', '')

    cherrypy.response.headerMap['Pragma'] = 'no-cache'
    cherrypy.response.headerMap['Cache-Control'] = 'max-age=0'
    
    if isinstance(error, SessionError):
        if path not in ('/', '/login'):
            if path.split('/')[-1] not in ('make', 'delete', 'save'):
                tmp = path + urllib.quote("?" + cherrypy.request.queryString)
            else:
                tmp = '/'.join(path.split('/')[:-1])
            msg = "Your session has most likely timed out."
            redirect('/login?redirect=%s&msg=%s' % (tmp, msg))
        else:
            redirect('/login')
        return
    elif isinstance(error, Redirected):
        title = "Redirection error."
        message = "Your browser does not seem to support redirection."
    elif isinstance(error, NotFoundError):
        title = "Resource not found."
        message = "The requested resource was not found."
    elif isinstance(error, CustomError):
        title, message = error.args
        tracebk = "No traceback"
        
    if title is None:
        title = error.__class__.__name__
    if message is None:
        message = str(error)
    if tracebk is None:
        tracebk = "".join(traceback.format_exception(*sys.exc_info()))

    if not config.conf.getboolean('error', 'allow_traceback'):
        tracebk = ""
    
    report = config.conf.getboolean('error', 'allow_reporting')
    
    template = ErrorTemplate()
    return template.error(title, message, path, tracebk, referer, report)

# arch-tag: 52b56f54-2b55-11da-97eb-80927010959a
