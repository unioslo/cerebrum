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

from SpineIDL.Errors import NotFoundError
from gettext import gettext as _
from lib.utils import *
from lib.WorkList import remember_link
from lib.Search import SearchHandler, setup_searcher
from lib.templates.AccountSearchTemplate import AccountSearchTemplate

def search(transaction, **vargs):
    """Search for accounts and display results and/or searchform.""" 
    handler = SearchHandler('account', AccountSearchTemplate().form)
    handler.args = (
        'name', 'spread', 'create_date', 'expire_date', 'description'
    )
    handler.headers = (
        ('Name', 'name'), ('Owner', ''), ('Create date', 'create_date'),
        ('Expire date', 'expire_date'), ('Actions', '')
    )

    def search_method(values, offset, orderby, orderby_dir):
        name, spread, create_date, expire_date, description = values

        search = transaction.get_account_searcher()
        setup_searcher([search], orderby, orderby_dir, offset)
        
        if name:
            search.set_name_like(name)

        if expire_date:
            if not legal_date(expire_date):
                queue_message("Expire date is not a legal date.",error=True)
                return None
            date = transaction.get_commands().strptime(expire_date, "%Y-%m-%d")
            search.set_expire_date(date)

        if create_date:
            if not legal_date(create_date):
                queue_message("Created date is not a legal date.", error=True)
                return None
            date = transaction.get_commands().strptime(create_date, "%Y-%m-%d")
            search.set_create_date(date)

        if description:
            if not description.startswith('*'):
                description = '*' + description
            if not description.endswith('*'):
                description += '*'
            search.set_description_like(description)

        if spread:
            account_type = transaction.get_entity_type('account')

            entityspread = transaction.get_entity_spread_searcher()
            entityspread.set_entity_type(account_type)

            spreadsearcher = transaction.get_spread_searcher()
            spreadsearcher.set_entity_type(account_type)
            spreadsearcher.set_name_like(spread)

            entityspread.add_join('spread', spreadsearcher, '')
            search.add_intersection('', entityspread, 'entity')
		
        return search.search()
    
    def row(elm):
        owner = object_link(elm.get_owner())
        cdate = strftime(elm.get_create_date())
        edate = strftime(elm.get_expire_date())
        edit = object_link(elm, text='edit', method='edit', _class='action')
        remb = remember_link(elm, _class='action')
        return object_link(elm), owner, cdate, edate, str(edit)+str(remb)
    
    accounts = handler.search(search_method, **vargs)
    result = handler.get_only_result(accounts, row)
    cherrypy.response.headerMap['Content-Type'] = "text/xml"
    return result
search = transaction_decorator(search)
search.exposed = True

def dialog(transaction):
    cherrypy.response.headerMap['Content-Type'] = "text/xml"
    return """
<xml>
    <header>
        <p>header</p>
    </header>
    <body>
        <form><label for="group">Group:</label><input id="group" type="text"/></form>
    </body>
    <footer>
        <p>footer</p>
    </footer>
</xml>"""
dialog = transaction_decorator(dialog)
dialog.exposed = True

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
