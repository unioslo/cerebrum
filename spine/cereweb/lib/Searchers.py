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
import cjson
import urllib
import config
import cherrypy

import cereconf
import utils
import Messages
from gettext import gettext as _
from templates.SearchResultTemplate import SearchResultTemplate
import SpineIDL.Errors

from lib.utils import get_database

class Searcher(object):
    """
    Searcher class that should be subclassed by the respective search
    pages in cereweb.  You need to overload the abstract methods
    ''get_results'' and ''count''.

    def get_results(self):
        if not self.is_valid():
            return

        name = self.form_values.get('name', '')
        ...

    def count(self):
        if not self.is_valid():
            return 0
        ...

    You can also set the SearchForm class attribute to the search form that
    should be used with the searcher.  In that case you can use the
    get_form-method to get the form prefilled with remembered values from the
    previous search.
    """

    SearchForm = None

    url = 'search'

    headers = (
        ('Name', 'name'),
        ('Description', 'description'),
        ('Actions', '')
    )

    defaults = {
        'offset': 0,
        'orderby': '',
        'orderby_dir': 'asc',
        'redirect': '',
    }

    def __init__(self, *args, **kwargs):
        if self.SearchForm:
            self.form = self.SearchForm(**kwargs)

        self.is_ajax = utils.is_ajax_request()
        self.form_values = self.__init_values(*args, **kwargs)
        self.options = self.__init_options(kwargs)
        self.url_args = dict(self.form_values.items() + self.options.items())

    def __init_values(self, *args, **kwargs):
        """
        Parse kwargs dict based on the args list and decide whether we
        have any search parameters.

        Sets the self.values member variable to a dictionary with the
        search parameters.
        """
        if self.SearchForm:
            return self.form.get_values()

        form_values = {}
        for field in args:
            value = kwargs.get(field, '')
            if value != '':
                form_values[field] = value

        return form_values

    def __init_options(self, kwargs):
        options = self.defaults.copy()

        for key, value in self.defaults.items():
            if type(value) == int:
                options[key] = int(kwargs.get(key, value))
            else:
                options[key] = kwargs.get(key, value)
        return options

    @property
    def max_hits(self):
        return min(
            int(cherrypy.session['options'].getint('search', 'display hits')),
            config.conf.getint('cereweb', 'max_hits'))

    @property
    def offset(self):
        return int(self.options['offset'])

    @property
    def orderby(self):
        return self.options['orderby']

    @property
    def orderby_dir(self):
        return self.options['orderby_dir']

    @property
    def last_on_page(self):
        return min(
            self.count(),
            self.offset + self.max_hits)

    def get_form(self):
        if self.SearchForm:
            return self.SearchForm(**self.__get_remembered())

    def render_search_form(self):
        if not self.SearchForm:
            return None

        return self.get_form().respond()

    def respond(self):
        if not self.is_valid():
            fail_response = self._get_fail_response('400 Bad request')
            if self.is_ajax:
                return fail_response
            return self.render_search_form() or fail_response

        self.__remember_last()
        result = self.search()
        if not result:
            return self._get_fail_response('404 Not Found', [("No hits", True)])

        page = SearchResultTemplate()
        content = page.viewDict(result)
        page.content = lambda: content

        if self.is_ajax:
            return content
        else:
            return page.respond()

    def is_valid(self):
        if self.SearchForm:
            return self.form.is_correct()

        if hasattr(self, 'valid'):
            return self.valid
        return self.form_values and True or False

    def search(self):
        result_data = self._get_pager_data()
        result_data['rows'] = self.get_results()
        result_data['headers'] = self._create_table_headers()
        result_data['url'] = self.url
        result_data['url_args'] = self.url_args

        return result_data

    def get_results(self):
        """
        Returns a list of rows that matches the given search terms.
        """
        raise NotImplementedError("This method must be overloaded.")

    def count(self):
        """
        Returns the number of results found.  Can be more than the number of
        results returned by get_results.
        """
        raise NotImplementedError("This method must be overloaded.")

    def _create_table_headers(self):
        """Returns the headers for insertion into a table.

        Headers which the search can be sorted by, will be returned as a
        link with the searchparameters.
        """
        headers = []
        for header, h_orderby in self.headers:
            if not h_orderby:
                headers.append(header)
                continue

            href, current = self._get_header_link(h_orderby)
            if current:
                _class = 'class="current"'
            else:
                _class = ''
            header = '<a href="%s" %s>%s</a>' % (href, _class, header)
            headers.append(header)

        return headers

    def _get_header_link(self, header):
        current = False

        url_args = self.url_args.copy()
        url_args['orderby'] = header
        if header == self.url_args['orderby']:
            current = True

            url_args['orderby_dir'] = ''
            if self.url_args['orderby_dir'] != 'desc':
                url_args['orderby_dir'] = 'desc'

        return cgi.escape('%s?%s' % (self.url, urllib.urlencode(url_args))), current

    def _get_pager_data(self):
        hits = self.count()
        offset = self.offset

        return {
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
            'last_on_page': min(hits, offset + self.max_hits),
        }

    def _get_fail_response(self, status, messages=[]):
        if self.is_ajax:
            cherrypy.response.headerMap['Content-Type'] = 'text/plain; charset=utf-8'
            cherrypy.response.status = status
            if not messages:
                messages = utils.get_messages()
            return cjson.encode({'status': 404, 'messages': messages})
        else:
            return None

    def __remember_last(self):
        if cherrypy.session['options'].getboolean('search', 'remember last'):
            name = "%s_%s" % (self.__class__.__name__, 'last_search')
            cherrypy.session[name] = self.form_values

    def __get_remembered(self):
        remembered = {}
        if cherrypy.session['options'].getboolean('search', 'remember last'):
            name = "%s_%s" % (self.__class__.__name__, 'last_search')
            remembered = cherrypy.session.get(name, {})
        return remembered
    get_remembered = __get_remembered

