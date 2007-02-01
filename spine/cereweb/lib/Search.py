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

See SearchHandler for how to create searchpages.
"""

import cherrypy

import cgi
import urllib
from utils import object_id, object_name
from gettext import gettext as _

import config

# maximum hits to search for in one search.
max_hits = config.conf.getint('cereweb', 'max_hits')

class SearchHandler:
    """Handling display of a search-page and searching.
    
    To create a searchpage for cereweb initiate this class and provide
    the needed information.
    
    'cls_name' is the object which is searched for, and is used for
    storing the values searched for.
    'form' should be a method which returns the searchform.
    'args' should be a list containing the names of the search variables.
    'headers' should be a list with the names of the result table headers
    and their respective variables on the search-objects.

    Code-example:
    ----------------------------------------------------------------
    def example_search(transaction, **vargs):
        handler = SearchHandler('example', example_form_method)
        handler.args = ('name', 'description')
        handler.headers = (('Name', 'name'), ('Actions', ''))

        def search_method(values, offset, orderby, orderby_dir):
            name, description = values
            search = transaction.get_example_searcher()
            setup_searcher([search], orderby, orderby_dir, offset)
            if name:
                search.set_name_like(name)
            return search.search()

        def row(elm):
            return object_link(elm), "no actions here"

        objs = handler.search(search_method, **vargs)
        result = handler.get_result(objs, row)
        return result
    ----------------------------------------------------------------
    """
    
    def __init__(self, cls_name, form):
        self.var_name = cls_name + '_last_search'
        self.form = form
        self.args = []
        self.headers = []
        
    def search(self, method, **vargs):
        """Prepare values for search and return result.

        Prepares search-values before the search, then performs
        the actual search with the provided search-method 'method'.
        'method' is provided with a dict containing the search-values
        given by the user, and the offset, orderby and orderby-direction.
        
        If no values was provided None is returned, else a list with
        the search-result is returned (empty list if none is found).
        """

        # We want to be able to force the search form to redirect
        # us to a specific page when a result is chosen.
        self.redirect = vargs.get('redirect', None)

        self.values = get_arg_values(self.args, vargs)
        perform_search = len([i for i in self.values if i != ""])

        if perform_search:
            self.offset = vargs.get('offset', 0)
            self.orderby = vargs.get('orderby', None)
            self.orderby_dir = vargs.get('orderby_dir', None)
            cherrypy.session[self.var_name] = self.values
            return method(self.values, self.offset,
                          self.orderby, self.orderby_dir)
        else:
            return None

    def get_form(self):
        """ Get the html-form for the search.
        
        Return the HTML-form for the search with the values
        used in the current or last performed search.

        self.form must be set, and should be a callable method
        which returns a string with the search-form.
        """
        assert self.form is not None
        
        remember = cherrypy.session['options'].getboolean('search', 'remember last')

        formvalues = {}
        if self.redirect:
            formvalues['redirect'] = self.redirect

        if self.var_name in cherrypy.session and remember:
            values = cherrypy.session[self.var_name]
            formvalues = get_form_values(self.args, values)
        return self.form(formvalues)

    def filter_elements(self, elements, row_method):
        """Run the elements through the row_method so they can be used to render
        the chosen template."""
        if not (hasattr(self, 'values') and hasattr(self, 'offset')):
            raise Exception('search must be called before get_result')
        
        # maximum hits to display in a search result.
        dis_hits = cherrypy.session['options'].getint('search', 'display hits')

        result = []
        for elm in elements[:dis_hits]:
            result.append(row_method(elm))
        return result, dis_hits
    
    def get_result(self, elements, row_method):
        """Returns a table with the result.

        'row_method' is called on each element in 'elements' and the
        result is inserted into a SearchResultTemplate.

        search must be called before get_result.
        """
        if elements is None:
            return self.get_form()
        
        if self.redirect:
            def m(elm):
                url = '<a href="%s=%s">%s</a>'
                return [url % (self.redirect, object_id(elm), object_name(elm))]
            row_method = m
            
        result, dis_hits = self.filter_elements(elements, row_method)

        # To avoid import-circle we import the template here
        from lib.templates.SearchResultTemplate import SearchResultTemplate
        
        template = SearchResultTemplate()
        return template.view(result, self.headers, self.args, self.values,
                             len(elements), dis_hits, self.offset, self.orderby,
                             self.orderby_dir, self.get_form(), 'search')

def setup_searcher(searchers, orderby, orderby_dir, offset):
    """Set up the searcher with offset and orderby if given.
    
    'searchers' should if it contains more than 1 element, be a
    dict with {name of searcer: searcer}. The primary searcher
    which we set the limit/offset on should be named main. The
    dict is used when we need to set orderby on other searchers
    then the main searcher.
    
    'orderby' should be on the format 'searcher.attr' if you need
    to order by attrs not in the primary searcher.
    """
    if len(searchers) == 1:
        searcher, = searchers
    else:
        searcher = searchers['main']
    
    if orderby:
        if '.' in orderby and len(searchers) > 1:
            tmp, orderby = orderby.split('.')
            orderby_searcher = searchers[tmp]
        else:
            orderby_searcher = searcher
        
        if orderby_dir == 'desc':
            searcher.order_by_desc(orderby_searcher, orderby)
        else:
            searcher.order_by(orderby_searcher, orderby)

    if not offset:
        searcher.set_search_limit(max_hits, 0)
    else:
        searcher.set_search_limit(max_hits - int(offset), int(offset))

def get_arg_values(args, vargs):
    """Returns a list containing the values sorted by attr.

    The method is used in searchpages to create a list of the arguments
    given for the search. 'args' should contain a list with the names
    of the arguments. 'vargs' should be a dict with {'argument': value}.
    """
    args = list(args)
    valuelist = [''] * len(args)
    for name, value in vargs.items():
        if name in args:
            if name == 'redirect': print name
            valuelist[args.index(name)] = value
    return valuelist

def get_form_values(args, values):
    """Creates a dict with {arg: value} for each arg in args."""
    formvalues = {}
    for i in range(len(args)):
        formvalues[args[i]] = values[i]
    return formvalues

def get_link_arguments(args, values):
    """Returns the args/values converted for use in links."""
    argdict = dict(zip(args, values))
    return cgi.escape(urllib.urlencode(argdict))

def create_table_headers(headers, args, values, orderby, orderby_dir, page):
    """Returns the headers for insertion into a table.
    
    Headers which the search can be sorted by, will be returned as a
    link with the searchparameters.
    
    'headers' should be a list where each element contains the name
    for that particular header and optionaly the name for the attribute
    it should be sorted after.
    """
    vargs = {}
    for i in range(len(args)):
        vargs[args[i]] = values[i]
    
    new_headers = []
    for header, h_orderby in headers:
        if not h_orderby:
            new_headers.append(_(header))
            continue
        
        new_vargs = vargs.copy()
        new_vargs['orderby'] = h_orderby
        _class = ''

        if h_orderby == orderby:
            _class = 'current'
            new_vargs['orderby_dir'] = ''
            if orderby_dir != 'desc':
                new_vargs['orderby_dir'] = 'desc'
        
        href = cgi.escape('%s?%s' % (page, urllib.urlencode(new_vargs)))
        _class = _class and 'class="%s"' % _class
        header = '<a href="%s" %s>%s</a>' % (href, _class, _(header))
        new_headers.append(header)

    return new_headers

# arch-tag: 3c5b9e16-4d49-11da-85e2-cbdfb1bc4ff1
