#!/usr/bin/env python2.2

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

import time
import sys

import cerebrum_path
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules import Email

Cerebrum = Factory.get('Database')()
co = Factory.get('Constants')(Cerebrum)
mail_addr = Email.EmailAddress(Cerebrum)
mail_dom = Email.EmailDomain(Cerebrum)
mail_targ = Email.EmailTarget(Cerebrum)

targ2addr = {}
targets = []


def read_addr():
    for row in mail_addr.get_all_email_addresses():

        id = Cerebrum.pythonify_data(row['address_id'])
        mail_addr.clear()
        mail_addr.find(id)
        targ_id = mail_addr.get_target_id()

        targ2addr.setdefault(int(targ_id), []).append(id)


def read_targ():
    for row in mail_targ.get_all_email_targets():

        id = Cerebrum.pythonify_data(row['target_id'])
        mail_targ.clear()
        mail_targ.find(id)
    
        targets.append(id)


def write_ldif():
    for t in targets:
        mail_targ.clear()
        mail_targ.find(t)
        
        print "dn: cn=a%s,ou=mail,dc=uio,dc=no" % t
        print "objectClass: top"

        if targ2addr.has_key(t):
            for a in targ2addr[t]:
                mail_addr.clear()
                mail_addr.find(a)
                dom_id = mail_addr.get_domain_id()
                mail_dom.clear()
                mail_dom.find(dom_id)
                print "mail: %s@%s" % ( mail_addr.get_localpart(),
                                        mail_dom.get_domain_name() )
        print "\n"

def main():
    read_addr()
    read_targ()
    write_ldif()


if __name__ == '__main__':
    main()
