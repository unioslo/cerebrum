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

import time
import forgetHTML
import Cereweb.config
import urllib
from Cereweb.SpineIDL.Errors import NotFoundError
import Error


WEBROOT = Cereweb.config.conf.get('cereweb', 'webroot')

def url(path):
    """Returns a full path for a path relative to the base installation.
       Example:
       url("group/search") could return "/group/search" for normal
       installations, but /~stain/group/search for test installations.
    """
    if path[:1] == '/':
        path = path[1:]
    if not (path.startswith('css') or path.endswith('png')
            or path.endswith('js')):
        path = 'Chandler.cgi' + '/' + path
    return WEBROOT + "/" + path

def _spine_type(object):
    """Return the type (string) of a Spine object.

    If the Spine object is an instance of SpineEntity, the name of
    get_type() is returned.  Else, the class name part of the the
    Spine IDL repository ID is returned.  

    For instance, _spine_type(some_account) -> "account" while
    _spine_type(some_spine_email_domain) -> EmailDomain

    
    """
    if object._is_a("IDL:SpineIDL/SpineEntity:1.0"):
        return object.get_type().get_name()
    else:
        # split up "IDL:SpineIDL/SpineEntity:1.0"
        idl_type = object._NP_RepositoryId.split(":", 3)[1]
        spine_type = idl_type.split("/")[1]
        # The Spine prefix is not important
        name = spine_type.replace("Spine", "")
        return name.lower()


def object_url(object, method="view", **params):
    """Return the full path to a page treating the object.
    
    Method could be "view" (the default), "edit" and other things.

    Any additional keyword arguments will be appended to the query part.
    """
    type = _spine_type(object)
    params["id"] = object.get_id()

    # FIXME: urlencode will separate with & - not &amp; or ?
    return url("%s/%s?%s" % (type, method, urllib.urlencode(params)))


def object_link(object, text=None, method="view", _class="", **params):
    """Create a HTML anchor (a href=..) for the object.

    The text of the anchor will be str(object) - unless
    the parameter text is given.

    Any additional keyword arguments will be appended to the query part.
    """
    url = object_url(object, method, **params)
    if text is None:
        type = _spine_type(object)
        if type == 'person':
            text = object.get_cached_full_name()
        elif type == 'ou':
            tmp = object.get_display_name()
            text = tmp and tmp or object.get_name()
        elif type == 'emailtarget':    
            try:
                primary = object.get_primary_address()
            except NotFoundError:
                text = "Email target of type '%s'" % object.get_type().get_name()
            else:
                text = primary.full_address() + " (%s)" % object.get_type().get_name()
        elif type == 'disk':
            text = object.get_path()
        elif hasattr(object, "get_name"):
        # should also cover
        #elif type in ('group', 'account'):
            text = object.get_name()   
        else:
            text = str(object)
            text.replace("<", "&lt;")
            text.replace(">", "&gt;")
    if _class:
        _class = ' class="%s"' % _class
    return '<a href="%s"%s>%s</a>' % (url, _class, text)

def redirect(req, url, temporary=False, seeOther=False):
    """
    Immediately redirects the request to the given url. If the
    seeOther parameter is set, 303 See Other response is sent, if the
    temporary parameter is set, the server issues a 307 Temporary
    Redirect. Otherwise a 301 Moved Permanently response is issued.

    General use:
        After a POST request you want to revert to the normal viewing:
            seeOther=True
        Some general style url, like entity/view?id=29, really should
        mean somewhere else, ie. group/view?id=29:
            the defaults (permanent redirect)
        An error occured, and you want to go to some default page
            temporary=True    
    """
    HTTP_SEE_OTHER = 303
    HTTP_TEMPORARY_REDIRECT = 307
    HTTP_MOVED_PERMANENTLY = 301

    assert not (temporary and seeOther) # cannot set both temporary and seeOther

    if seeOther:
        status = HTTP_SEE_OTHER
    elif temporary:
        status = HTTP_TEMPORARY_REDIRECT
    else:
        status = HTTP_MOVED_PERMANENTLY

    req.headers_out['Location'] = url
    req.status = status
    
def redirect_object(req, object, method="view", 
                    temporary=False, seeOther=False):
    """Redirects to the given object. 
       This is shorthand for calling object_url and redirect 
       in succession. See the respecting methods for
       explanation of the parameters.
    """                 
    url = object_url(object, method)                   
    redirect(req, url, temporary, seeOther)

def queue_message(req, message, error=False):
    """Queue a message
    
    The message will be displayed next time a Main-page is showed.
    If error is true, the message will be indicated as such.
    """
    if 'messages' not in req.session:
        req.session['messages'] = [(message, error)]
    else:
        req.session['messages'].append((message, error))
    req.session.save() #FIXME: temporarly fixes that session isnt saved when redirect.

def strftime(date, format="%Y-%m-%d", default=''):
    """Returns a string for the date.

    If date evaluates to true its formated with the 'format' string.
    Else the value of default will be returned.
    """
    return date and date.strftime(format) or default

def new_transaction(req):
    try:
        return req.session['session'].new_transaction()
    except Exception, e:
        raise Error.SessionError, e

def transaction_decorator(method):
    def transaction_decorator(req, *args, **vargs):
        tr = new_transaction(req)
        try:
            return method(req, transaction=tr, *args, **vargs)
        finally:
            try:
                # FIXME: sjekk status på transaction?
                tr.rollback()
            except:
                pass
    return transaction_decorator

# arch-tag: 046d3f6d-3e27-4e00-8ae5-4721aaf7add6
