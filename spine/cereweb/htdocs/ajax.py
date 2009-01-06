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

##
## it seems like javascript uses unicode and the strings must be decoded
## ,- at least itcured my problems by displaying norwegian characters.
##
## 2007-09-28 tk.
##

def get_owner(owner):
    owner_type = owner.get_type().get_name() 
    if owner_type == 'person':
        data = get_person_info(owner)
    elif owner_type == 'group':
        data = get_group_info(owner)
    else:
        data = {
            'id': html_quote(owner.get_id()),
            'name': None,
            'type': owner_type,
        }

    return data

def get_account_info(account, owner=None):
    data = {
            "id": "%s" % html_quote(account.get_id()),
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
    return get_lastname_firstname(person)

def get_person_info(person):
    data = {
        "id": html_quote(person.get_id()),
        "name": get_person_name(person),
        "type": 'person',
    }
    return data

def get_group_info(group):
    data = {
        'id': html_quote(group.get_id()),
        'name': group.get_name(),
        'type': 'group',
    }
    return data

def search_account(transaction, query):
    result = {}
    accounts = transaction.get_account_searcher()
    accounts.set_search_limit(20, 0)
    accounts.order_by(accounts, 'name')
    accounts.set_name_like("%s*" % query)
    accounts = accounts.search()
    for account in accounts:
        account = get_account_info(account)
        result[account['id']] = account
    return result.values()

def search_person(transaction, query):
    result = {}
    searcher = transaction.get_person_name_searcher()
    searcher.set_search_limit(20, 0)
    searcher.set_name_variant(transaction.get_name_type("FULL"))
    searcher.order_by(searcher, 'person')
    searcher.set_name_like("*%s*" % query)
    people = [x.get_person() for x in searcher.search()]

    for person in people:
        data = get_person_info(person)
        accounts = {}
        for account in person.get_accounts():
            account = get_account_info(account, data)
            accounts[account['id']] = account
        data['accounts'] = accounts.values()
        result[data['id']] = data
    return result.values()

def search_group(transaction, query):
    result = {}
    searcher = transaction.get_group_searcher()
    searcher.set_search_limit(20, 0)
    searcher.order_by(searcher, 'account')
    searcher.set_name_like("%s*" % query)
    for group in searcher.search():
        group = get_group_info(group)
        result[group['id']] = group
    return result.values()

def search(transaction, query=None, type=None, output=None):
    if not query: return

    ## must convert from web encoding to native python
    ## string before calling islower
    query = from_web_decode(query)
    if not type:
        # We assume that people have names with upper case letters.
        if (query.find(':') == -1):
            if not query.islower():
                type = "person"
            else:
                type = "account"
        else:
            type, query = query.split(':', 1)
    if type:
        type = type.lower()

    ## convert to spine encoding
    query = to_spine_encode(query.strip())

    # Do not search unless the query has a chance of returning a good result.
    if len(query) < 3:
        result = ""
    elif type in ["account", 'a']:
        result = search_account(transaction, query)
    elif type in ["person", 'p']:
        result = search_person(transaction, query)
        if output == "account":
            accounts = {}
            for person in result:
                for a in person.get('accounts'):
                    accounts[a['id']] = a
            result = accounts.values()
    elif type in ["group", 'g']:
        result = search_group(transaction, query)
    else:
        result = ""

    if result:
        result.sort(lambda x,y: cmp(x['name'], y['name']))
        result = {'ResultSet': result}
    else:
        # JSON doesn't consider [] and {} to be empty.
        result = None
    ## cjson will convert to browser's charset
    return cjson.encode(result)
search = transaction_decorator(search)
search.exposed = True


def get_motd(transaction, id):
    message, subject = "",""
    try:
        motd = transaction.get_cereweb_motd(int(id))
        message, subject = motd.get_message(), motd.get_subject()
        ## just decode from spine cjson vil do the rest
        ##message = to_web_encode(message)
        ##subject = to_web_encode(subject)
    except NotFoundError, e:
        pass
    return cjson.encode({'message': message, 'subject': subject})
get_motd = transaction_decorator(get_motd)
get_motd.exposed = True
