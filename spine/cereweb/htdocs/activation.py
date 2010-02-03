# -*- encoding: utf-8 -*-

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

import urllib
import cherrypy

import cerebrum_path
import cereconf

from Cerebrum.Utils import Factory
from lib.data.AccountDAO import AccountDAO

from lib import utils
from lib import Messages
from gettext import gettext as _
from lib.Main import Main
from lib.utils import queue_message, get_messages
from lib.utils import is_correct_referer, get_referer_error
from lib.templates.ActivationTemplate import ActivationTemplate
from lib.wsidm.wsidm import WSIdm
from lib.Languages import Languages
from lib.wsidm.wsidm import WSIdm
import config
import re
from Cerebrum.modules.PasswordChecker import PasswordGoodEnoughException

logger = None

path = ['language', 'fodselsnr', 'studentnr', 'pinkode', 'eula', 'initpassword', 'welcome']

def checkParam(pname, plen, **vargs):
    param = vargs.get(pname, '')
    if not param or len(param) != plen:
        return False
    toMatch = '^\d{' + str(plen) + '}$'
    patt = re.compile(toMatch)
    if not patt.match(param):
        return False
    return True

def negotiate_encoding():
    prefered_charset = default_charset = 'utf-8'
    allowed_charsets = cherrypy.request.headerMap.get('Accept-Charset', '')
    if not allowed_charsets:
        return default_charset

    charsets = [c.strip().lower() for c in allowed_charsets.split(',')]
    if prefered_charset in charsets:
        return prefered_charset
    return charsets[0]

def get_timeout():
    """Returns the time it takes in seconds for _a_ session to time out."""
    return getattr(cereconf, 'SPINE_SESSION_TIMEOUT', 900)

def has_session():
    return cherrypy.session.get('timeout', '') and \
        cherrypy.session.get('client_encoding', '')  and \
        cherrypy.session.get('spine_encoding', '')
        
def index(**vargs):
    global logger
    global path
    logger  = Factory.get_logger('root')
    if not has_session():
        cherrypy.session['timeout'] = get_timeout()
        cherrypy.session['client_encoding'] = negotiate_encoding()
        cherrypy.session['spine_encoding'] = 'iso-8859-1'
    if not is_correct_referer():
        print 'is_correct'
        queue_message(get_referer_error(), title="Error!", error=True)
        print 'vargs =', vargs
        print 'session =', cherrypy.session
        return _retry_page(**vargs).respond()
    lang = Languages(vargs.get('lang', 'no'))
    currentPage = vargs.get('page', '')
    if currentPage == 'fodselsnr':
        if not checkParam('fnr', 11, **vargs):
            queue_message(lang.get_nin_not_legal_error_message(), error=True)
            return _retry_page(**vargs).respond()
    elif currentPage == 'studentnr':
        studentnr = vargs.get('studentnr', '')
        if not checkParam('studentnr', 6, **vargs):
            queue_message(lang.get_sid_not_legal_error_mesage(), error=True)
            return _retry_page(**vargs).respond()
    elif currentPage == 'initpassword':
        pw1 = vargs.get('pw1', '')
        pw2 = vargs.get('pw2', '')
        username = cherrypy.session.get('username', '')
        if not username:
            return _get_page('noUsernameFound', **vargs).respond()
        if username and pw1 and pw2 and pw1 == pw2 and len(pw1) > 7:
            db = Factory.get("Database")()
            db.cl_init(change_program="set_password")
            const = Factory.get("Constants")(db)

            acc = Factory.get("Account")(db)
            acc.clear()
            acc.find_by_name(username)
            try:
                acc.set_password(pw1)
            except PasswordGoodEnoughException, e:
                db.rollback()
                queue_message("Not strong enough", error=True)
                _retry_page(**vargs).respond()
            try:
                acc.write_db()
            except Exception, e:
                db.rollback()
                queue_message('The server is unavailable.',error=True)
                queue_message('If the server remains ' + \
                    ' unavailable, call (735) 91500 and notify ' + \
                    'Orakeltjenesten of the situation.', error=True)
                logger.error(e)
                _retry_page(**vargs).respond()
            try:
                db.commit()
            except Exception, e:
                db.rollback()
                queue_message('The server is unavailable.',error=True)
                queue_message('If the server remains ' + \
                    ' unavailable, call (735) 91500 and notify ' + \
                    'Orakeltjenesten of the situation.', error=True)
                logger.error(e)
                _retry_page(**vargs).respond()
            remote = cherrypy.request.headerMap.get("Remote-Addr", '')
            logger.warn(username + ' is activated. Remote-Addr = ' + remote)
        if pw1 and pw2 and pw1 == pw2 and len(pw1) < 8:
            queue_message(lang.get_setpassword_too_short_error_message(), title="Passwords too short", error=True)
            return _retry_page(**vargs).respond()
        elif pw1 != pw2:
            queue_message(lang.get_setpassword_no_match_error_message(), title="Passwords do not match", error=True)
            return _retry_page(**vargs).respond()
        elif not pw1:
            queue_message(lang.get_setpassword_no_match_error_message(), title="Passwords do not match", error=True)
            return _retry_page(**vargs).respond()
        elif not pw2:
            queue_message(lang.get_setpassword_no_match_error_message(), title="Passwords do not match", error=True)
            return _retry_page(**vargs).respond()
    elif currentPage == 'pinkode':
        pin = vargs.get('pin', '')
        if not checkParam('pin', 4, **vargs):
            queue_message(lang.get_pin_not_legal_error_message(), error=True)
            return _retry_page(**vargs).respond()
    elif currentPage == 'eula':
        godkjent_logger = vargs.get('godkjent_logger', '')
        if not godkjent_logger or godkjent_logger != 'on':
            cherrypy.session.clear()
            return _get_page('eulaNotApproved', **vargs).respond()
        else:
            fnr = cherrypy.session.get('fnr', '')
            studnr = cherrypy.session.get('studentnr', '')
            if studnr:
                studnr = int(studnr)
            bdate = int(fnr[0:6])
            ssn = int(fnr[6:])
            pin = cherrypy.session.get('pin', '');
            wsidm = WSIdm()
            ret = wsidm.checkIdentity(bdate, ssn, studnr, pin)
            if not ret:
                return _get_page('noUsernameFound', **vargs).respond()
            else:
                cherrypy.session['username'] = ret
    cherrypy.session.update(vargs)
    page = _get_next_page(**vargs)
    return page.respond()
index.exposed = True


def _get_next_page(**vargs):
    ## i do not like this code,- but it works...
    next = vargs.get('page', '')
    if not next:
        return _retry_page(**vargs)
    else:
        pp = vargs.get('page', path[-1])
        next = (path.index(pp) + 1 % len(path))
        next = path[next]
    return _get_page(next, **vargs)

def _get_page(name, **vargs):
    ## print 'name =', name
    try:
        page = ActivationTemplate()
        page.vargs = vargs
        page.content = getattr(page, name)
    except Exception, e:
        page = object
        page.respond = lambda x: [str(e)]
    return page

def _retry_page(**vargs):
    return _get_page(vargs.get('page', path[0]), **vargs)

