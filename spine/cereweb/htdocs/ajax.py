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

import cjson
from sets import Set

from Cerebrum.Errors import NotFoundError
from gettext import gettext as _
from lib.utils import *

from lib.data.AccountDAO import AccountDAO
from lib.data.PersonDAO import PersonDAO
from lib.data.GroupDAO import GroupDAO

@session_required_decorator
def search(query=None, type=None, output=None):
    query = from_web_decode(query).strip()

    if not type:
        type, query = divine_type_from_query(query)
    type = normalize_type_name(type)

    if not is_valid_query(query, type):
        return cjson.encode(None)

    query = to_spine_encode(query)

    if type == "account":
        result = search_account(query, output)
    elif type == "person":
        result = search_person(query, output)
    elif type == "group":
        result = search_group(query)

    if result:
        result.sort(lambda x,y: cmp(x['name'], y['name']))
        result = {'ResultSet': result}

    ## cjson will convert to browser's charset
    return cjson.encode(result or None)
search.exposed = True

def search_account(query, output):
    dao = AccountDAO()
    accounts = dao.search(query)

    result = {}
    for account in accounts:
        data = dto_to_dict(account)
        if output == "account":
            owner = dao.get_owner(account.id)
            data['owner'] = dto_to_dict(owner)

        result[account.id] = data

    return result.values()

def search_person(query, output):
    dao = PersonDAO()
    people = dao.search(query)

    result = {}
    for person in people:
        if output == "account":
            owner = dto_to_dict(person)
            for account in dao.get_accounts(person.id):
                data = dto_to_dict(account)
                data['owner'] = owner
                result[account.id] = data
        else:
            result[person.id] = dto_to_dict(person)
    return result.values()

def search_group(query):
    dao = GroupDAO()
    groups = dao.search(query)

    result = {}
    for group in groups:
        result[group.id] = dto_to_dict(group)
    return result.values()

def dto_to_dict(dto):
    return {
            "id": dto.id,
            "name": html_quote(dto.name),
            "type": dto.type_name,
    }

def divine_type_from_query(query):
    if query.find(':') >= 0:
        type, query = query.split(':')
        query = query.strip()

    elif query.islower():
        type = "account"

    else:
        type = "person"

    return type, query

types = {
    'account': 'account',
    'a': 'account',
    'group': 'group',
    'g': 'group',
    'person': 'person',
    'p': 'person',
}

def normalize_type_name(type_name):
    type_name = type_name.strip().lower()
    return types.get(type_name, '')

def is_valid_query(query, type):
    if not type in types:
        return False

    if len(query) < 3:
        return False

    return True

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
