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

from lib import cjson
from sets import Set

from SpineIDL.Errors import NotFoundError
from gettext import gettext as _
from lib.utils import *
from lib.WorkList import remember_link
from lib.Search import SearchHandler, setup_searcher
from lib.templates.AccountSearchTemplate import AccountSearchTemplate

def get_owner(owner):
    owner_type = owner.get_type().get_name() 
    if owner_type == 'person':
        data = get_person_info(owner, include_accounts=False)
    elif owner_type == 'group':
        data = get_group_info(owner, include_accounts=False)
    else:
        data = {
            'id': owner.get_id(),
            'name': None,
            'type': owner_type,
        }

    return data

def get_account_info(account, owner=None):
    data = {
            "id": "%s" % account.get_id(),
            "name": "%s" % account.get_name(),
            "type": "account",
    }

    if not owner:
        owner = get_owner(account.get_owner())

    if owner:
        data['owner'] = owner.copy()
    else:
        data['owner'] = "No owner"

    return data

def get_person_name(person):
    for n in person.get_names():
        if n.get_name_variant().get_name() == "FULL":
            return n.get_name()
    return None

def get_person_info(person, include_accounts=True):
    data = {
        "id": person.get_id(),
        "name": get_person_name(person),
        "type": 'person',
    }
    return data

def get_group_info(group, include_accounts=True):
    data = {
        'id': group.get_id(),
        'name': group.get_name(),
        'type': 'group',
    }
    return 

def search_account(transaction, query):
    result = {}

    accounts = transaction.get_account_searcher()
    accounts.set_name_like("%s*" % query)
    accounts = accounts.search()
    for account in accounts:
        account = get_account_info(account)
        result[account['id']] = account
    return result.values()

def search_person(transaction, query):
    result = {}

    searcher = transaction.get_person_name_searcher()
    searcher.set_name_variant(transaction.get_name_type("FULL"))
    searcher.set_name_like("%s*" % query)
    people = [x.get_person() for x in searcher.search()]

    for person in people:
        data = get_person_info(person)
        for account in person.get_accounts():
            account = get_account_info(account, data)
            result[account['id']] = account
    return result.values()

def search(transaction, query=None, type=None):
    if not query: return
    
    if not type:
        if not query.islower():
            type = "person"
        else:
            type = "account"

    if type == "account":
        result = search_account(transaction, query)
    elif type == "person":
        result = search_person(transaction, query)
    else:
        result = ""

    if result:
        result = {'ResultSet': result}
    return cjson.encode(result)
search = transaction_decorator(search)
search.exposed = True

def get_motd(transaction, id):
    message, subject = "",""
    try:
        motd = transaction.get_cereweb_motd(int(id))
    except NotFoundError, e:
        pass
    message = motd.get_message().decode('latin1').encode('utf-8')
    message = message.replace('\n', '\\n').replace('\r', '').replace("'", "\\'").replace('"', '\\"')
    subject = motd.get_subject().decode('latin1').encode('utf-8')
    subject = subject.replace('\n', '\\n').replace('\r', '').replace("'", "\\'").replace('"', '\\"')
    return "{'message': '%s', 'subject': '%s' }" % (message, subject)
get_motd = transaction_decorator(get_motd)
get_motd.exposed = True
