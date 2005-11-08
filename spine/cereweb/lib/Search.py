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

import forgetHTML as html
from gettext import gettext as _
from Cereweb.utils import url

import Cereweb.config
max_hits = Cereweb.config.conf.getint('cereweb', 'max_hits')

def get_arg_values(args, vargs):
    """Returns a list containing the values sorted by attr.

    The method is used in searchpages to create a list of the arguments
    given for the search. 'args' should contain a list with the names
    of the arguments. 'vargs' should be a dict with {'argument': value}.
    """
    valuelist = [''] * len(args)
    for name, value in vargs.items():
        if name in args:
            valuelist[args.index(name)] = value
    return valuelist

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

def get_form_values(args, values):
    """Creates a dict with {arg: value} for each arg in args."""
    formvalues = {}
    for i in range(len(args)):
        formvalues[args[i]] = values[i]
    return formvalues

def get_link_arguments(args, values):
    """Returns the args/values converted for use in links."""
    arguments = ['%s=%s' % (args[i],values[i]) for i in 
                    range(len(args)) if values[i] != '']
    return len(arguments) and '?' + '&'.join(arguments) or ''

def create_table_headers(headers, args, values, page):
    """Returns the headers for insertion into a table.
    
    Headers which the search can be sorted by, will be returned as a
    link with the searchparameters.
    
    'headers' should be a list where each element contains the name
    for that particular header and optionaly the name for the attribute
    it should be sorted after.
    """
    link = url(page)

    new_headers = []
    for header, orderby in headers:
        if orderby != '':
            new_values = values[:]
            if values[args.index('orderby')] == orderby:
                if values[args.index('orderby_dir')] != 'desc':
                    new_values[args.index('orderby_dir')] = 'desc'
                else:
                    new_values[args.index('orderby_dir')] = ''
                _class = 'current'
            else:
                new_values[args.index('orderby')] = orderby
                _class = ''
            href = link + get_link_arguments(args, new_values)
            header = html.Anchor(_(header), href=href, _class=_class) 
            new_headers.append(header)
        else:
            new_headers.append(_(header))

    return new_headers

# arch-tag: 3c5b9e16-4d49-11da-85e2-cbdfb1bc4ff1
