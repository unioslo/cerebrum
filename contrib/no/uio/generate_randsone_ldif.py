#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2002-2019 University of Oslo, Norway
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
Generate an organization ldif file using an alternative configuration module.

This script will generate an organization.ldif, just like
`contrib/generate_org_ldif.py`, but using LDAP_ORG, LDAP_OU and LDAP_PERSON
settings from another module.

The configuration module should be importable, and named <inst>_ldap_conf
"""
import argparse
import importlib
import logging

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Utils import Factory, make_timer
from Cerebrum.modules.OrgLDIF import OrgLdifConfig
from Cerebrum.utils.module import make_class


logger = logging.getLogger(__name__)


def generate_dump(ldif, filename, max_change, use_mail_module):
    timer = make_timer(logger, 'Starting dump')
    config = ldif.config

    outfile = config.org.start_outfile(filename=filename,
                                       max_change=max_change)
    logger.debug('writing org data to %r', outfile)
    timer('Generating org data...')
    ldif.generate_org_object(outfile)

    ou_outfile = config.ou.start_outfile(default=outfile,
                                         explicit_default=filename)
    logger.debug('Writing ou data to %r', ou_outfile)
    timer('Generating ou data...')
    ldif.generate_ou(ou_outfile)

    pers_outfile = config.person.start_outfile(default=outfile,
                                               explicit_default=filename)
    logger.debug('Writing person data to %r', pers_outfile)
    timer('Generating person data...')
    ldif.generate_person(pers_outfile, ou_outfile, use_mail_module)

    logger.info('OrgLDIF written to %s', repr(outfile))

    config.person.end_outfile(pers_outfile, outfile)
    config.ou.end_outfile(ou_outfile, outfile)
    config.org.end_outfile(outfile)

    timer("Dump done")


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description='Generate org.ldif for randsone units',
    )
    parser.add_argument(
        '-o', '--org',
        dest='filename',
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
    parser.add_argument(
        '-i', '--inst',
        dest='unit',
        type=str,
        required=True,
        help='Fetch settings from %(metavar)s_ldap_conf',
        metavar='<unit>',
    )
    parser.add_argument(
        '-m', '--omit-mail-module',
        dest='use_mail_module',
        action='store_false',
        default=True,
        help='Do not use the email module for email addrs',
    )
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)

    logger.info('Start %s', parser.prog)
    logger.debug('args: %s', repr(args))

    module_name = args.unit + '_ldap_conf'

    # The following overrides some imported values from cereconf.
    logger.info('Importing module_name=%r', module_name)
    try:
        ldif_conf = importlib.import_module(module_name)
    except ImportError:
        logger.error("Unable to import module_name=%r", module_name,
                     exc_info=True)
        raise SystemExit("Invalid configuration module %r" % (module_name, ))

    org_ldif_cls = make_class(ldif_conf.CLASS_ORGLDIF)
    config = OrgLdifConfig.get_default(module=ldif_conf)

    db = Factory.get('Database')()
    ldif = org_ldif_cls(db, config=config)

    generate_dump(ldif, args.filename, args.max_change, args.use_mail_module)

    logger.info("Done %s", parser.prog)


if __name__ == '__main__':
    main()
