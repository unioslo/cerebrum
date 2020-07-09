#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2002-2020 University of Oslo, Norway
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
Write an organization LDIF file.

Writes organization, person and alias information to an LDIF file (if
enabled in cereconf), which can then be loaded into LDAP.

If --omit-mail-module, mail addresses are read from the contact_info
table instead of from the Cerebrum e-mail tables.  That's useful for
installations without the mod_email module.
"""
from __future__ import unicode_literals

import argparse
import logging

import six

import cereconf
import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Utils import Factory, make_timer
from Cerebrum.modules.OrgLDIF import OrgLdifConfig

logger = logging.getLogger(__name__)


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description=__doc__,
    )
    parser.add_argument(
        '-o', '--output',
        dest='output',
        type=six.text_type,
        help="Write to %(metavar)s (default: LDAP_ORG['file'])",
        metavar='<filename>',
    )
    parser.add_argument(
        '--max-change',
        dest='max_change',
        type=int,
        default=None,
        help=("Require changes < %(metavar)s%%"
              " (default: LDAP_ORG['max_change'])"),
        metavar='<percent>',
    )
    # TODO: This should really be defined by each instance, and not by a
    #       cli-option - as it is mainly controlled by support for mod_email
    parser.add_argument(
        '-m,', '--omit-mail-module',
        dest='use_mail_module',
        action='store_false',
        default=True,
        help='Do not use the email module for email addrs',
    )
    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)

    # TODO: Add some sort of option/parser callback support in OrgLDIF, so we
    # can provide cli-args for things like 'entitlement_file', if supported.

    Cerebrum.logutils.autoconf('cronjob', args)

    config = OrgLdifConfig.get_default(module=cereconf)
    db = Factory.get('Database')()
    ldif = Factory.get('OrgLDIF')(db, config=config)

    timer = make_timer(logger, 'Starting dump.')

    default_output = config.org.start_outfile(filename=args.output,
                                              max_change=args.max_change)
    ldif.generate_org_object(default_output)

    ou_output = config.ou.start_outfile(
        default=default_output,
        explicit_default=args.output,
    )
    ldif.generate_ou(ou_output)

    person_output = config.person.start_outfile(
        default=default_output,
        explicit_default=args.output,
    )
    ldif.generate_person(
        outfile=person_output,
        alias_outfile=ou_output,
        use_mail_module=args.use_mail_module,
    )

    logger.info('OrgLDIF written to %s', repr(default_output))

    config.person.end_outfile(outfile=person_output,
                              default_file=default_output)
    config.ou.end_outfile(outfile=ou_output, default_file=default_output)
    config.org.end_outfile(outfile=default_output)

    timer("Dump done.")


if __name__ == '__main__':
    main()
