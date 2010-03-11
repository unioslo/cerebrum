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

from gettext import gettext as _
import gettext
import time
import urllib
import urlparse
import mx.DateTime
import cherrypy
import re
import cgi
import string
import random
from datetime import datetime
import Messages

from Cerebrum import Utils
Database = Utils.Factory.get("Database")

from lib.data.AccountDAO import AccountDAO
from lib.data.EntityFactory import EntityFactory

def get_referer():
    return cherrypy.request.headers.get('Referer','')
    
def get_host():
    host = cherrypy.request.headers.get('X-Forwarded-Host', '')
    if not host:
        host = cherrypy.request.headers.get('Host', '')
    return host

def get_method():
    return cherrypy.request.method.strip()

def get_referer_error():
    return 'Somebody is trying to do something nasty.  Referer from: %s' % get_referer()

def is_correct_referer():
    approved = False
    if 'POST' == get_method():
        ref_loc = urlparse.urlparse(get_referer()).netloc
        hostname = get_host()
        if hostname and ref_loc:
            if ref_loc.startswith(hostname):
                approved = True
    else:
        approved = True
    return approved

def get_content_type():
    client_charset = cherrypy.session.get('client_encoding', 'utf-8')
    content_type = 'application/xhtml+xml; charset=%s' % client_charset
    user_agent = cherrypy.request.headerMap['User-Agent']
    if user_agent.rfind('MSIE') != -1:
        content_type = 'text/html; charset=%s' % client_charset
    return content_type

def get_pragma():
    return 'no-cache'

def get_cache_control():
    return 'private, no-cache, no-store, must-revalidate, max-age=0'

def clean_url(url):
    """Make sure the url doesn't point to a different server."""
    if not url:
        return ''
    # Urlparse splits an url into 6 parts:
    #  <scheme>://<netloc>/<path>;<params>?<query>#<fragment>
    url = ('', '') + urlparse.urlparse(url)[2:]
    return urlparse.urlunparse(url)

def entity_url(entity, method="view", **params):
    """Return the full path to a page treating the entity.

    Method could be "view" (the default), "edit" and other things.

    Any additional keyword arguments will be appended to the query part.
    """
    if not isentity(entity):
        entity = EntityFactory().get_entity(entity)
    return create_url(entity.id, entity.type_name, method, **params)

def create_url(entity_id, entity_type, method="view", **params):
    params['id'] = entity_id
    params = urllib.urlencode(params)

    map = {
        'email_target': 'emailtarget',
        'email_domain': 'email',
    }

    type_name = map.get(entity_type, entity_type)
    return cgi.escape("/%s/%s?%s" % (type_name, method, params))

def entity_link(entity, text=None, method="view", _class="", **params):
    """Create a HTML anchor (a href=..) for the entity.

    The text of the anchor will be entity.name - unless
    the parameter text is given.

    Any additional keyword arguments will be appended to the query part.
    """
    if not isentity(entity):
        entity = EntityFactory().get_entity(entity)

    url = entity_url(entity, method, **params)
    if text is None:
        text = entity.name
    if _class:
        _class = ' class="%s"' % _class
    return '<a href="%s"%s>%s</a>' % (url, _class, spine_to_web(text))

def isentity(entity):
    return hasattr(entity, 'id')

def redirect(url, status=None):
    url = clean_url(url)
    raise cherrypy.HTTPRedirect(url, status)

def redirect_entity(entity, method="view", status=None):
    url = entity_url(entity, method)
    redirect(url, status)

