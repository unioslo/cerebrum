import cgi
import urllib
import config
from utils import object_link, strftime
from WorkList import remember_link

class Searcher(object):
    """Simplified search handler interface.

        'headers' should be a list where each element contains the name
        for that particular header and optionaly the name for the attribute
        it should be sorted after.
    """

    headers = []

    defaults = {
        'offset': 0,
        'orderby': '',
        'orderby_dir': '',
        'redirect': '',
    }

    def __init__(self, transaction, *args, **vargs):
        self.transaction = transaction
        self.form_values = self.init_values(*args, **vargs)
        self.options = Searcher.defaults.copy()
        for key, value in Searcher.defaults.items():
            if type(value) == int:
                self.options[key] = int(vargs.get(key, value))
            else:
                self.options[key] = vargs.get(key, value)

        self.url_args = dict(self.form_values.items() + self.options.items())
        self.searcher = self.get_searcher()
        self.init_searcher()

    def init_searcher(self):
        """This method configures the searcher based on
        the contents of the args and vargs variables.
        """

        import cherrypy

        orderby = self.options['orderby']
        orderby_dir = self.options['orderby_dir']
        self.options['offset'] = offset = int(self.options['offset'])
        self.max_hits = min(
            int(cherrypy.session['options'].getint('search', 'display hits')),
            config.conf.getint('cereweb', 'max_hits'))
        searcher = self.searcher

        if orderby:
            if orderby_dir == 'desc':
                searcher.order_by_desc(searcher, orderby)
            else:
                searcher.order_by(searcher, orderby)

        if not offset:
            searcher.set_search_limit(self.max_hits, 0)
        else:
            searcher.set_search_limit(self.max_hits, int(offset))

        for (key, value) in self.form_values.items():
            func = getattr(self, key)
            func(value)

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
        
        return cgi.escape('search?%s' % (urllib.urlencode(url_args))), current

    def get_results(self):
        hits = self.searcher.length()
        offset = self.url_args['offset'] 
        result = {
            'headers': self.create_table_headers(),
            'rows': self.filter_rows(self.search()),
            'url_args': self.url_args,
            'hits': hits,
            'is_paginated': hits > self.max_hits,
            'results_per_page': min(hits, offset + self.max_hits),
            'has_next': offset < hits,
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

    def filter_rows(self, rows):
        return [(row,) for row in rows]

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
            return self.searcher.search()

    def is_valid(self):
        return self.form_values and True or False

class AccountSearcher(Searcher):
    headers = [
            ('Name', 'name'),
            ('Owner', 'owner'),
            ('Create date', 'create_date'),
            ('Expire date', 'expire_date'),
            ('Actions', '')
        ]

    def get_searcher(self):
        return self.transaction.get_account_searcher()

    def name(self, name):
        self.searcher.set_name_like(name)

    def expire_date(self, expire_date):
        if not legal_date(expire_date):
            raise Exception(('expire_date', "Not a legal date."))
        date = self.transaction.get_commands().strptime(expire_date, "%Y-%m-%d")
        self.searcher.set_expire_date(date)

    def create_date(self, create_date):
        if not legal_date(create_date):
            raise Exception(('create_date', "Not a legal date."))
        date = self.transaction.get_commands().strptime(create_date, "%Y-%m-%d")
        self.searcher.set_create_date(date)

    def description(self, description):
        if not description.startswith('*'):
            description = '*' + description
        if not description.endswith('*'):
            description += '*'
        self.search.set_description_like(description)

    def spread(self, spread):
        account_type = self.transaction.get_entity_type('account')

        entityspread = self.transaction.get_entity_spread_searcher()
        entityspread.set_entity_type(account_type)

        spreadsearcher = self.transaction.get_spread_searcher()
        spreadsearcher.set_entity_type(account_type)
        spreadsearcher.set_name_like(spread)

        entityspread.add_join('spread', spreadsearcher, '')
        self.search.add_intersection('', entityspread, 'entity')
            
    def filter_rows(self, results):
        rows = []
        for elm in results:
            owner = object_link(elm.get_owner())
            cdate = strftime(elm.get_create_date())
            edate = strftime(elm.get_expire_date())
            edit = object_link(elm, text='edit', method='edit', _class='action')
            remb = remember_link(elm, _class='action')
            rows.append((object_link(elm), owner, cdate, edate, str(edit)+str(remb)))
        return rows
