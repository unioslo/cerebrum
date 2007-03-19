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

"""
Helper-module for search-pages and search-result-pages in cereweb.
"""

import cgi
import urllib
import config
import cherrypy

import utils
from WorkList import remember_link
from templates.SearchResultTemplate import SearchResultTemplate
import SpineIDL.Errors

class Searcher(object):
    """Searcher module that should be subclassed by the respective search
    pages in cereweb.  To use this class, you need to subclass it and make
    a method "get_searcher" which must return a dictionary with at least the
    'main' searcher. Ex return {'main': transaction.get_account_searcher()}

    The 'headers' should be a list where each element contains the name
    for that particular header and optionaly the name for the attribute
    it should be sorted after.

    If the sort name contains a period, the name before the period is the
    key of the searcher dictionary and the rest is the field in that searcher
    that we should order by.
    """

    headers = (
        ('Name', 'name'),
        ('Description', 'description'),
        ('Actions', '')
    )

    defaults = {
        'offset': 0,
        'orderby': '',
        'orderby_dir': '',
        'redirect': '',
    }

    def __init__(self, transaction, *args, **vargs):
        self.ajax = cherrypy.request.headerMap.get('X-Requested-With', "") == "XMLHttpRequest"

        self.transaction = transaction
        self.form_values = self.init_values(*args, **vargs)
        self.options = Searcher.defaults.copy()
        for key, value in Searcher.defaults.items():
            if type(value) == int:
                self.options[key] = int(vargs.get(key, value))
            else:
                self.options[key] = vargs.get(key, value)

        self.url_args = dict(self.form_values.items() + self.options.items())
        self.searchers = self.get_searcher()
        self.init_searcher()

    def init_searcher(self):
        """This method configures the searcher based on
        the contents of the args and vargs variables.
        """

        orderby = self.options['orderby']
        orderby_dir = self.options['orderby_dir']
        self.options['offset'] = offset = int(self.options['offset'])
        self.max_hits = min(
            int(cherrypy.session['options'].getint('search', 'display hits')),
            config.conf.getint('cereweb', 'max_hits'))
        searcher = self.searchers['main']

        if orderby:
            s = 'main'
            try:
                s, orderby = orderby.split('.')
            except ValueError, e:
                pass

            try:
                orderby_searcher = self.searchers[s]
                jn = getattr(orderby_searcher, 'join_name', None)
                if jn:
                    searcher.add_left_join('', orderby_searcher, jn)
            except KeyError, e:
                orderby_searcher = searcher
                
            if orderby_dir == 'desc':
                searcher.order_by_desc(orderby_searcher, orderby)
            else:
                searcher.order_by(orderby_searcher, orderby)

        if not offset:
            searcher.set_search_limit(self.max_hits, 0)
        else:
            searcher.set_search_limit(self.max_hits, int(offset))

        for (key, value) in self.form_values.items():
            func = getattr(self, key)
            func(value)

    def remember_last(self):
        if cherrypy.session['options'].getboolean('search', 'remember last'):
            name = "%s_%s" % (self.__class__.__name__, 'last_search')
            cherrypy.session[name] = self.form_values

    def get_remembered(self):
        remembered = {}
        if cherrypy.session['options'].getboolean('search', 'remember last'):
            name = "%s_%s" % (self.__class__.__name__, 'last_search')
            remembered = cherrypy.session.get(name, {})
        return remembered

    def init_values(self, *args, **vargs):
        """Parse vargs dict based on the args list and decide whether we
        have any search parameters.
        
        Sets the self.values member variable to a dictionary with the
        search parameters.

        Returns False if all the search parameters are empty, else False."""

        form_values = {}
        for item in args:
            value = vargs.get(item, '')
            if value != '':
                if self.ajax:
                    value = value.decode('utf8').encode('latin1')

                form_values[item] = value

        return form_values

    def get_header_link(self, header):
        current = False

        url_args = self.url_args.copy()
        url_args['orderby'] = header
        if header == self.url_args['orderby']:
            current = True

            url_args['orderby_dir'] = ''
            if self.url_args['orderby_dir'] != 'desc':
                url_args['orderby_dir'] = 'desc'
        
        return cgi.escape('search?%s' % (urllib.urlencode(url_args))), current

    def get_results(self):
        results = self.search()
        rows = self.filter_rows(results)
        hits = self.searchers['main'].length()
        headers = self.create_table_headers()
        offset = self.url_args['offset'] 
        result = {
            'headers': headers,
            'rows': rows,
            'url_args': self.url_args,
            'hits': hits,
            'is_paginated': hits > self.max_hits,
            'results_per_page': min(hits, self.max_hits),
            'has_next': (offset + self.max_hits) < hits,
            'has_previous': offset > 0,
            'next_offset': offset + self.max_hits,
            'previous_offset': offset - self.max_hits,
            'page': (offset / self.max_hits) + 1,
            'pages': (hits / self.max_hits) + 1,
            'first_on_page': offset + 1,
            'last_on_page': offset + self.max_hits,
        }
        if result['last_on_page'] > hits:
            result['last_on_page'] = hits
        return result

    def create_table_headers(self):
        """Returns the headers for insertion into a table.
        
        Headers which the search can be sorted by, will be returned as a
        link with the searchparameters.
        
        """
        headers = []
        for header, h_orderby in self.headers:
            if not h_orderby:
                headers.append(header)
                continue
            
            href, current = self.get_header_link(h_orderby)
            if current:
                _class = 'class="current"'
            else:
                _class = ''
            header = '<a href="%s" %s>%s</a>' % (href, _class, header)
            headers.append(header)

        return headers

    def search(self):
        """Executes the search and returns the result."""
        if self.is_valid():
            return self.searchers['main'].search()

    def is_valid(self):
        if hasattr(self, 'valid'):
            return self.valid
        return self.form_values and True or False

    def get_fail_response(self, status, messages=[]):
        if self.ajax:
            cherrypy.response.headerMap['Content-Type'] = 'text/plain; charset=utf-8'
            cherrypy.response.status = status
            import cjson
            if not messages:
                messages = utils.get_messages()
            return cjson.encode({'status': 404, 'messages': messages})
        else:
            return None

    def respond(self):
        if not self.is_valid():
            return self.get_fail_response('400 Bad request')

        self.remember_last()

        try:
            result = self.get_results()
        except SpineIDL.Errors.AccessDeniedError, e:
            print e
            return self.get_fail_response('403 Forbidden', [("No access", True)])
        if not result:
            return self.get_fail_response('404 Not Found', [("No hits", True)])

        page = SearchResultTemplate()
        content = page.viewDict(result)
        page.content = lambda: content

        if self.ajax:
            cherrypy.response.headerMap['Content-Type'] = 'text/html; charset=iso-8859-1'
            return content
        else:
            return page.respond()

    def name(self, name):
        self.searchers['main'].set_name_like(name)

    def description(self, description):
        self.searchers['main'].set_description_like(description)

    def filter_rows(self, results):
        rows = []
        for elm in results:
            edit = utils.object_link(elm, text='edit', method='edit', _class='action')
            remb = remember_link(elm, _class='action')
            rows.append([utils.object_link(elm), elm.get_description(), str(edit)+str(remb)])
        return rows

