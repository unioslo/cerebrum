#!/usr/bin/env python2.2
# -*- coding: iso-8859-1 -*-

# Copyright 2003 University of Oslo, Norway
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

import cerebrum_path
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules import Email

db = Factory.get('Database')()
co = Factory.get('Constants')(db)
dom = Email.EmailDomain(db)

def is_uio_domain(domain):
    domain = "." + domain
    return (domain == '.UIO_HOST' or
            (domain.endswith('.uio.no') and
             not domain.endswith('.ifi.uio.no')))

def main():
    for row in dom.list_email_domains():
        domain = row['domain']
        if is_uio_domain(domain):
            try:
                dom.clear()
                dom.find_by_domain(row['domain'])
                for ctg in dom.get_categories():
                    if ctg == co.email_domain_category_uio_globals:
                        break
                else:
                    dom.add_category(co.email_domain_category_uio_globals)
                    print "Added: %d: %s" % (dom.email_domain_id, domain)
            except Errors.NotFoundError:
                print "Not fround: %s" % domain
        else:
            print "Omitted: %s" % domain
    db.commit()


if __name__ == '__main__':
    main()
