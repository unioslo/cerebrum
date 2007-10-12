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
import urlparse
import mx.DateTime
import cherrypy
import re
import cgi
import string
import random
from omniORB import CORBA
from datetime import datetime
import Messages

def clean_url(url):
    """Make sure the url doesn't point to a different server."""
    if not url:
        return ''
    # Urlparse splits an url into 6 parts:
    #  <scheme>://<netloc>/<path>;<params>?<query>#<fragment>
    url = ('', '') + urlparse.urlparse(url)[2:]
    return urlparse.urlunparse(url)

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
        return object.get_typestr()
    else:
        # split up "IDL:SpineIDL/SpineEntity:1.0"
        idl_type = object._NP_RepositoryId.split(":", 3)[1]
        spine_type = idl_type.split("/")[1]
        # The Spine prefix is not important
        name = spine_type.replace("Spine", "")
        return name.lower()

def object_name(object):
    ##type = object.get_type().get_name()
    type = object.get_typestr()
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
            text = "Email target of type '%s'" % object.get_target_type()
        else:
            primary_address = object.get_primary_address()
            if primary_address:
                text = primary_address.full_address() + " (%s)" % object.get_target_type()
            else:
                text = "No primary address" + " (%s)" % object.get_target_type()
    elif type == 'disk':
        text = object.get_path()
    elif type == 'project':
        text = object.get_title() or \
                "(untitled %d)" % (object_id(object),)
    elif type == 'allocation':
        text = object.get_allocation_name().get_name()
    elif hasattr(object, "get_name"):
        text = object.get_name()   
    elif type == 'account':
        text = object['name']
    else:
        text = str(object)
    return text

def object_id(object):
    if type(object) == type({}):
        return object['id']
    else:
        return object.get_id()

def object_url(object, method="view", **params):
    """Return the full path to a page treating the object.
    
    Method could be "view" (the default), "edit" and other things.
    
    Any additional keyword arguments will be appended to the query part.
    """
    object_type = _spine_type(object)

    params['id'] = object_id(object)

    if object_type == 'emaildomain':
        object_type = 'email'

    params = urllib.urlencode(params)
    return cgi.escape("/%s/%s?%s" % (object_type, method, params))

def object_link(object, text=None, method="view", _class="", **params):
    """Create a HTML anchor (a href=..) for the object.

    The text of the anchor will be str(object) - unless
    the parameter text is given.

    Any additional keyword arguments will be appended to the query part.
    """
    url = object_url(object, method, **params)
    if text is None:
        text = object_name(object)
    if _class:
        _class = ' class="%s"' % _class
    return '<a href="%s"%s>%s</a>' % (url, _class, cgi.escape(text))

def remember_link(object, text='remember', _class=''):
    obj_id = object_id(object)
    url = urllib.quote("/worklist/remember?id=%i" % obj_id)
    return '<a class="action jsonly %s" href="%s">%s</a>' % (_class, url, text)

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

def queue_message(message=None, error=False, link=''):
    """Queue a message.
    
    The message will be displayed next time a Main-page is showed.
    If error is true, the message will be indicated as such.
    Link is used in activitylog so the user knows which
    object the action was on, should be a string linking to
    the object.
    """

    Messages.queue_message(
        title='No title',
        message=message,
        is_error=error,
        link=link
    )

def get_messages():
    return Messages.get_messages()

def strftime(date, format="%Y-%m-%d", default=''):
    """Returns a string for the date.

    If date evaluates to true its formated with the 'format' string.
    Else the value of default will be returned.
    """
    return date and html_quote(date.strftime(format)) or html_quote(default)

def strptime(tr, date, format="%Y-%m-%d"):
    """Returns a Date obj for the date-string."""
    if date:
        return tr.get_commands().strptime(date, format)
    else:
        return None

def get_date(tr, sDate):
    return strptime(tr, sDate.strip(), "%Y-%m-%d")

def has_valid_session():
    """Tries to ping the server.  Returns True if we've got
    contact, False otherwise."""
    try:
        cherrypy.session['session'].ping()
    except (CORBA.COMM_FAILURE, CORBA.TRANSIENT, KeyError), e:
        return False
    return True

def new_transaction():
    if not has_valid_session():
        Messages.queue_message(
                title="Session Expired",
                message='Your session is no longer available.  Please log in again.',
                is_error=True)
        redirect_to_login()
    return cherrypy.session['session'].new_transaction()

def redirect_to_login():
        query = cherrypy.request.path
        if cherrypy.request.queryString:
            query += '?' + cherrypy.request.queryString

        cherrypy.session['next'] = query
        redirect('/login')

def transaction_decorator(method):
    def transaction_decorator(*args, **vargs):
        cherrypy.session['timestamp'] = time.time()
        tr = new_transaction()
        # In Python < 2.5, try...except...finally did not work.
        # try...except had to be nested in try...finally.
        try:
            from SpineIDL.Errors import AccessDeniedError
            try:
                return method(transaction=tr, *args, **vargs)
            except AccessDeniedError, e:
                Messages.queue_message(
                        title="Access Denied",
                        message=e.explanation,
                        is_error=True)
                redirect(cherrypy.session.get('client'))
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
    except Exception, e:
        Messages.queue_message(
            title="Commit Failed",
            message=error,
            is_error=True,
            link=link,
            tracebk=e)
    else:
        if msg:
            Messages.queue_message(
                title="Commit Success",
                message=msg,
                link=link)
    raise cherrypy.HTTPRedirect(url)

def rollback_url(url, msg, err=False):
    if msg:
        Messages.queue_message(
            title="Did Not Save",
            message=msg,
            is_error=err)
    raise cherrypy.HTTPRedirect(url)
	
