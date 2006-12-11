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
import urllib
import mx.DateTime
import cherrypy

def _spine_type(object):
    """Return the type (string) of a Spine object.

    If the Spine object is an instance of SpineEntity, the name of
    get_type() is returned.  Else, the class name part of the the
    Spine IDL repository ID is returned.  

    For instance, _spine_type(some_account) -> "account" while
    _spine_type(some_spine_email_domain) -> EmailDomain
    """
    if type(object) == type({}):
        return object['object_type']
    elif object._is_a("IDL:SpineIDL/SpineEntity:1.0"):
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
    object_type = _spine_type(object)

    if type(object) == type({}):
        params["id"] = object['id']
    else:
        params["id"] = object.get_id()

    if object_type == 'emaildomain':
        object_type = 'email'

    # FIXME: urlencode will separate with & - not &amp; or ?
    return "/%s/%s?%s" % (object_type, method, urllib.urlencode(params))


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
            from SpineIDL.Errors import NotFoundError
            try:
                primary = object.get_primary_address()
            except NotFoundError:
                text = "Email target of type '%s'" % object.get_type().get_name()
            else:
                text = primary.full_address() + " (%s)" % object.get_type().get_name()
        elif type == 'disk':
            text = object.get_path()
        elif type == 'project':
            text = object.get_title() or "(untitled %d)" % (object.get_id(),)
        elif type == 'allocation':
            text = object.get_allocation_name().get_name()
        elif hasattr(object, "get_name"):
            text = object.get_name()   
        elif type == 'account':
            text = object['name']
        else:
            text = str(object)
            text.replace("<", "&lt;")
            text.replace(">", "&gt;")
    if _class:
        _class = ' class="%s"' % _class
    return '<a href="%s"%s>%s</a>' % (url, _class, text)

def redirect(url, status=None):
    raise cherrypy.HTTPRedirect(url, status)

def redirect_object(object, method="view", status=None):
    """Redirects to the given object. 
       This is shorthand for calling object_url and redirect 
       in succession. See the respecting methods for
       explanation of the parameters.
    """                 
    url = object_url(object, method)
    raise cherrypy.HTTPRedirect(url, status)

def queue_message(message, error=False, link=''):
    """Queue a message.
    
    The message will be displayed next time a Main-page is showed.
    If error is true, the message will be indicated as such.
    Link is used in activitylog so the user knows which
    object the action was on, should be a string linking to
    the object.
    """
    # When we're called through _cpOnErrors, the cherrypy.session
    # isn't set up properly.  The workaround is to access the
    # session dict through the request object.
    if not hasattr(cherrypy.session, 'sessionStorage'):
        sessionData = cherrypy.request._session.sessionData
    else:
        sessionData = cherrypy.session

    timestamp = mx.DateTime.now()
    if 'messages' not in sessionData:
        sessionData['messages'] = [(message, error)]
    else:
        sessionData['messages'].append((message, error))
    if 'al_messages' not in sessionData:
        sessionData['al_messages'] = [(message, error, link, timestamp)]
    else:
        sessionData['al_messages'].append((message, error, link, timestamp))

def strftime(date, format="%Y-%m-%d", default=''):
    """Returns a string for the date.

    If date evaluates to true its formated with the 'format' string.
    Else the value of default will be returned.
    """
    return date and date.strftime(format) or default

def strptime(tr, date, format="%Y-%m-%d"):
    """Returns a Date obj for the date-string."""
    if date:
        return tr.get_commands().strptime(date, format)
    else:
        return None

def new_transaction():
    try:
        return cherrypy.session['session'].new_transaction()
    except Exception, e:
        import Error
        raise Error.SessionError, e

def transaction_decorator(method):
    def transaction_decorator(*args, **vargs):
        cherrypy.session['timestamp'] = time.time()
        tr = new_transaction()
        try:
            return method(transaction=tr, *args, **vargs)
        finally:
            try:
                # FIXME: sjekk status på transaction?
                tr.rollback()
            except:
                pass
    return transaction_decorator

def commit(transaction, object, method='view', msg='', error=''):
    """Commits the transaction, then redirects.

    If 'msg' is given, the message will be queued after the
    transaction successfully commits. If the commit raises
    an exception, and 'error' is given, it will be queued.
    """
    url, link = object_url(object, method), object_link(object)
    commit_url(transaction, url, msg, error, link)

def commit_url(transaction, url, msg='', error='', link=''):
    """Commits the transaction, then redirects.

    If 'msg' is given, the message will be queued after the
    transaction successfully commits. If the commit raises
    an exception, and 'error' is given, it will be queued.

    The diffrence in this method versus commit(), is usefull
    when your objected is deleted during the transaction.
    """
    try:
        transaction.commit()
    except:
        if not errormsg:
            raise
        queue_message(error, error=True, link=link)
    else:
        if msg:
            queue_message(msg, link=link)
    raise cherrypy.HTTPRedirect(url)

def struct2dict(struct):
    """Converts a SpineStruct to a python dictionary."""
    d = {}
    for attr in dir(struct):
        if attr.startswith('_'):
            continue
        d[attr] = getattr(struct, attr)
    return d

def get_account(transaction, account_id=None, account_name=None):
    """Returns a dictionary with the information about the
    given account."""
    account = {}

    assert account_id or account_name
    searcher = transaction.get_account_searcher()
    if account_id:
        searcher.set_id(account_id)
    else:
        searcher.set_name(account_id)
    acc_struct = searcher.dump()
    acc_objects = searcher.search()
    if acc_struct:
        account = struct2dict(acc_struct[0])
        acc_object = acc_objects[0]
    account['is_posix'] = acc_object.is_posix()
    account['object_type'] = _spine_type(acc_object)
    return account

# arch-tag: 046d3f6d-3e27-4e00-8ae5-4721aaf7add6