class AccountSearcher(Searcher):
    headers = [
            ('Name', 'name'),
            ('Owner', 'owner'),
            ('Create date', 'create_date'),
            ('Expire date', 'expire_date'),
            ('Actions', '')
        ]

    def get_searcher(self):
        return {'main': self.transaction.get_account_searcher()}

    def expire_date(self, expire_date):
        if not utils.legal_date(expire_date):
            utils.queue_message("Date of birth is not a legal date.",error=True)
            self.valid = False
            return
        date = self.transaction.get_commands().strptime(expire_date, "%Y-%m-%d")
        self.searchers['main'].set_expire_date(date)

    def create_date(self, create_date):
        if not utils.legal_date(create_date):
            utils.queue_message("Date of birth is not a legal date.",error=True)
            self.valid = False
            return
        date = self.transaction.get_commands().strptime(create_date, "%Y-%m-%d")
        self.searchers['main'].set_create_date(date)

    def description(self, description):
        if not description.startswith('*'):
            description = '*' + description
        if not description.endswith('*'):
            description += '*'
        self.searchers['main'].set_description_like(description)

    def spread(self, spread):
        account_type = self.transaction.get_entity_type('account')

        entityspread = self.transaction.get_entity_spread_searcher()
        entityspread.set_entity_type(account_type)

        spreadsearcher = self.transaction.get_spread_searcher()
        spreadsearcher.set_entity_type(account_type)
        spreadsearcher.set_name_like(spread)

        entityspread.add_join('spread', spreadsearcher, '')
        self.searchers['main'].add_intersection('', entityspread, 'entity')
            
    def filter_rows(self, results):
        rows = []
        for elm in results:
            owner = utils.object_link(elm.get_owner())
            cdate = utils.strftime(elm.get_create_date())
            edate = utils.strftime(elm.get_expire_date())
            edit = utils.object_link(elm, text='edit', method='edit', _class='action')
            remb = remember_link(elm, _class='action')
            rows.append((utils.object_link(elm), owner, cdate, edate, str(edit)+str(remb)))
        return rows

