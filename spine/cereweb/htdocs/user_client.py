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
from lib.templates.UserTemplate import UserTemplate
from lib.templates.MailUserTemplate import MailUserTemplate
import SpineIDL

def _get_links():
    return (
        ('index', _('Index')),
        ('mail', _('Mail')),
        ('/logout', _('Logout')),
    )

def index(transaction):
    try:
        page = UserTemplate()
        username = cherrypy.session.get('username', '')
        account = get_user_info(transaction,username)
        page.tr = transaction
        page.account = account
        if not page.messages:
            page.messages = get_messages()
        page.set_focus('index/')
        page.links = _get_links()
        return page.respond()
    except SpineIDL.Errors.AccessDeniedError, e:
        return [str(e)]
index = transaction_decorator(index)
index.exposed = True

def get_user_info(transaction,username):
    user = {}
    account = transaction.get_commands().get_account_by_name(username)
    my_id = account.get_id()
    username = account.get_name()
    owner = account.get_owner()
    owner_type = account.get_owner_type().get_name()
    expire_date = ''
    if owner_type == 'person':
        fullname = owner.get_cached_full_name()
        birthdate = owner.get_birth_date().strftime('%Y-%m-%d')
        is_quarantined = owner.is_quarantined()
    else:
        fullname = owner.get_name()
        birthdate = ''
        is_quarantined = ''
    user = {'id':my_id,'username':username,'fullname':fullname,'expire_date':expire_date,
            'birthdate':birthdate,'quarantined':is_quarantined,'external_id': [], 'spreads': [], 'groups': [], 'affiliations': []}
    if owner_type == 'person':
        extids = owner.get_external_ids()
        for extid in extids:
            extid_type = extid.get_id_type().get_name()
            extid_type_description = extid.get_id_type().get_description()
            external_id = extid.get_external_id()
            extdict = {'extid_type': extid_type,'extid_type_description':extid_type_description,'external_id': external_id}
            user['external_id'].append(extdict)
    spreads = account.get_spreads()
    for spread in spreads:
        user['spreads'].append((spread.get_name(), spread.get_description()))
    groups = account.get_groups()
    for group in groups:
        user['groups'].append((group.get_name(), group.get_description()))
    affiliations = account.get_owner().get_affiliations()
    for affiliation in affiliations:
        user['affiliations'].append((affiliation.get_affiliation().get_name(), affiliation.get_status().get_description(), affiliation.get_ou().get_name()))
    return user

def mail(transaction):
    page = MailUserTemplate()
    username = cherrypy.session.get('username', '')
    account = transaction.get_commands().get_account_by_name(username)
    page.tr = transaction
    page.account = get_user_info(transaction, username)
    page.vacations = get_vacations(transaction, account)
    page.forwards = get_forwards(transaction, account)
    if not page.messages:
        page.messages = get_messages()

    page.set_focus("/mail")
    page.links = _get_links()
    res = str(page)
    return [res]
mail = transaction_decorator(mail)
mail.exposed = True

def add_vacation(transaction, **kwargs):
    if not len(kwargs) == 4:
        redirect('/user_client/mail')

    username = kwargs.get('username')
    start = kwargs.get('start')
    end = kwargs.get('end')
    alias = kwargs.get('alias')

    msg = ''
    if not start:
        msg = 'Start date is empty.'
    elif not utils.legal_date(start):
        msg='Start date is not a legal date (YYYY-MM-DD).'
    if not msg and end:
        if not utils.legal_date(end):
            msg = 'End date is not a legal date (YYYY-MM-DD).'
    if not msg and not alias:
        msg = 'Alias is empty.'
    else:
        if len(alias) > 256:
            msg = 'Alias is too long ( max. 256 characters).'
    if not msg:
        msg = 'Vacation added.'
        error = False
    else:
        error = True

    rollback_url('/user_client/mail', msg, err=error)
add_vacation = transaction_decorator(add_vacation)
add_vacation.exposed = True

def add_forward(transaction, **kwargs):
    if not len(kwargs) == 4:
        redirect('/user_client/mail')

    username = kwargs.get('username')
    start = kwargs.get('start')
    end = kwargs.get('end')
    forward = kwargs.get('forward')

    msg = ''
    if not start:
        msg = 'Start date is empty.'
    elif not utils.legal_date(start):
        msg = 'Start date is not a legal date (YYYY-MM-DD).'
    if not msg and end:
        if not utils.legal_date(end):
            msg = 'End date is not a legal date (YYYY-MM-DD).'
    if not msg and not forward:
        msg = 'Forward is empty.'
    elif len(forward) > 256:
        msg = 'Forward is too long ( max. 256 charcters).'
    if not msg:
        msg = 'Forward added.'
        error = False
    else:
        error = True

    rollback_url('/user_client/mail', msg, err=error)
add_forward = transaction_decorator(add_forward)
add_forward.exposed = True

def get_vacations(tr,acc):
    vacations = []
    vacs = get_vacations_helper(tr, acc)
    for vacation in vacs:
        target_id = vacation.get_target().get_id()
        start_date = vacation.get_start_date().to_string()
        end_date = vacation.get_end_date()
        if end_date:
            end_date = end_date.to_string()
        else:
            end_date = ''
        text = vacation.get_vacation_text()
        enabled = vacation.get_enable()
        vacations.append({'id':target_id,'start_date':start_date,'end_date':end_date,'text':text,'enabled':enabled})
    return vacations

def get_forwards(tr,acc):
    forwards = []
    fwds = get_forwards_helper(tr, acc)
    for forward in fwds:
        target_id = forward.get_target().get_id()
        start_date = forward.get_start_date().to_string()
        end_date = forward.get_end_date()
        if end_date:
            end_date = end_date.to_string()
        else:
            end_date = ''
        address = forward.get_forward_to()
        enabled = forward.get_enable()
        forwards.append({'id':target_id,'start_date':start_date,'end_date':end_date,'address':address,'enabled':enabled})
    return forwards

def get_email_targets_helper(tr, account):
    ts = tr.get_email_target_searcher()
    ts.set_entity(account)
    return ts.search()

def get_forwards_helper(tr, account):
    forwards = []
    targets = get_email_targets_helper(tr, account)
    if not targets:
        return []
    for target in targets:
        fwds = target.get_forwards()
        if fwds:
            forwards.extend(fwds)
    return forwards
    
def get_vacations_helper(transaction, account):
    vacations = []
    targets = get_email_targets_helper(transaction, account)
    if not targets: 
        return []
    for target in targets:
        vacs = target.get_vacations()
        if vacs:
            vacations.extend(vacs)
    return vacations

def set_password(transaction, **vargs):
    myId = vargs.get('id')
    pass1 = vargs.get('passwd1')
    pass2 = vargs.get('passwd2')
    if myId and pass1 and pass2 and pass1 == pass2:
        account = transaction.get_account(int(myId))
        account.set_password(pass1)
        transaction.commit()
        queue_message("Password changed successfully")
    elif (not myId):
        queue_message("Account-Id missing. Missing transaction?",error=True)
    elif (not pass1):
        queue_message("Passwords doesn't match",error=True)
    elif ( not pass2):
        queue_message("Passwords doesn't match.",error=True)
    elif ( not pass1 == pass2 ):
        queue_message("Passwords doesn't match",error=True)
    else:
        queue_message("Something went very wrong!", error=True)
    utils.redirect('/user_client/')
set_password = transaction_decorator(set_password)
set_password.exposed = True

