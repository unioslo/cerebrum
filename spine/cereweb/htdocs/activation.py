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

from lib import utils
from gettext import gettext as _
from lib.Main import Main
from lib.utils import commit, commit_url, queue_message, object_link
from lib.utils import transaction_decorator, redirect, redirect_object
from lib.utils import get_messages, rollback_url
from lib.templates.ActivationTemplate import ActivationTemplate
from lib import CallWSIdm
from lib.Languages import Languages

import config
import SpineIDL
import SpineClient

def _login():
    Spine = SpineClient.SpineClient(config=config.conf)
    spine = Spine.connect()
    service_user = config.conf.get('SpineClient','activation_user')
    server_pw = config.conf.get('SpineClient','activation_password')
    return spine.login(service_user,server_pw)

def _get_session():
    cps = cherrypy.session
    ss = cps.get('session') 
    if not ss:
        ss = cps['session'] = _login()
    ss.set_encoding("utf-8")
    return ss

def checkParam(pname, plen, **vargs):
    param = vargs.get(pname, '')
    if not param or len(param) != plen:
        return False
    return True

def index(**vargs):
    session = _get_session()
    tr = session.new_transaction()
    lang = Languages(vargs.get('lang', ''))
    page = None
    print 'post-args: %s' % vargs
    print 'session-args: %s' % cherrypy.session
    currentPage = vargs.get('page', '')
    if currentPage == 'fodselsnr':
        if not checkParam('fnr', 11, **vargs):
            queue_message(lang.get_nin_not_legal_error_message(), error=True)
            page = _get_page(tr, 'fodselsnr', **vargs)
    elif currentPage == 'studentnr':
        studentnr = vargs.get('studentnr', '')
        if not checkParam('studentnr', 6, **vargs):
            queue_message(lang.get_sid_not_legal_error_mesage(), error=True)
            page = _get_page(tr, 'studentnr', **vargs)
    elif currentPage == 'initpassword':
        pw1 = vargs.get('pw1', '')
        pw2 = vargs.get('pw2', '')
        username = vargs.get('username', '')
        if username and pw1 and pw2 and pw1 == pw2 and ln(pw1) > 7:
            pass           
        elif not username:
            pass
        elif pw1 and pw2 and pw1 == pw2 and len(pw1) < 8 or:
            queue_message(lang.get_setpassword_too_short_error_message(), error=True)
            page = _get_page(tr, 'initpassword', **vargs)
        elif pw1 != pw2:
            queue_message(lang.get_setpassword_no_match_error_message(), error=True)
            page = _get_page(tr, 'initpassword', **vargs)
        elif not pw1:
            queue_message(lang.get_setpassword_no_match_error_message(), error=True)
            page = _get_page(tr, 'initpassword', **vargs)
        elif not pw2:
            queue_message(lang.get_setpassword_no_match_error_message(), error=True)
            page = _get_page(tr, 'initpassword', **vargs)
        else:
             pass
    elif currentPage == 'pinkode':
        pin = vargs.get('pin', '')
        if not checkParam('pin', 4, **vargs):
            queue_message(lang.get_pin_not_legal_error_message(), error=True)
            page = _get_page(tr, 'pinkode', **vargs)
    elif currentPage == 'eula':
        godkjent_logger = vargs.get('godkjent_logger', '')
        if not godkjent_logger or godkjent_logger != 'on':
            page = _get_page(tr, 'eulaNotApproved', **vargs)
        else:
            fnr = vargs.get('fnr', '')
            studnr = vargs.get('studentnr', '')
            pin = vargs.get('pin', '');
            godkjent_logger = vargs.get('godkjent_logger', '')
            bdate = fnr[0:6]
            ssn = fnr[6:]
            print '++++++++++++++++++++++++++++++++++'
            print 'bdate = ', bdate
            print 'ssn = ', ssn
            print 'studnr = ', studnr
            print 'pin = ', pin
            print 'godkjent_logger = ', godkjent_logger
            bdate = '281086'
            ssn = '33745'
            studnr = '702750'
            pin = '4599'
            ret = CallWSIdm.checkIdentity(bdate, ssn, studnr, pin)
            if ret:
                vargs['username'] = ret
            else:
                page = _get_page(tr, 'noUsernameFound', **vargs)
    if not page:
        try:
            page = _get_next_page(tr, **vargs)
            ## cherrypy.session.update(vargs)
        except Exception, e:
            v = dict(cherrypy.session)
            page = _retry_page(tr, **v)
            queue_message(str(e))

    cherrypy.session.update(vargs)
    tr.rollback()
    return page.respond()
index.exposed = True


path = ['language', 'fodselsnr', 'studentnr', 'pinkode', 'eula', 'initpassword', 'welcome']
def _get_next_page(tr, **vargs):
    pp = vargs.get('page', path[-1])
    next = (path.index(pp) + 1 % len(path))
    next = path[next]

    return _get_page(tr, next, **vargs)

def _get_page(tr, name, **vargs):
    lang = vargs.get('lang','')
    try:
        page = ActivationTemplate()
        page.vargs = vargs
        page.content = getattr(page, name)
    except SpineIDL.Errors.AccessDeniedError, e:
        page = object
        page.respond = lambda x: [str(e)]
    return page

def _retry_page(tr, **vargs):
    return _get_page(tr, vargs.get('page', path[0]), **vargs)

