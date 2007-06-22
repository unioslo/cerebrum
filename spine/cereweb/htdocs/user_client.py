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
    account = transaction.get_commands().get_account_by_name(username)
    owner = account.get_owner()
    owner_type = account.get_owner_type().get_name()
    expire_date = account.get_expire_date()
    expire_date = expire_date and expire_date.strftime('%Y-%m-%d') or ''
    
    if owner_type == 'person':
        fullname = owner.get_cached_full_name()
        birthdate = owner.get_birth_date().strftime('%Y-%m-%d')
        is_quarantined = owner.is_quarantined()
        affiliations = owner.get_affiliations()
    else:
        fullname = owner.get_name()
        birthdate = ''
        is_quarantined = ''
        affiliations = []

    user = {
        'id': account.get_id(),
        'username': username,
        'fullname': fullname,
        'expire_date': expire_date,
        'is_expired': account.is_expired(),
        'birthdate': birthdate,
        'quarantined': is_quarantined,
        'external_id': [],
        'spreads': [],
        'groups': [],
        'affiliations': [],
    }

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
    for affiliation in affiliations:
        user['affiliations'].append((affiliation.get_affiliation().get_name(), affiliation.get_status().get_description(), affiliation.get_ou().get_name()))
    return user

def mail(transaction):
    page = MailUserTemplate()
    username = cherrypy.session.get('username', '')
    account = transaction.get_commands().get_account_by_name(username)
    page.account = get_user_info(transaction, username)
    page.emailtargets = account.get_email_targets()
    if not page.messages:
        page.messages = get_messages()

    page.set_focus("/mail")
    page.links = _get_links()
    res = str(page)
    return [res]
mail = transaction_decorator(mail)
mail.exposed = True

def delete_vacation(transaction, id, start):
    cs = transaction.get_commands()
    email_target = transaction.get_email_target(int(id))
    email_target.remove_vacation(cs.strptime(start, '%Y-%m-%d'))
    transaction.commit()
    queue_message("Vacation deleted successfully.")
    redirect('/user_client/mail')
delete_vacation= transaction_decorator(delete_vacation)
delete_vacation.exposed = True

def delete_forward(transaction, id, forward):
    email_target = transaction.get_email_target(int(id))
    email_target.remove_forward(forward)
    transaction.commit()
    queue_message("Forward deleted successfully.")
    redirect('/user_client/mail')
delete_forward= transaction_decorator(delete_forward)
delete_forward.exposed = True
    
def add_vacation(transaction, start, end, alias, target):
    
    if not start:
        msg = 'Start date is empty.'
        rollback_url('/user_client/mail', msg, err=True)
    if not utils.legal_date(start):
        msg='Start date is not a legal date (YYYY-MM-DD).'
        rollback_url('/user_client/mail', msg, err=True)
    if not end:
        msg = 'End date is empty.'
        rollback_url('/user_client/mail', msg, err=True)
    if not utils.legal_date(end):
        msg = 'End date is not a legal date (YYYY-MM-DD).'
        rollback_url('/user_client/mail', msg, err=True)
    if not alias:
        msg = 'Alias is empty.'
        rollback_url('/user_client/mail', msg, err=True)
    if len(alias) > 256:
        msg = 'Alias is too long ( max. 256 characters).'
        rollback_url('/user_client/mail', msg, err=True)
    if not target:
        msg = 'Target-identity is missing.'
        rollback_url('/user_client/mail', msg, err=True)
    email_target = transaction.get_email_target(int(target))
    start_date = transaction.get_commands().strptime(start, '%Y-%m-%d')
    end_date = transaction.get_commands().strptime(end, '%Y-%m-%d')
    try:
        email_target.add_vacation(start_date, alias, end_date)
        transaction.commit()
    except SpineIDL.Errors.IntegrityError, e:
        msg = 'Could not save vacation,- a possible reason is identical vacations.'
        rollback_url('/user_client/mail', msg, err=True)
    queue_message('Vacation successfully added.') 
    redirect('/user_client/mail')
add_vacation = transaction_decorator(add_vacation)
add_vacation.exposed = True

def add_forward(transaction, forward, target):

    if not forward:
        msg = 'Forward is empty.'
        rollback_url('/user_client/mail', msg, err=True)
    if len(forward) > 256:
        msg = 'Forward is too long ( max. 256 charcters).'
        rollback_url('/user_client/mail', msg, err=True)
    if not target:
        msg = 'Emailtarget-identity is missing.'
        rollback_url('/user_client/mail', msg, err=True)
    email_target = transaction.get_email_target(int(target))
    try:
        fwd = email_target.add_forward(forward)
        transaction.commit()
    except SpineIDL.Errors.IntegrityError, e:
        msg = 'Could not save forward,- a possible reason is identical forwards.'
        rollback_url('/user_client/mail', msg, err=True)
        
    queue_message('Forward successfully added.')
    redirect('/user_client/mail')
add_forward = transaction_decorator(add_forward)
add_forward.exposed = True

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