class CoreSearcher(Searcher):
    """
    An abstract base class for cerebrum core searchers that creates a
    db-connection and a DAO.  Inheritors can set the DAO class attribute to
    the a DAO class and this class will be instatiated as dao.

    The database connection is available as db.

    Overload _get_results to return the actual search results.

    Create format_%s methods where %s is the column name you want to format.
    See _format_date for an example.

    See PersonSearcher for an example of correct usage of this base class.
    """
    DAO = None

    def __init__(self, *args, **kwargs):
        super(CoreSearcher, self).__init__(*args, **kwargs)

        self.db = get_database()
        self.dao = self.DAO and self.DAO(self.db)

    def _get_results(self):
        raise NotImplementedError("This method must be overloaded.")

    def get_results(self):
        if not self.is_valid():
            return

        results = self._get_results()
        results = self._extend_complete_results(results)
        results = self._sort_results(results)
        results = self._limit_results(results)
        results = self._extend_limited_result(results)

        for result in results:
            yield self.format_row(result)

    def _noop(self, results):
        return results
    _extend_complete_results = _noop
    _extend_limited_result = _noop

    def _sort_results(self, results):
        reverse = self.orderby_dir == 'desc'
        key = lambda x: self._get_column_value(x, self.orderby)

        results.sort(key=key, reverse=reverse)
        return results

    def _limit_results(self, result):
        start, end = self.offset, self.last_on_page
        return result[start:end]

    def count(self):
        return len(self._get_results())

    def format_row(self, row):
        for column in self.columns:
            value = self._get_column_value(row, column)
            formatter = self._get_formatter(column)

            yield formatter and formatter(value, row) or value

    def _get_formatter(self, name):
        fname = 'format_%s' % name.replace('.', '_')
        return getattr(self, fname, None)

    def _get_column_value(self, row, name):
        column = row
        for el in name.split('.'):
            column = getattr(column, el, '')
        return column

    def _format_date(self, date, row):
        return date.strftime("%Y-%m-%d")

    def _create_view_link(self, name, target_type, target_id):
        return '<a href="/%s/view?id=%s">%s</a>' % (target_type, target_id, name)

    def _create_link(self, name, row):
        target_id = row.id
        target_type = row.type_name
        return self._create_view_link(name, target_type, target_id)

