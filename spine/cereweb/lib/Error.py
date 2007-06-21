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
import utils 
import omniORB
from templates.ErrorTemplate import ErrorTemplate
from SpineIDL.Errors import *

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
    path = utils.clean_url(cherrypy.request.path)
    referer = cherrypy.request.headerMap.get('Referer', '')

    cherrypy.response.headerMap['Pragma'] = 'no-cache'
    cherrypy.response.headerMap['Cache-Control'] = 'max-age=0'

    if isinstance(error, omniORB.CORBA.COMM_FAILURE) or \
       isinstance(error, omniORB.CORBA.TRANSIENT):
        # We seem to have lost connection with the Spine server.  This is
        # handled by the login page so that the user gets information about
        # what's wrong.
        utils.redirect_to_login() 
    elif isinstance(error, AccessDeniedError):
        msg = "Sorry, you do not have permissions to do the requested operation."
        if cherrypy.config.get('server.showTracebacks'):
            traceback.print_exc()
        # Login page doesn't support queue_message
        if referer.split('?')[0].endswith('login'):
            utils.redirect('/login?msg=%s' % msg)
        else:
            utils.queue_message(msg, error=True)
            utils.redirect(referer)
    elif isinstance(error, IntegrityError):
        title = "Operation failed"
        message = "The operation you tried to do would cause an integrity error "
        message += "in the database.  The usual reason for this is that you tried "
        message += "to delete an object that is referenced elsewhere."
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
    
    if path in referer or 'login' in path:
        template = ErrorTemplate()
        return template.error(title, message, path, tracebk, referer, report)

    import mx.DateTime
    msg = {
        'title': title,
        'message': message,
        'error': True,
        'details': tracebk,
        'link': None,
        'date': mx.DateTime.now(),
    }
        
    utils.queue_message(data=msg)
    utils.redirect(referer)

# arch-tag: 52b56f54-2b55-11da-97eb-80927010959a
