#!/usr/bin/env python2.2
# -*- coding: iso-8859-1 -*-

# Copyright 2002, 2003 University of Oslo, Norway
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
import xml.sax
import sys
import getopt
import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules import Email

db = Factory.get('Database')()
co = Factory.get('Constants')(db)

def is_uio_domain(domain):
    domain = "." + domain
    return (domain == '.UIO_HOST' or
            (domain.endswith('.uio.no') and
             not domain.endswith('.ifi.uio.no')))

def create_uio_globals(data):
    dom = Email.EmailDomain(db)
    for d in data:
        dom.clear()
        if d == "domain":
            if is_uio_domain(data[d]):
                try:
                    dom.find_by_domain(data[d])
                    dom.add_category(co.email_domain_category_uio_globals)
                    print "Added: %d: %s" % (dom.email_domain_id, data[d])
                except Errors.NotFoundError:
                    print "Not fround: %s" % data[d]
            else:
                print "Omitted: %s" % data[d]
                
class MailDataParser(xml.sax.ContentHandler):

    def __init__(self, callback):
        self.callback = callback

    def startElement(self, name, attrs):
        tmp = {}
        for k in attrs.keys():
            tmp[k.encode('iso8859-1')] = attrs[k].encode('iso8859-1')
        if name == 'email':
            pass
        elif name == 'emaildomain':
            self.callback(tmp)
        else:
            pass

def import_email(filename, callback):
    try:
        xml.sax.parse(filename, MailDataParser(callback))
    except StopIteration:
        pass
    db.commit()


if __name__ == '__main__':
    try:
        opts, args = getopt.getopt(sys.argv[1:],"m:","mail-file=")
    except getopt.GetoptError:
        usage()
        sys.exit(2)

    mfile = ""
        
    for o, a in opts:
        if o in ('-m', '--mail-file'):
            mfile = a

    if mfile == "":
        usage()
        
    import_email(mfile, create_uio_globals)