def queue_message(message=None, error=False, link='', title="No title", tracebk=None):
    """Queue a message.

    The message will be displayed next time a Main-page is showed.
    If error is true, the message will be indicated as such.
    Link is used in activitylog so the user knows which
    object the action was on, should be a string linking to
    the object.
    """

    Messages.queue_message(
        title=title,
        message=message,
        is_error=error,
        link=link,
        tracebk=tracebk
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
        return mx.DateTime.strptime(date, format)
    else:
        return None

def get_date(tr, sDate):
    return strptime(tr, sDate.strip(), "%Y-%m-%d")

def parse_date(date):
    if not date: return None
    return get_date(None, date)

def has_valid_session():
    """Tries to ping the server.  Returns True if we've got
    contact, False otherwise."""
    return cherrypy.session.get("username") and True or False

def session_required_decorator(method):
    def fn(*args, **vargs):
        if not has_valid_session():
            redirect_to_login()

        cherrypy.session['timestamp'] = time.time()
        return method(*args, **vargs)
    return fn

def redirect_to_login():
    query = cherrypy.request.path
    if cherrypy.request.queryString:
        query += '?' + cherrypy.request.queryString

    cherrypy.session['next'] = query
    redirect('/login')

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

def get_section(page):
    map = {
        'motd': 'index',
    }
    return map.get(page, page)

def get_tabs(current=None):
    tabs = [
      ('Cereweb', 'index', '/index'),
      ('Persons', 'person', '/person'),
      ('Accounts', 'account', '/account'),
      ('Groups', 'group', '/group'),
      ('Organization units', 'ou', '/ou'),
      ('Hosts', 'host', '/host'),
      ('Disks', 'disk', '/disk'),
      ('Email', 'email', '/email'),
      ('Search', 'search', '/search'),
      ('Logout', 'logout', '/logout'),
    ]

    html = '<li%s><a href="%s"><em>%s</em></a></li>'
    res = []

    current = get_section(current)
    for (name, page, link) in tabs:
        selected = page == current and ' class="selected"' or ''
        res.append(html % (selected, link, name))
    return "\n".join(res)

def get_links(page):
    map = {
        'index': (
            ('/index', _('Index')),
            ('/motd/all', _('View all messages')),
            ('/entity/global_historylog', _('View recent changes')),
        ),
        'person': (
            ('/person/search/', _('Search')),
            ('/person/create/', _('Create')),
        ),
        'account': (
            ('/account/search/', _('Search')),
        ),
        'group': (
            ('/group/search/', _('Search')),
            ('/group/create/', _('Create')),
        ),
        'ou': (
            ('/ou/tree/', _('Tree')),
            ('/ou/create/', _('Create')),
        ),
        'host': (
            ('/host/search/', _('Search')),
            ('/host/create/', _('Create')),
        ),
        'disk': (
            ('/disk/search/', _('Search')),
            ('/disk/create/', _('Create')),
        ),
        'email': (
            ('/email/search/', _('Search')),
            ('/email/create/', _('Create')),
        ),
    }
    section = get_section(page)
    return map.get(section, ())

def flatten(elem, perspective_type):
    output = [elem]
    for ou in elem.get_children(perspective_type):
        output += flatten(ou, perspective_type)
    return output

def ou_selects(elem, perspective_type, indent=""):
    output = []
    id = html_quote(elem.get_id())
    name = indent + spine_to_web(elem.get_name())
    output += [(id, name)]
    for ou in elem.get_children(perspective_type):
       output += ou_selects(ou, perspective_type, "&nbsp;&nbsp;&nbsp;" + indent)
    return output

def create_ou_selection_tree(elem, indent="", output=[]):
    if isinstance(elem, list):
        for root in elem:
            create_ou_selection_tree(root, indent, output)
        return output

    name = indent + spine_to_web(elem.name)
    output.append((elem.id, name))

    indent = ("&nbsp;" * 3) + indent;
    for child in elem.children:
        create_ou_selection_tree(child, indent, output)
    return output

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
                        city=address.get_city(),
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
    if not s: return ""
    return cgi.escape(str(s)).replace('"', '&quot;')

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
    charsets = [string.ascii_lowercase, string.ascii_uppercase, string.digits]

    result = ''
    for i in range(length):
        if i < len(charsets):
            chars = charsets[i]
        else:
            choice = random.randint(0, 10) % len(charsets)
            chars = charsets[choice]

        result += getsalt(chars,1)
    return result

def get_spine_encoding():
    return cherrypy.session['spine_encoding']

def is_ajax_request():
    return cherrypy.request.headerMap.get('X-Requested-With', "") == "XMLHttpRequest"

def get_client_encoding():
    if is_ajax_request(): return "utf-8"
    return cherrypy.session['client_encoding']

def can_decode_encode(string):
    return hasattr(string, 'decode') and hasattr(string, 'encode')
    
def spine_to_web(string):
    if not string: return ""
    if can_decode_encode(string):
        return to_web_encode(from_spine_decode(html_quote(string)))
    return string

def web_to_spine(string):
    if not string: return ''
    if can_decode_encode(string):
        return to_spine_encode(from_web_decode(string))
    return string

def from_spine_decode(string):
    if not string: return ''
    return string.decode(get_spine_encoding())

def to_spine_encode(string):
    if not string: return ''
    return string.encode(get_spine_encoding())

def from_web_decode(string):
    if not string: return ''
    return string.decode(get_client_encoding())

def to_web_encode(string):
    if not string: return ''
    return string.encode(get_client_encoding())

def encode_args(args):
    retStr= ''
    for k in args.keys():
        value = str(args[k])
        if retStr:
            retStr += '&amp;'
        retStr += k + '='
        if value:
            retStr += value
    return retStr

def get_lastname_firstname(pers):
    lastname = None
    firstname = None
    fullname = None
    found = None
    for name in pers.get_names():
        if name.get_name_variant().get_name() == 'LAST':
            lastname = name.get_name()
        if name.get_name_variant().get_name() == 'FIRST':
            firstname = name.get_name()
        if name.get_name_variant().get_name() == 'FULL':
            fullname  = name.get_name()
    if lastname and firstname:
        found = lastname + ", " + firstname
    elif fullname:
        found = fullname
    elif lastname:
        found = lastname
    elif firstname:
        found = firstname
    return found

def nl2br(string):
    string = string or ""
    return string.replace('\n', '<br />')

def quotedate(date):
    if not date: return ''
    return html_quote(strftime(date, "%Y-%m-%d"))

def quotetimestamp(date):
    if not date: return ''
    return html_quote(strftime(date, "%Y-%m-%d %H:%M:%S"))

def get_database():
    db = Database()
    userid = cherrypy.session.get("userid")
    db.cl_init(change_by = userid)
    return db

def timer_decorator(fn):
    def func(*args, **kwargs):
        t = time.time()
        retval = fn(*args, **kwargs)
        delta = time.time() - t
        print "%s used %s seconds." % (fn.__name__, delta)
        return retval
    return func

def get_translation(name, localedir, lang):
    tr = None
    try:
        tr = gettext.translation(name, localedir, languages=[lang])
        cherrypy.session['lang'] = lang
    except Exception, e:
        ## fall back to default translation
        tr = gettext
    return tr.gettext

def negotiate_lang(**vargs):
    default_lang = 'en'
    legal_langs = ['no', 'en']
    lang = vargs.get('lang')
    if lang:
        lang = lang.lower()
        if lang in legal_langs:
            return lang
        else:
            return default_lang
    lang = cherrypy.session.get('lang')
    if lang:
        return lang.lower()
    header_langs = cherrypy.request.headerMap.get('Accept-Language')
    tmp = [c.strip().lower() for c in header_langs.split(';')]
    accepted_langs = []
    for part in tmp:
        dd = [c.strip().lower() for c in part.split(',')]
        accepted_langs += dd
    for legal in legal_langs:
        if legal in accepted_langs:
            return legal
    return default_lang