class SpineSearcher(Searcher):
    """
    A spine-specific searcher module that should be subclassed by the
    respective search pages in cereweb.  To use this class, you need to
    subclass it and make the following methods:

    def get_searchers(self):
        '''
        Configures searchers and returns them in a dictionary.  The searchers
        should have the attribute 'join_name' set to the name needed to join
        the searcher to the main searcher or '' if the searcher is the main
        searcher.  The main searcher must be added to the dictionary with both
        the key 'main' and the header name (see below).
        '''  
        name = self.form_values.get('name').strip() + '*'
        account = self.transaction.get_account_searcher()
        account.set_name_like(name)
        account.join_name = ''
        return {'main': account, 'account': account}

    def filter_rows(self, results):
        '''
        Goes through the results and creates a list of tuples containing the
        search results.  The tuples should of course match the headers tuple
        so that the resulting table is labeled correctly.

        NB: Remember that this loop iterates over all resulting objects and
        so the operations in the loop should be minimal to keep the searches
        fast.
        '''
        rows = []
        for elm in results:
            attr = self.searchers['main'].join_name
            if attr:
                obj = getattr(obj, 'get_' + attr)()
            else:
                obj = elm

            owner = utils.object_link(obj.get_owner())
            cdate = utils.strftime(obj.get_create_date())
            edate = utils.strftime(obj.get_expire_date())
            edit = utils.object_link(obj, text='edit', method='edit', _class='action')
            rows.append((utils.object_link(obj), owner, cdate, edate, str(edit)))
        return rows


    The subclass must also define a 'headers' class variable which is a list of columns
    and sort names.  If the sort name contains a period, the name before the period is the
    key of the searcher dictionary and the rest is the field in that searcher
    that we should order by.

    Examples:
      ('Column name', 'searcher_key.attribute'),
    or if the attribute is guaranteed to be in the main searcher:
      ('Column name', 'attribute'),
    or if we don't want to be able to sort by this column:
      ('Column name', ''),

    """

    def __init__(self, transaction, *args, **kwargs):
        super(SpineSearcher, self).__init__(*args, **kwargs)

        self.transaction = transaction
        self.searchers = self.get_searchers()
        self.init_searcher()

    def init_searcher(self):
        """
        Configure the searcher based on the orderby, offset and display hits
        options.
        """

        offset = int(self.options['offset'])
        self.searchers['main'].set_search_limit(self.max_hits, offset)

    def count(self):
        return self.searchers['main'].length()

    def get_results(self):
        rows = self.get_rows()
        return self.filter_rows(rows)

    def get_rows(self):
        """Executes the search and returns the resulting rows."""
        if self.is_valid():
            return self.searchers['main'].search()

    def respond(self):
        try:
            return super(SpineSearcher, self).respond()
        except SpineIDL.Errors.AccessDeniedError, e:
            return self._get_fail_response('403 Forbidden', [("No access", True)])

class EmailDomainSearcher(SpineSearcher):
    headers = (
        ('Name', 'name'),
        ('Description', 'description'),
        ('Categories', '')
    )

    def get_searchers(self):
        form = self.form_values
        main = self.transaction.get_email_domain_searcher()

        name = utils.web_to_spine(form.get('name', '').strip())
        if name:
            main.set_name_like(name)

        description = utils.web_to_spine(form.get('description', '').strip())
        if description:
            main.set_description_like(description)

        return {'main': main}

    def filter_rows(self, results):
        rows = []
        for elm in results:
            link = utils.object_link(elm)
            cats = [utils.spine_to_web(i.get_name()) for i in elm.get_categories()[:4]]
            cats = ", ".join(cats[:3]) + (len(cats) == 4 and '...' or '')
            ## edit = utils.object_link(elm, text='edit', method='edit', _class='action')
            ## rows.append([link, utils.spine_to_web(elm.get_description()), cats, str(edit)])
            rows.append([link, utils.spine_to_web(elm.get_description()), cats, ])
        return rows

class OUSearcher(SpineSearcher):
    headers = (
        ('Name', 'name'),
        ('Acronym', 'acronym'),
        ('Short name', 'short_name'),
        ('Actions', '')
    )

    def get_searchers(self):
        main = self.transaction.get_ou_searcher()
        form = self.form_values

        acronym = utils.web_to_spine(form.get('acronym', '').strip())
        if acronym:
            main.set_acronym_like(acronym)

        short = utils.web_to_spine(form.get('short', '').strip())
        if short:
            main.set_short_name_like(short)

        spread = utils.web_to_spine(form.get('spread', '').strip())
        if spread:
            ou_type = self.transaction.get_entity_type('ou')

            searcher = self.transaction.get_entity_spread_searcher()
            searcher.set_entity_type(ou_type)

            spreadsearcher = self.transaction.get_spread_searcher()
            spreadsearcher.set_entity_type(ou_type)
            spreadsearcher.set_name_like(spread)

            searcher.add_join('spread', spreadsearcher, '')
            main.add_intersection('', searcher, 'entity')

        name = utils.web_to_spine(form.get('name', '').strip())
        if name:
            main.set_name_like(name)

        description = utils.web_to_spine(form.get('description', '').strip())
        if description:
            main.set_description_like(description)

        return {'main': main}

    def filter_rows(self, results):
        rows = []
        for elm in results:

            name = utils.spine_to_web(elm.get_display_name() or elm.get_name())
            link = utils.object_link(elm, text=name)
            ## edit = utils.object_link(elm, text='edit', method='edit', _class='action')
            acro = utils.spine_to_web(elm.get_acronym())
            short = utils.spine_to_web(elm.get_short_name())
            ## rows.append([link, acro, short, str(edit)])
            rows.append([link, acro, short, ])
        return rows