class PersonSearcher(Searcher):
    headers = [
        ('Name', 'last_name.name'),
        ('Date of birth', 'birth_date'),
        ('Account(s)', ''),
        ('Affiliation(s)', ''),
        ('Actions', '')
    ]

    def get_searcher(self):
        variant = self.transaction.get_name_type('LAST')
        source = self.transaction.get_source_system('Cached')

        main = self.transaction.get_person_searcher()
        last_name = self.transaction.get_person_name_searcher()
        last_name.set_name_variant(variant)
        last_name.set_source_system(source)
        last_name.join_name = 'person'
        #main.add_left_join('', last_name, 'person')
        return {'main': main,
                'last_name': last_name}

    def accountname(self, accountname):
        searcher = self.transaction.get_account_searcher()
        searcher.set_name_like(accountname)
        self.searchers['main'].add_intersection('', searcher, 'owner')
            
    def birthdate(self, birthdate):
        if not utils.legal_date( birthdate ):
            utils.queue_message("Date of birth is not a legal date.",error=True)
            self.valid = False
            return

        date = strptime(self.transaction, birthdate)
        self.searchers['main'].set_birth_date(date)

    def name(self, name):
        name = name.replace(" ", "*")
        name_searcher = self.transaction.get_person_name_searcher()
        name_searcher.set_name_like(name)
        self.searchers['main'].add_intersection('', name_searcher, 'person')

    def spread(self, spread):
        person_type = self.transaction.get_entity_type('person')

        searcher = self.transaction.get_entity_spread_searcher()
        searcher.set_entity_type(person_type)

        spreadsearcher = self.transaction.get_spread_searcher()
        spreadsearcher.set_entity_type(person_type)
        spreadsearcher.set_name_like(spread)

        searcher.add_join('spread', spreadsearcher, '')
        self.searchers['main'].add_intersection('', searcher, 'entity')

    def ou(self, ou):
        ousearcher = self.transaction.get_ou_searcher()
        ousearcher.set_name_like(ou)
        searcher = self.searchers.setdefault('aff_searcher',
            self.transaction.get_person_affiliation_searcher())
        searcher.add_join('ou', ousearcher, '')
        self.searchers['main'].add_intersection('', searcher, 'person')

    def aff(self, aff):
        affsearcher = self.transaction.get_person_affiliation_type_searcher()
        affsearcher.set_name_like(aff)
        searcher = self.searchers.setdefault('aff_searcher',
            self.transaction.get_person_affiliation_searcher())
        searcher.add_join('affiliation', affsearcher, '')
        self.searchers['main'].add_intersection('', searcher, 'person')

    def filter_rows(self, results):
        rows = []
        for elm in results:
                try:
                    date = utils.strftime(elm.get_birth_date())
                    affs = [str(utils.object_link(i.get_ou())) for i in elm.get_affiliations()[:3]]
                    affs = ', '.join(affs[:2]) + (len(affs) == 3 and '...' or '')
                except SpineIDL.Errors.AccessDeniedError, e:
                    date = 'No Access'
                    affs = 'No Access'
                accs = [str(utils.object_link(i)) for i in elm.get_accounts()[:3]]
                accs = ', '.join(accs[:2]) + (len(accs) == 3 and '...' or '')
                edit = utils.object_link(elm, text='edit', method='edit', _class='action')
                remb = remember_link(elm, _class="action")
                rows.append([utils.object_link(elm), date, accs, affs, str(edit)+str(remb)])
        return rows

