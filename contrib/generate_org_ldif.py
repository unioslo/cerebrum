#!/usr/bin/env python2.2
# -*- coding: iso-8859-1 -*-
# Copyright 2002, 2003, 2004 University of Oslo, Norway
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

"""Usage: generate_org_ldif.py [options]

Write organization, person and alias information to an LDIF file (if
enabled in cereconf), which can then be loaded into LDAP.

Options:
    -o <outfile> | --org=<outfile> : Set ouput file.
    -m | --omit-mail-module        : Omit the mail module in Cerebrum.
    -h | --help                    : This help text.

If --omit-mail-module, mail addresses are read from the contact_info
table instead of from Cerebrum's e-mail tables.  That's useful for
installations without the mod_email module."""

import getopt, sys
import cerebrum_path, cereconf
from Cerebrum.Utils   import Factory, SimilarSizeWriter
from Cerebrum.modules import LDIFutils

def main():
    # The script is designed to use the mail-module.
    use_mail_module = True
    ofile = None
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'ho:m',
                                   ('help', 'org=', 'omit-mail-module'))
    except getopt.GetoptError, e:
        usage("\n" + str(e))
    if args:
        usage("\n" "Invalid arguments: %s" % " ".join(args))
    for opt, val in opts:
        if opt in ('-o', '--org'):
            ofile = val
        elif opt in ('-m', '--omit-mail-module'):
            use_mail_module = False
            sys.stderr.write(
                "Warning: Option --omit-mail-module (-m) is untested.\n")
        else:
            usage()

    logger  = Factory.get_logger("console")
    ldif    = Factory.get('OrgLDIF')(Factory.get('Database')(), logger)
    timer   = ldif.make_timer("Starting dump.")
    outfile = SimilarSizeWriter(ofile or (cereconf.LDAP_DUMP_DIR + '/'
                                          + cereconf.LDAP_ORG_FILE    ))
    outfile.set_size_change_limit(10)
    ldif.generate_base_object(outfile)
    ldif.generate_org(outfile)
    ldif.generate_person(outfile, use_mail_module)
    LDIFutils.add_ldif_file(outfile, cereconf.LDAP_ORG_ADD_LDIF_FILE)
    outfile.close()
    timer("Dump done.")

def usage(exitcode=0):
    print __doc__
    sys.exit(exitcode)

if __name__ == '__main__':
    	main()

# arch-tag: 67ab2aa3-9a05-4ece-a9ff-0c068be632dd
