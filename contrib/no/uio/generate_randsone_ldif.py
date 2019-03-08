#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2002-2017 University of Oslo, Norway
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

"""Usage: generate_randsone_ldif.py [options]

Write FEIDE information to an LDIF file for Randsone organizations
affiliated to UiO.  Like generate_org_ldif, but reads an <inst>conf
file which can override some cereconf LDAP variables.
"""

import getopt
import sys
import importlib


# Save default values of LDAP vars which cereconf will modify.
# Must be done before anything imports cereconf.
from Cerebrum import default_config as _d
_save = map(dict.copy, (_d.LDAP, _d.LDAP_ORG, _d.LDAP_OU, _d.LDAP_PERSON))
# Restore the default values to cereconf and default_config.
import cereconf as _c
(_c.LDAP, _c.LDAP_ORG, _c.LDAP_OU, _c.LDAP_PERSON) = \
    (_d.LDAP, _d.LDAP_ORG, _d.LDAP_OU, _d.LDAP_PERSON) = _save
del _c, _d, _save

from Cerebrum.Utils import Factory, make_timer
from Cerebrum.modules.LDIFutils import ldif_outfile, end_ldif_outfile


def main():
    logger = Factory.get_logger("cronjob")

    # The script is designed to use the mail-module.
    module_name = None
    unit = None
    use_mail_module = True
    config = ofile = None
    try:
        opts, args = getopt.getopt(sys.argv[1:], "ho:i:m",
                                   ("help", "org=", "inst=",
                                    "omit-mail-module"))
    except getopt.GetoptError, e:
        usage(str(e))
    if args:
        usage("Invalid arguments: " + " ".join(args))
    for opt, val in opts:
        if opt in ("-o", "--org"):
            ofile = val
        elif opt in ("-i", "--inst"):
                unit = str(val)
                module_name = str(unit)+'_ldap_conf'
        elif opt in ("-m", "--omit-mail-module"):
            use_mail_module = False
        else:
            usage()
    if not unit:
        usage("\nThe -i or --inst option must be provided with valid argument")
        return 1
    # The following overrides some imported values from cereconf.
    try:
        importlib.import_module(module_name)
    except:
        usage("\nNo configuration with a file name %s found, aborting"
              % module_name)
        return 1

    ldif = Factory.get('OrgLDIF')(Factory.get('Database')(), logger)
    timer = make_timer(logger, 'Starting dump.')
    outfile = ldif_outfile('ORG', ofile)
    ldif.generate_org_object(outfile)
    ou_outfile = ldif_outfile('OU', default=outfile, explicit_default=ofile)
    ldif.generate_ou(ou_outfile)
    pers_outfile= ldif_outfile('PERSON',default=outfile,explicit_default=ofile)
    ldif.generate_person(pers_outfile, ou_outfile, use_mail_module)
    end_ldif_outfile('PERSON', pers_outfile, outfile)
    end_ldif_outfile('OU', ou_outfile, outfile)
    end_ldif_outfile('ORG', outfile)
    timer("Dump done.")


def usage(err=0):
    if err:
        print >>sys.stderr, err
    print >>sys.stderr, __doc__
    sys.exit(bool(err))


if __name__ == '__main__':
        main()
