#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2002-2018 University of Oslo, Norway
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
Write organization, person and alias information to an LDIF file (if
enabled in cereconf), which can then be loaded into LDAP.

If --omit-mail-module, mail addresses are read from the contact_info
table instead of from Cerebrum's e-mail tables.  That's useful for
installations without the mod_email module.
"""

from __future__ import unicode_literals

import argparse
import logging

import six

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Utils import Factory, make_timer
from Cerebrum.modules.LDIFutils import ldif_outfile, end_ldif_outfile

logger = logging.getLogger(__name__)


def main(inargs=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '-o', '--output',
        type=six.text_type,
        dest='output',
        help='output file')
    parser.add_argument(
        '-m,', '--omit-mail-module',
        action='store_true',
        dest='omit_mail_module',
        help='omit the email module')
    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)

    db = Factory.get('Database')()
    ldif = Factory.get('OrgLDIF')(db)
    timer = make_timer(logger, 'Starting dump.')

    default_output = ldif_outfile('ORG', args.output)
    ldif.generate_org_object(default_output)

    ou_output = ldif_outfile('OU',
                             default=default_output,
                             explicit_default=args.output)
    ldif.generate_ou(ou_output)

    person_output = ldif_outfile('PERSON',
                                 default=default_output,
                                 explicit_default=args.output)
    ldif.generate_person(outfile=person_output,
                         alias_outfile=ou_output,
                         use_mail_module=not args.omit_mail_module)

    end_ldif_outfile('PERSON',
                     outfile=person_output,
                     default_file=default_output)
    end_ldif_outfile('OU',
                     outfile=ou_output,
                     default_file=default_output)
    end_ldif_outfile('ORG', outfile=default_output)
    timer("Dump done.")


if __name__ == '__main__':
    main()
