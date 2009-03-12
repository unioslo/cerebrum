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

import cereconf
import utils
import Messages
from gettext import gettext as _
from Forms import Form
from templates.SearchResultTemplate import SearchResultTemplate
import SpineIDL.Errors

class Searcher(object):
    """
    Searcher module that should be subclassed by the respective search
    pages in cereweb.  To use this class, you need to subclass it and make
    the following methods:

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
            remb = utils.remember_link(obj, _class='action')
            rows.append((utils.object_link(obj), owner, cdate, edate, str(edit)+str(remb)))
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

    url = 'search'

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
        self.searchers = self.get_searchers()
        self.init_searcher()

    def init_searcher(self):
        """
        Configure the searcher based on the orderby, offset and display hits
        options.
        """

        orderby = self.options['orderby']
        orderby_dir = self.options['orderby_dir']
        offset = int(self.options['offset'])

        self.max_hits = min(
            int(cherrypy.session['options'].getint('search', 'display hits')),
            config.conf.getint('cereweb', 'max_hits'))

        main = self.searchers['main']
        main.set_search_limit(self.max_hits, offset)

        ## if orderby:
        ##     try:
        ##         orderby_searcher, orderby = orderby.split('.')
        ##         orderby_searcher = self.searchers[orderby_searcher]
        ##         join_name = orderby_searcher.join_name
        ##         main.add_join(main.join_name, orderby_searcher, join_name)
        ##     except (ValueError, KeyError), e:
        ##         orderby_searcher = main
        ##         
        ##     if orderby_dir == 'desc':
        ##         main.order_by_desc(orderby_searcher, orderby)
        ##     else:
        ##         main.order_by(orderby_searcher, orderby)

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
        
        return cgi.escape('%s?%s' % (self.url, urllib.urlencode(url_args))), current

    def get_results(self):
        self.max_hits = 10
        results = self.search()
        rows = self.filter_rows(results)
        hits = self.searchers['main'].length()
        headers = self.create_table_headers()
        offset = self.url_args['offset'] 
        result = {
            'headers': headers,
            'rows': rows,
            'url': self.url,
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
            return content
        else:
            return page.respond()

class AccountSearcher(Searcher):
    class SearchForm(Form):
        def init_form(self):
            self.action = '/account/search'
            self.title = "Search for Account"
            self.help = ['Use wildcards * and ? to extend the search.', 'Supply several search parameters to limit the search.']

            self.order = [
                'name', 'spread', 'create_date', 'expire_date', 'description',
            ]
            self.fields = {
                'name': {
                    'label': _('Account name'),
                    'required': False,
                    'type': 'text',
                },
                'spread': {
                    'label': _('Spread name'),
                    'required': False,
                    'type': 'text',
                },
                'create_date': {
                    'label': _('Create date'),
                    'required': False,
                    'type': 'text',
                    'help': "YYYY-MM-DD, exact match.",
                },
                'expire_date': {
                    'label': _('Expire date'),
                    'required': False,
                    'type': 'text',
                    'help': "YYYY-MM-DD, exact match.",
                },
                'description': {
                    'label': _('Description'),
                    'required': False,
                    'type': 'text',
                },
            }

    headers = [
            ('Name', 'name'),
            ('Owner', 'owner'),
            ('Create date', 'create_date'),
            ('Expire date', 'expire_date'),
            ('Actions', '')
        ]

    def get_form(self):
        return self.SearchForm(self.transaction, **self.get_remembered())

    def get_searchers(self):
        form = self.form_values

        main = self.transaction.get_account_searcher()
        main.join_name = ''
        searchers = {'main': main}

        name = utils.web_to_spine(form.get('name', '').strip())
        if name:
            main.set_name_like(name)

        description = utils.web_to_spine(form.get('description', '').strip())
        if description:
            main.set_description_like(description)

        expire_date = form.get('expire_date', '').strip()
        if expire_date:
            date = utils.get_date(self.transaction, expire_date)
            main.set_expire_date(date)

        create_date = form.get('create_date', '').strip()
        if create_date:
            date = utils.get_date(self.transaction, create_date)
            main.set_create_date(date)

        spread = utils.web_to_spine(form.get('spread', '').strip())
        if spread:
            spreadsearcher = self.transaction.get_spread_searcher()
            account_type = self.transaction.get_entity_type('account')
            spreadsearcher.set_entity_type(account_type)
            spreadsearcher.set_name_like(spread)
            spreadsearcher.join_name = ''

            searcher = self.transaction.get_entity_spread_searcher()
            searcher.set_entity_type(account_type)
            searcher.join_name = 'entity'
            searchers['spread'] = searcher

            searcher.add_join('spread', spreadsearcher, spreadsearcher.join_name)
            main.add_intersection(main.join_name, searcher, searcher.join_name)

        return searchers
            
    def filter_rows(self, results):
        rows = []
        for elm in results:
            owner_name = utils.spine_to_web(utils.get_lastname_firstname(elm.get_owner()))
            owner = utils.object_link(elm.get_owner(), text=owner_name)
            cdate = utils.strftime(elm.get_create_date())
            edate = utils.strftime(elm.get_expire_date())
            edit = utils.object_link(elm, text='edit', method='edit', _class='action')
            remb = utils.remember_link(elm, _class='action')
            rows.append((utils.object_link(elm), owner, cdate, edate, str(edit)+str(remb)))
        return rows

class PersonSearcher(Searcher):
    """
    BUGS: Currently, if you've filled in both Affiliations and Affiliation Type, you must
          include another search term.
    """
    headers = [
        ('Name', ''),
        ('Date of birth', ''),
        ('Account(s)', ''),
        ('Affiliation(s)', ''),
        ('Actions', '')
    ]

    def get_searchers(self):
        searchers = {}

        form = self.form_values
        main = None

        person = self.transaction.get_person_searcher()
        person.join_name = ''
        searchers['person'] = person

        description = utils.web_to_spine(form.get('description', '').strip())
        if description:
            person.set_description_like("*%s*" % description)

        birthdate = form.get('birthdate', '').strip()
        if birthdate:
            date = utils.get_date(self.transaction, birthdate)
            person.set_birth_date(date)
            main = person

        name = utils.web_to_spine(form.get('name', '').strip())
        if name:
            name = '*' + name + '*'
            name = name.replace(" ", "*")
            variant = self.transaction.get_name_type('FULL')
            source = self.transaction.get_source_system('Cached')
            searcher = self.transaction.get_person_name_searcher()

            searcher.set_source_system(source)
            searcher.set_name_variant(variant)
            searcher.set_name_like(name)
            searcher.join_name = 'person'
            searchers['name'] = searcher

            if not main:
                main = searcher
            else:
                main.add_join(main.join_name, searcher, searcher.join_name)

        account_name = utils.web_to_spine(form.get('accountname', '').strip())
        if account_name:
            entity_type = self.transaction.get_entity_type('person')

            searcher = self.transaction.get_account_searcher()
            searcher.set_name_like(account_name)
            searcher.set_owner_type(entity_type)
            searcher.join_name = 'owner'
            searchers['account'] = searcher

            if not main:
                main = searcher
            #else:
            #    main.add_join(main.join_name, searcher, searcher.join_name)


        ou = utils.web_to_spine(form.get('ou', '').strip())
        if ou:
            s_ou = self.transaction.get_ou_searcher()
            s_ou.set_name_like(ou)
            ous = s_ou.search()

            if not ous:
                Messages.queue_message(
                    title='Not Found',
                    message="Could not find OU (%s)" % ou,
                    is_error=True)
                self.valid = False
            elif len(ous) > 1:
                Messages.queue_message(
                    title='Too Many Found',
                    message="Found more than one OU (%s)" % ou,
                    is_error=True)
                self.valid = False
            else:
                ou = ous[0]

                searcher = self.transaction.get_person_affiliation_searcher()
                searcher.set_ou(ou)
                searcher.join_name = 'person'
                searchers['ou_searcher'] = searcher

                if not main:
                    main = searcher
                else:
                    main.add_intersection(main.join_name, searcher, searcher.join_name)

        aff = utils.web_to_spine(form.get('aff', '').strip())
        if aff:
            s_aff = self.transaction.get_person_affiliation_type_searcher()
            s_aff.set_name_like(aff)
            affs = s_aff.search()

            if not affs:
                Messages.queue_message(
                        title="Not Found",
                        message="Could not find affiliation type (%s)" % aff,
                        is_error=True)
                self.valid = False
            elif len(affs) > 1:
                Messages.queue_message(
                        title="Too Many Found",
                        message="Found more than one affiliation type (%s)" % aff,
                        is_error=True)
                self.valid = False
            else:
                aff = affs[0]

                searcher = searchers.get('ou_searcher') or \
                    self.transaction.get_person_affiliation_searcher()
                searcher.join_name = 'person'
                searcher.set_affiliation(aff)

                if not main:
                    main = searcher
                else:
                    main.add_intersection(main.join_name, searcher, searcher.join_name)

        if not main:
            main = person

        ## always use last name for sorting order
        person_orderby_name = self.transaction.get_person_name_searcher()
        person_orderby_name.set_name_variant(self.transaction.get_name_type('LAST'))
        person_orderby_name.set_source_system(self.transaction.get_source_system('Cached'))
        main.add_join(main.join_name, person_orderby_name, 'person')
        main.order_by(person_orderby_name, 'name')

        searchers['main'] = main
        return searchers

    def filter_rows(self, results):
        rows = []
        for obj in results:
            attr = self.searchers['main'].join_name
            if attr:
                pers = getattr(obj, 'get_' + attr)()
            else:
                pers = obj

            date = utils.strftime(pers.get_birth_date())
            ## to get norwegian characters displayed
            affs = []
            for i in pers.get_affiliations()[:3]:
                linktext = utils.spine_to_web(i.get_ou().get_name())
                affs.append(utils.object_link(i.get_ou(), text=linktext))
            ## affs = [str(utils.object_link(i.get_ou())) for i in pers.get_affiliations()[:3]]
            affs = ', '.join(affs[:2]) + (len(affs) == 3 and '...' or '')
            ## to get norwegian characters displayed
            accs = []
            for i in pers.get_accounts()[:3]:
                linktext = utils.spine_to_web(i.get_name())
                accs.append(utils.object_link(i, text=linktext))
            ## accs = [str(utils.object_link(i)) for i in pers.get_accounts()[:3]]
            accs = ', '.join(accs[:2]) + (len(accs) == 3 and '...' or '')
            edit = utils.object_link(pers, text='edit', method='edit', _class='action')
            linktext = utils.spine_to_web(utils.get_lastname_firstname(pers))
            remb = utils.remember_link(pers, _class="action")
            rows.append([utils.object_link(pers, text=linktext), date, accs, affs, str(edit)+str(remb)])
              
        return rows

class AllocationPeriodSearcher(Searcher):
    headers = (('Name', 'name'),
               ('Allocation Authority', 'allocationauthority'),
               ('Actions', ''),
    )

    def get_searchers(self):
        form = self.form_values
        main = self.transaction.get_allocation_period_searcher()
        searchers = {'main': main}

        name = utils.web_to_spine(form.get('name', '').strip())
        if name:
            main.set_name_like(name)

        authority = utils.web_to_spine(form.get('allocationauthority', '').strip())
        if authority:
            main.set_allocationauthority_like(authority)
        return searchers

    def filter_rows(self, results):
        rows = []
        for elm in results:
            edit = utils.object_link(elm, text='edit', method='edit', _class='action')
            remb = utils.remember_link(elm, _class='action')
            auth = utils.spine_to_web(elm.get_authority().get_name())
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

    def get_searchers(self):
        form = self.form_values
        main = self.transaction.get_allocation_searcher()
        searchers = {'main': main}

        allocation_name = utils.web_to_spine(form.get('allocation_name', '').strip())
        if allocation_name:
            an_searcher = self.transaction.get_project_allocation_name_searcher()
            an_searcher.set_name_like(allocation_name)
            self.searchers['allocation_name'] = an_searcher
            self.searchers['main'].add_join('allocation_name', an_searcher, '')

        return searchers

    def filter_rows(self, results):
        rows = []
        for elm in results:
            edit = utils.object_link(elm, text='edit', method='edit', _class='action')
            remb = utils.remember_link(elm, _class='action')
            proj = utils.object_link(elm.get_allocation_name().get_project())
            period = utils.spine_to_web(elm.get_period().get_name())
            status = utils.spine_to_web(elm.get_status().get_name())
            machines = [utils.spine_to_web(m.get_name()) for m in elm.get_machines()]
            machines = "(%s)" % ",".join(machines)
            rows.append([utils.object_link(elm), period, status, machines, str(edit)+str(remb)])
        return rows

class DiskSearcher(Searcher):
    headers = (
        ('Path', 'path'),
        ('Host', ''),
        ('Description', 'description'),
        ('Actions', '')
    )
   
    def get_searchers(self):
        form = self.form_values
        main = self.transaction.get_disk_searcher()

        path = utils.web_to_spine(form.get('path', '').strip())
        if path:
            main.set_path_like(path)

        description = utils.web_to_spine(form.get('description', '').strip())
        if description:
            main.set_description_like(description)

        return {'main': main}


    def filter_rows(self, results):
        rows = []
        for elm in results:
            ## should convert charset?
            path = utils.object_link(elm, text=elm.get_path())
            host = utils.object_link(elm.get_host())
            edit = utils.object_link(elm, text='edit', method='edit', _class='action')
            remb = utils.remember_link(elm, _class='action')
            rows.append([path, host, utils.spine_to_web(elm.get_description()), str(edit)+str(remb)])
        return rows

class EmailDomainSearcher(Searcher):
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
            edit = utils.object_link(elm, text='edit', method='edit', _class='action')
            remb = utils.remember_link(elm, _class='action')
            rows.append([link, utils.spine_to_web(elm.get_description()), cats, str(edit)+str(remb)])
        return rows

class GroupSearcher(Searcher):
    headers = (
        ('Group name', 'name'),
        ('Description', 'description'),
        ('Actions', '')
    )

    def get_searchers(self):
        form = self.form_values
        main = self.transaction.get_group_searcher()

        name = utils.web_to_spine(form.get('name', '').strip())
        if name:
            main.set_name_like(name)

        description = utils.web_to_spine(form.get('description', '').strip())
        if description:
            main.set_description_like(description)

        gid_end = utils.web_to_spine(form.get('gid_end', '').strip())
        if gid_end:
            if gid_end:
                main.set_posix_gid_less_than(int(gid_end))

        gid = form.get('gid', '').strip()
        if gid:
            gid_option = self.form_values['gid_option']
            if gid_option == "exact":
                self.searchers['main'].set_posix_gid(int(gid))
            elif gid_option == "above":
                self.searchers['main'].set_posix_gid_more_than(int(gid))
            elif gid_option == "below":
                self.searchers['main'].set_posix_gid_less_than(int(gid))
            elif gid_option == "range":
                self.searchers['main'].set_posix_gid_more_than(int(gid))
                
        spread = utils.web_to_spine(form.get('spread', '').strip())
        if spread:
            group_type = self.transaction.get_entity_type('group')

            searcher = self.transaction.get_entity_spread_searcher()
            searcher.set_entity_type(group_type)

            spreadsearcher = self.transaction.get_spread_searcher()
            spreadsearcher.set_entity_type(group_type)
            spreadsearcher.set_name_like(spread) 
            
            searcher.add_join('spread', spreadsearcher, '')
            main.add_intersection('', searcher, 'entity')

        return {'main': main}

    def filter_rows(self, results):
        rows = []
        for elm in results:
            edit = utils.object_link(elm, text='edit', method='edit', _class='action')
            remb = utils.remember_link(elm, _class='action')
            rows.append([utils.object_link(elm), utils.spine_to_web(elm.get_description()), str(edit)+str(remb)])
        return rows

class HostSearcher(Searcher):
    def get_searchers(self):
        main = self.transaction.get_host_searcher()
        form = self.form_values

        name = form.get('name', '')
        if name:
            name = utils.web_to_spine(name)
            main.set_name_like(name)

        description = form.get('description', '')
        if description:
            description = utils.web_to_spine(description)
            main.set_description_like(description)

        return {'main': main}

    def filter_rows(self, results):
        rows = []
        for elm in results:
            edit = utils.object_link(elm, text='edit', method='edit', _class='action')
            remb = utils.remember_link(elm, _class='action')
            desc = elm.get_description()
            if desc:
                desc = utils.spine_to_web(desc)
            rows.append([utils.object_link(elm), desc, str(edit)+str(remb)])
        return rows

class OUSearcher(Searcher):
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
            edit = utils.object_link(elm, text='edit', method='edit', _class='action')
            remb = utils.remember_link(elm, _class='action')
            acro = utils.spine_to_web(elm.get_acronym())
            short = utils.spine_to_web(elm.get_short_name())
            rows.append([link, acro, short, str(edit)+str(remb)])
        return rows

class ProjectSearcher(Searcher):
    headers = (
        ('Title', 'title'),
        ('Science', 'science'),
        ('Owner', 'owner'),
        ('Actions', '')
    )

    def get_searchers(self):
        main = self.transaction.get_project_searcher()
        form = self.form_values
        
        name = utils.web_to_spine(form.get('name', '').strip())
        if name:
            main.set_name_like(name)

        description = utils.web_to_spine(form.get('description', '').strip())
        if description:
            main.set_description_like(description)

        title = utils.web_to_spine(forrm.get('title', '').strip())
        if title:
            main.set_title_like(title)

        return {'main': main}

    def filter_rows(self, results):
        rows = []
        for elm in results:
            edit = utils.object_link(elm, text='edit', method='edit', _class='action')
            remb = utils.remember_link(elm, _class='action')
            sci  = " " #elm.get_science().get_name()
            ownr = utils.object_link(elm.get_owner())
            rows.append([utils.object_link(elm), sci, ownr, str(edit)+str(remb)])
        return rows

class PersonAffiliationsSearcher(Searcher):
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
    def search(self):
        """Executes the search and returns the result."""
        if not self.is_valid():
            return
    
        vargs = self.form_values
        tr = self.transaction

        id = utils.web_to_spine(vargs.get('id', '').strip())
        ou = tr.get_ou(int(id))
        perspective = utils.web_to_spine(vargs.get('source', '').strip())
        affiliation = utils.web_to_spine(vargs.get('affiliation','').strip())
        withoutssn = utils.web_to_spine(vargs.get('withoutssn', '').strip())
        recursive = utils.web_to_spine(vargs.get('recursive', '').strip())
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

    def get_results(self):
        results = self.search()
        rows = self.filter_rows(results)
        #hits = self.searchers['main'].length()
        #hits = len(results)
        hits = self.len
        headers = self.create_table_headers()
        offset = self.url_args['offset']
        result = {
            'headers': headers,
            'rows': rows,
            'url': self.url,
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