class PersonAffiliationsSearcher(SpineSearcher):
    headers = (('Name', 'person_name.name'),
               ('Type', ''),
               ('Status', 'status'),
               ('Source', ''),
               ('Affiliations', ''),
               ('Birth date', 'person.birth_date'))

    url = 'list_aff_persons'

    def get_searchers(self):
        form = self.form_values
        tr = self.transaction

        main = tr.get_person_affiliation_searcher()
        main.set_deleted_date_exists(False)
        main.join_name = 'person'

        person_name = tr.get_person_name_searcher()
        person_name.join_name = 'person'
        person_name.set_name_variant(tr.get_name_type('FULL'))
        person_name.set_source_system(tr.get_source_system('Cached'))

        person = tr.get_person_searcher()
        person.join_name = ''

        id = utils.web_to_spine(form.get('id', '').strip())
        if id:
            try:
                ou = tr.get_ou(int(id))
                main.set_ou(ou)
            except SpineIDL.Errors.NotFoundError, e:
                self.valid = False

        source = utils.web_to_spine(form.get('source', '').strip())
        if source:
            main.set_source_system(
                    tr.get_source_system(source))

        person_orderby_name = self.transaction.get_person_name_searcher()
        person_orderby_name.set_name_variant(self.transaction.get_name_type('LAST'))
        person_orderby_name.set_source_system(self.transaction.get_source_system('Cached'))
        main.add_join(main.join_name, person_orderby_name, 'person')
        main.order_by(person_orderby_name, 'name')

        return {'main': main, 'person_name': person_name, 'person': person}

    def filter_rows(self, results):
        rows = []
        #print 'filter_rows: !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! len(results)=',len(results)
        for elm in results:
            p = elm.get_person()
            affs=[]
            for a in p.get_affiliations():
                affs.append(utils.object_link(a.get_ou(), text=utils.spine_to_web(a.get_ou().get_name())))
            ##affs = [utils.spine_to_web(a.get_ou().get_name()) for a in p.get_affiliations()]
            type = utils.spine_to_web(elm.get_affiliation().get_name())
            status = utils.spine_to_web(elm.get_status().get_name())
            source = utils.spine_to_web(elm.get_source_system().get_name())
            persname = utils.spine_to_web(utils.get_lastname_firstname(p))
            name = utils.object_link(p, text=persname)
            birth_date = utils.strftime(p.get_birth_date())
            rows.append([name, type, status, source, ", ".join(affs), birth_date])
        return rows

class PersonAffiliationsOuSearcher(PersonAffiliationsSearcher):
    len = 0
    def get_rows(self):
        """Executes the search and returns the result."""
        if not self.is_valid():
            return

        kwargs = self.form_values
        tr = self.transaction

        id = utils.web_to_spine(kwargs.get('id', '').strip())
        ou = tr.get_ou(int(id))
        perspective = utils.web_to_spine(kwargs.get('source', '').strip())
        affiliation = utils.web_to_spine(kwargs.get('affiliation','').strip())
        withoutssn = utils.web_to_spine(kwargs.get('withoutssn', '').strip())
        recursive = utils.web_to_spine(kwargs.get('recursive', '').strip())
        perspectives = []
        if perspective == 'All':
            for pers in tr.get_ou_perspective_type_searcher().search():
                perspectives.append(pers)
        else:
            perspectives.append(tr.get_ou_perspective_type(perspective))
        ou_list = []
        if recursive:
            for perspective in perspectives:
                try:
                    ret = utils.flatten(ou, perspective)
                    if ret:
                        for r in ret:
                            ou_list.append(r)       
                except SpineIDL.Errors.NotFoundError, e:
                    pass
        else:
            ou_list.append(ou)
        affs = []
        if affiliation == 'All':
            for aff in tr.get_person_affiliation_type_searcher().search():
                affs.append(aff)
        else:
            affs.append(tr.get_person_affiliation_type(affiliation))
        allresults = []
        for theOu in ou_list:
            for aff in affs:
                aff_searcher = tr.get_person_affiliation_searcher()
                aff_searcher.set_ou(theOu)
                aff_searcher.set_affiliation(aff)
                res = aff_searcher.search()
                if res:
                    for result in res:
                        allresults.append(result)
        if withoutssn:
            filtered = []
            for personAff in allresults:
                person = personAff.get_person()
                extidsList = utils.extidlist(person)
                found = False
                for id in extidsList:
                    if id.variant.get_name() == 'NO_BIRTHNO':
                        found = True
                if not found:
                    filtered.append(personAff)
            allresults = filtered
        self.len = len(allresults)
        allresults.sort(lambda x,y : cmp(utils.get_lastname_firstname(x.get_person()), utils.get_lastname_firstname(y.get_person())))
        return allresults

    def count(self):
        return self.len
