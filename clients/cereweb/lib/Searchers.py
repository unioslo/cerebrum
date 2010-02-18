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

from gettext import gettext as _
from templates.SearchResultTemplate import SearchResultTemplate

from lib.utils import get_database, create_url, is_ajax_request
from lib.utils import spine_to_web, get_messages, queue_message

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

    orderby_default = ''

    def __init__(self, *args, **kwargs):
        if self.SearchForm:
            self.form = self.SearchForm(**kwargs)

        self.defaults.update({
            'orderby': self.orderby_default
        })

        self.is_ajax = is_ajax_request()
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
        if not self.SearchForm:
            return None

        values = self.__get_remembered()
        values.update(self.form_values)
        return self.SearchForm(**values)

    def render_search_form(self):
        if not self.SearchForm:
            return None

        return self.form.respond()

    def respond(self):
        if not self.is_valid():
            if self.is_ajax:
                return self._get_fail_response('400 Bad request')
            return self.render_search_form()

        self.__remember_last()
        result = self.search()

        if result['hits'] == 0:
            if self.is_ajax:
                return self._get_fail_response('404 Not Found', [("No hits", True)])

            queue_message(_('The current search would yield no results.  Please refine your criteria and search again.'), title=_("No results"))
            return self.render_search_form()

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
                messages = get_messages()
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
    An abstract base class for cerebrum core searchers.
    
    Inheritors _must_ set the DAO class attribute to a class that takes a
    Database object as an argument and that has a search-method that returns a
    list of DTO objects that matches the search.

    Inheritors _must_ set the SearchForm class attribute to a SearchForm class
    that honors the Forms interface.  CoreSearcher uses SearchForm.Fields to
    retrieve the search values which are then sent to the DAO.search method.

    The headers class attribute should contain a tuple of tuples containing the
    header title and optionally the name of the field that should be sorted on.
    If this name is given, the header will be rendered as a link that returns
    the search sorted by the specified field.

    The columns class attribute should contain a tuple of fields that can be
    extracted from the search result DTOs.  The order of the columns tuple
    should match the order of the headers tuple, otherwise chaos ensues.

    The orderby_default class attribute can be set to the name of the field
    that should be ordered by if the orderby-argument is not provided by the
    user.

    Create format_%s methods where %s is the column name you want to format.
    See _format_date for an example.

    See PersonSearcher for an example of correct usage.
    """
    DAO = None
    search_method = 'search'
    headers = ()
    columns = ()
    __results = None

    def __init__(self, *args, **kwargs):
        super(CoreSearcher, self).__init__(*args, **kwargs)

        self.db = get_database()
        self.dao = self.DAO and self.DAO(self.db)

    def _get_search_args(self):
        kwargs = {}
        for name in self.SearchForm.Fields.keys():
            kwargs[name] = self._get_search_arg(name)
        return ([], kwargs)

    def _get_search_arg(self, name):
        return (self.form_values.get(name, '') or '').strip()

    def _get_results(self):
        if self.__results is None:
            args, kwargs = self._get_search_args()
            fn = getattr(self.dao, self.search_method)
            self.__results = fn(*args, **kwargs)

        return self.__results

    def has_prerequisite(self):
        return self.form.has_prerequisite()

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

            if type(value) == str:
                value = spine_to_web(value)

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
        url = create_url(target_id, target_type)
        return '<a href="%s">%s</a>' % (url, name)

    def _create_link(self, name, row):
        target_id = row.id
        target_type = row.type_name
        return self._create_view_link(name, target_type, target_id)
