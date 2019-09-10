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

# Save default values of LDAP vars which cereconf will modify.
# Must be done before anything imports cereconf.
from Cerebrum import default_config as _d
_save = map(dict.copy, (_d.LDAP, _d.LDAP_ORG, _d.LDAP_OU, _d.LDAP_PERSON))
# Restore the default values to cereconf and default_config.
import cereconf as _c
(_c.LDAP, _c.LDAP_ORG, _c.LDAP_OU, _c.LDAP_PERSON) = \
    (_d.LDAP, _d.LDAP_ORG, _d.LDAP_OU, _d.LDAP_PERSON) = _save
del _c, _d, _save

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Utils import Factory, make_timer
from Cerebrum.modules.LDIFutils import ldif_outfile, end_ldif_outfile


logger = logging.getLogger(__name__)


def generate_dump(db, filename, use_mail_module):
    ldif = Factory.get('OrgLDIF')(db, logger.getChild('OrgLDIF'))

    timer = make_timer(logger, 'Starting dump')
    outfile = ldif_outfile('ORG', filename)
    logger.debug('writing org data to %r', outfile)

    timer('Generating org data...')
    ldif.generate_org_object(outfile)

    ou_outfile = ldif_outfile('OU', default=outfile, explicit_default=filename)
    logger.debug('Writing ou data to %r', outfile)
    timer('Generating ou data...')
    ldif.generate_ou(ou_outfile)

    pers_outfile = ldif_outfile('PERSON',
                                default=outfile,
                                explicit_default=filename)
    logger.debug('Writing person data to %r', outfile)
    timer('Generating person data...')
    ldif.generate_person(pers_outfile, ou_outfile, use_mail_module)

    end_ldif_outfile('PERSON', pers_outfile, outfile)
    end_ldif_outfile('OU', ou_outfile, outfile)
    end_ldif_outfile('ORG', outfile)
    timer("Dump done")


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description='Generate org.ldif for randsone units',
    )
    parser.add_argument(
        '-o', '--org',
        dest='filename',
        help='Write dump to %(metavar)s',
        metavar='<filename>',
    )
    parser.add_argument(
        '-i', '--inst',
        dest='unit',
        type=str,
        required=True,
        help='Fetch settings from %(metavar)_ldap_conf',
        metavar='<unit>',
    )
    parser.add_argument(
        '-m', '--omit-mail-module',
        dest='use_mail_module',
        action='store_false',
        default=True,
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
        importlib.import_module(module_name)
    except ImportError:
        logger.error("Unable to import module_name=%r", module_name,
                     exc_info=True)
        raise SystemExit("Invalid configuration module %r" % (module_name, ))

    db = Factory.get('Database')()
    generate_dump(db, args.filename, args.use_mail_module)
    logger.info("Done %s", parser.prog)


if __name__ == '__main__':
    main()
