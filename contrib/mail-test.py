#!/usr/bin/env python2.2

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

import time
import sys

import cerebrum_path
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules import Email

Cerebrum = Factory.get('Database')()
co = Factory.get('Constants')(Cerebrum)


def add_address(args):
    mail_addr = Email.EmailAddress(Cerebrum)
    mail_dom = Email.EmailDomain(Cerebrum)
    mail_targ = Email.EmailTarget(Cerebrum)

    try:
        address = args[0]
        target = args[1]
    except:
        print "Need mail-address and target for add."
        sys.exit()

    try:
        lp, dp = address.split('@')
    except ValueError:
        print "email-address must contain a '@'."
        sys.exit()

    try:
        mail_dom.find_by_domain(dp)
    except Errors.NotFoundError:
        print "Couldn't find domain '",dp,"'\n"
        sys.exit()

    try:
        mail_targ.find(int(target))
    except Errors.NotFoundError:
        print "Couldn't find target '",target,"'\n"
        sys.exit()

    
    mail_addr.populate(lp, mail_dom.email_domain_id, mail_targ.email_target_id)
    mail_addr.write_db()
    mail_addr.commit()

def add_domain(args):
    mail_dom = Email.EmailDomain(Cerebrum)

    try:
        domain = args[0]
        cat = args[1]
        desc = args[2]
    except:
        print "Need domain, category and description for add."
        sys.exit()

    try:
        mail_dom.populate(domain, int(cat), desc)
        mail_dom.write_db()
        mail_dom.commit()
    except:
        print "error in add_domain!!!"
        sys.exit()


def add_target(args):
    mail_targ = Email.EmailTarget(Cerebrum)

    try:
        type = args[0]
    except:
        print "Need type for add."
        sys.exit()

    try:
        mail_targ.populate(type)
        mail_targ.write_db()
        mail_targ.commit()
    except:
        print "error in add_target!!!"
        sys.exit()


def main():
    def parse_args():
        arg = []
        for i in range(2, len(sys.argv)):
            arg.append(sys.argv[i])
        return arg
                     
    if len(sys.argv) < 2:
       die()
    else:
        s = sys.argv[1]
        arg = parse_args()
        if   s == "-a": add_address(arg)
        elif s == "-d": add_domain(arg)
        elif s == "-t": add_target(arg)
        else: die()
            


def die():
    print "Give some arg!"
    sys.exit()



if __name__ == '__main__':
    main()