class AllocationPeriodSearcher(Searcher):
    headers = (('Name', 'name'),
               ('Allocation Authority', 'allocationauthority'),
               ('Actions', ''),
    )

    def get_searcher(self):
        return {'main': self.transaction.get_allocation_period_searcher()}

    def allocationauthority(self, allocationauthority):
        ## XXX need to fix pulldown search for allocation authority
        ## FIXME: What does this mean?
        self.searchers['main'].set_allocationauthority_like(allocationauthority)

    def filter_rows(self, results):
        rows = []
        for elm in results:
            edit = utils.object_link(elm, text='edit', method='edit', _class='action')
            remb = remember_link(elm, _class='action')
            auth = elm.get_authority().get_name()
            rows.append([utils.object_link(elm), auth, str(edit)+str(remb)])
        return rows

class AllocationSearcher(Searcher):
    headers = (
        ('Allocation name', 'allocation_name'),
        ('Period', 'period'),
        ('Status', 'status'),
        ('Machines', 'machines'),
        ('Actions', '')
    )

    def get_searcher(self):
        return self.transaction.get_allocation_searcher()

    def allocation_name(self, allocation_name):
        an_searcher = self.transaction.get_project_allocation_name_searcher()
        an_searcher.set_name_like(allocation_name)
        self.searchers['allocation_name'] = an_searcher
        self.searchers['main'].add_join('allocation_name', an_searcher, '')

    def filter_rows(self, results):
        rows = []
        for elm in results:
            edit = utils.object_link(elm, text='edit', method='edit', _class='action')
            remb = remember_link(elm, _class='action')
            proj = utils.object_link(elm.get_allocation_name().get_project())
            period = elm.get_period().get_name()
            status = elm.get_status().get_name()
            machines = [m.get_name() for m in elm.get_machines()]
            machines = "(%s)" % ",".join(machines)
            rows.append([utils.object_link(elm), period, status, machines, str(edit)+str(remb)])
        return rows
    #FIXME status
    #FIXME period

class DiskSearcher(Searcher):
    headers = (
        ('Path', 'path'), ('Host', ''),
        ('Description', 'description'), ('Actions', '')
    )
   
    def get_searcher(self):
        return {'main': self.transaction.get_disk_searcher()}

    def path(self, path):
        self.searchers['main'].set_path_like(path)

    def description(self, description):
        self.searchers['main'].set_description_like(description)

    def filter_rows(self, results):
        rows = []
        for elm in results:
            path = utils.object_link(elm, text=elm.get_path())
            host = utils.object_link(elm.get_host())
            edit = utils.object_link(elm, text='edit', method='edit', _class='action')
            remb = remember_link(elm, _class='action')
            rows.append([path, host, elm.get_description(), str(edit)+str(remb)])
        return rows

class EmailDomainSearcher(Searcher):
    headers = (
        ('Name', 'name'),
        ('Description', 'description'),
        ('Categories', '')
    )

    def get_searcher(self):
        return {'main': self.transaction.get_email_domain_searcher()}

    def category(self, category):
        # TODO
        pass

    def filter_rows(self, results):
        rows = []
        for elm in results:
            link = utils.object_link(elm)
            cats = [i.get_name() for i in elm.get_categories()[:4]]
            cats = ", ".join(cats[:3]) + (len(cats) == 4 and '...' or '')
            edit = utils.object_link(elm, text='edit', method='edit', _class='action')
            remb = remember_link(elm, _class='action')
            rows.append([link, elm.get_description(), cats, str(edit)+str(remb)])
        return rows