def legal_date(datestr, formatstr="%Y-%m-%d"):
    try:
        mx.DateTime.strptime(datestr.strip(), formatstr)
        return True
    except:
        return False

def legal_domain_format( domain ):
    pat=re.compile( '^(([a-zA-Z0-9]([a-zA-Z0-9]|\-)*)\.)*([a-zA-Z0-9]([a-zA-Z0-9]|\-[a-zA-Z0-9])*)\.[a-zA-Z]{2,7}$')
    if not pat.match(domain):
        return False
    return True

def legal_emailname( name ):
    pat = re.compile('^([a-zA-Z0-9]([a-zA-Z0-9]|((\_|\-|\.)[a-zA-Z0-9]))*)$')
    if not pat.match( name ):
        return False
    return True

def legal_domain_chars( domain ):
    rest=re.sub('\-*\.*','',domain)
    if not rest.isalnum():
        return False
    return True

def unlegal_name(name):
    if not name:
        return 'Name is empty.'
    if len(name) > 256:
        return 'Name too long; max 256 characters.'
    if name != html_quote(name):
        return 'Name contains unlegal characters.'
    return ''

def strip_html(title):
    """Removes html from the title"""
    return re.sub(r'<[^!>](?:[^>]|\n)*>', '', title)

def format_title(title):
    return strip_html(title)

def valid_search(*args, **vargs):
    valid = False
    for i in args:
        if i in vargs and vargs[i] != '':
            valid = True
            break
    return valid

def get_tabs(current=None):
    tabs = [
      ('cereweb', '/index'),
      ('person', '/person'),
      ('account', '/account'),
      ('group', '/group'),
      ('ou', '/ou'),
      ('host', '/host'),
      ('disk', '/disk'),
      ('email', '/email'),
      ('options', '/options'),
      ('logout', '/logout'),
    ]
    html = '<li%s><a href="%s"><em>%s</em></a></li>'
    res = []
    for (name, link) in tabs:
        selected = name == current and ' class="selected"' or ''
        res.append(html % (selected, link, name))
    return "\n".join(res)

def flatten(list, perspective, res=[]):
    if not list:
        return res
    ou = list.pop(0)
    res.append(ou)
    return flatten(ou.get_children(perspective), perspective, res)


#
# namelist does not really belong here...

class nvsobj(object):
    def __init__(self, value, variant):
        self.value=value
        if variant: self.variant=variant
        self.sources=[]

class vstruct(object):
    def __init__(self, **kw):
        self._data = kw
        l=kw.items()
        l.sort()
        self._hash = tuple(l).__hash__()
    def __eq__(self, other):
        return self._data == other._data
    def __hash__(self):
        return self._hash
    def __getattr__(self, attr):
        if attr == '_data':
            return self._data
        else:
            return self._data.get(attr)


def namelist(person):
    names = []
    variants = {}
    for name in person.get_names():
        variant = name.get_name_variant()
        source = name.get_source_system()
        value = name.get_name()
        if not variant in variants:
            variants[variant] = {}
        if not value in variants[variant]:
            name = nvsobj(value, variant)
            names.append(name)
            variants[variant][value] = name
        variants[variant][value].sources.append(source)
    return names

def extidlist(entity):
    extids = []
    variants = {}
    for extid in entity.get_external_ids():
        variant = extid.get_id_type()
        source = extid.get_source_system()
        value = extid.get_external_id()
        if not variant in variants:
            variants[variant] = {}
        if not value in variants[variant]:
            extid = nvsobj(value, variant)
            extids.append(extid)
            variants[variant][value] = extid
        variants[variant][value].sources.append(source)
    return extids

def contactlist(entity):
    contacts = []
    variants = {}
    for contact in entity.get_all_contact_info():
        variant = contact.get_type()
        source = contact.get_source_system()
        pref = contact.get_preference()
        value = contact.get_value()
        if not variant in variants:
            variants[variant] = {}
        if not value in variants[variant]:
            contact = nvsobj(value, variant)
            contacts.append(contact)
            variants[variant][value] = contact
        variants[variant][value].sources.append((source, pref))
    return contacts


def addresslist(entity):
    addresses = []
    variants = {}
    for address in entity.get_addresses():
        variant = address.get_address_type()
        source = address.get_source_system()
        value = vstruct(address_text=address.get_address_text(),
                        p_o_box=address.get_p_o_box(),
                        postal_number=address.get_postal_number(),
                        city=address.get_country(),
                        country=address.get_country())
        if not variant in variants:
            variants[variant] = {}
        if not value in variants[variant]:
            address = nvsobj(value, variant)
            addresses.append(address)
            variants[variant][value] = address
        variants[variant][value].sources.append(source)
    return addresses


def shownumber(n):
    """Unspinify number"""
    assert(isinstance(n, int) or isinstance(n, float))
    if (n == -1):
        return ''
    else:
        return str(n)

def html_quote(s):
    """ maybe add more characters that need quoting later... """
    return cgi.escape(str(s))

def url_quote(s):
    return urllib.quote(str(s))

def getsalt(chars = string.letters + string.digits, length=16):
    salt = ''
    for i in range(int(length)):
        salt += random.choice(chars)
    return salt

def randpasswd(length=8):
    """ Returns a random password at a given length based on a character set. 
    """
    result = ''
    az = string.ascii_lowercase
    AZ = string.ascii_uppercase
    dig = string.digits
    chars = az + AZ + dig
    # FIXME: Make shure passwords are according to the passwd-regexp
    for i in range(length):
        result += getsalt(chars,1)
    return result
