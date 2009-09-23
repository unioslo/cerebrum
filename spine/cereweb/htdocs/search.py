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
from gettext import gettext as _

from lib import utils
from lib.PersonSearchForm import PersonSearchForm
from lib.PersonSearcher import PersonSearcher

from lib.templates.NewSearchTemplate import NewSearchTemplate

class Search(object):
    @utils.session_required_decorator
    def index(self):
        page = NewSearchTemplate()
        page.forms = [
            PersonSearchForm(),
        ]

        return page.respond()
    index.exposed = True

class PersonSearch(object):
    @utils.session_required_decorator
    def search(self, **vargs):
        """Search after hosts and displays result and/or searchform."""
        searcher = PersonSearcher(**vargs)
        return searcher.respond()
    search.exposed = True
    index = search

search = Search()
search.person = PersonSearch()