class GroupSearcher(Searcher):
    headers = (
        ('Group name', 'name'),
        ('Description', 'description'),
        ('Actions', '')
    )

    def get_searcher(self):
        return {'main': self.transaction.get_group_searcher()}

    def gid_end(self, gid_end):
        if gid_end:
            self.searchers['main'].set_posix_gid_less_than(int(gid_end))

    def gid_option(self, gid_option):
        pass

    def gid(self, gid):
        gid_option = self.form_values['gid_option']
        if gid_option == "exact":
            self.searchers['main'].set_posix_gid(int(gid))
        elif gid_option == "above":
            self.searchers['main'].set_posix_gid_more_than(int(gid))
        elif gid_option == "below":
            self.searchers['main'].set_posix_gid_less_than(int(gid))
        elif gid_option == "range":
            self.searchers['main'].set_posix_gid_more_than(int(gid))
            
    def spread(self, spread):
        group_type = self.transaction.get_entity_type('group')

        searcher = self.transaction.get_entity_spread_searcher()
        searcher.set_entity_type(group_type)

        spreadsearcher = self.transaction.get_spread_searcher()
        spreadsearcher.set_entity_type(group_type)
        spreadsearcher.set_name_like(spread) 
        
        searcher.add_join('spread', spreadsearcher, '')
        self.searchers['main'].add_intersection('', searcher, 'entity')

class HostSearcher(Searcher):
    def get_searcher(self):
        return {'main': self.transaction.get_host_searcher()}

class OUSearcher(Searcher):
    headers = (
        ('Name', 'name'),
        ('Acronym', 'acronym'),
        ('Short name', 'short_name'),
        ('Actions', '')
    )

    def get_searcher(self):
        return {'main': self.transaction.get_ou_searcher()}
    
    def acronym(self, acronym):
        self.searchers['main'].set_acronym_like(acronym)

    def short(self, short):
        self.searchers['main'].set_short_name_like(short)
        
    def spread(self, spread):
        ou_type = self.transaction.get_entity_type('ou')

        searcher = self.transaction.get_entity_spread_searcher()
        searcher.set_entity_type(ou_type)

        spreadsearcher = self.transaction.get_spread_searcher()
        spreadsearcher.set_entity_type(ou_type)
        spreadsearcher.set_name_like(spread)

        searcher.add_join('spread', spreadsearcher, '')
        self.searchers['main'].add_intersection('', searcher, 'entity')
    
    def filter_rows(self, results):
        rows = []
        for elm in results:
            name = elm.get_display_name() or elm.get_name()
            link = utils.object_link(elm, text=name)
            edit = utils.object_link(elm, text='edit', method='edit', _class='action')
            remb = remember_link(elm, _class='action')
            rows.append([link, elm.get_acronym(), elm.get_short_name(), str(edit)+str(remb)])
        return rows

class ProjectSearcher(Searcher):
    headers = (
        ('Title', 'title'),
        ('Science', 'science'),
        ('Owner', 'owner'),
        ('Actions', '')
    )

    def get_searcher(self):
        return {'main': self.transaction.get_project_searcher()}

    def title(self, title):
        self.searchers['main'].set_title_like(title)

    def filter_rows(self, results):
        rows = []
        for elm in results:
            edit = utils.object_link(elm, text='edit', method='edit', _class='action')
            remb = remember_link(elm, _class='action')
            sci  = " " #elm.get_science().get_name()
            ownr = utils.object_link(elm.get_owner())
            rows.append([utils.object_link(elm), sci, ownr, str(edit)+str(remb)])
        return rows

class PersonAffiliationsSearcher(Searcher):
    headers = (('Type', 'type'),
               ('Status', 'status'),
               ('Source', 'source'),
               ('Name', 'name'),
               ('Birth date', 'birth_date'))

    def get_searcher(self):
        return {'main': self.transaction.get_person_affiliation_searcher()}

    def id(self, id):
        try:
            ou = self.transaction.get_ou(int(id))
        except SpineIDL.Errors.NotFoundError, e:
            self.valid = False
        else:
            self.searchers['main'].set_ou(ou)

    def source(self, source):
        self.searchers['main'].set_set_source_system(
                self.transaction.get_source_system(source))

    def filter_rows(self, results):
        rows = []
        for elm in results:
            p = elm.get_person()
            type = elm.get_affiliation().get_name()
            status = elm.get_status().get_name()
            source = elm.get_source_system().get_name()
            name = utils.object_link(p)
            birth_date = utils.strftime(p.get_birth_date())
            rows.append([type, status, source, name, birth_date])
        return rows
