#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2020 University of Oslo, Norway
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
Write sysadm users to a separate LDAP tree.

This scripts writes an LDIF similar to `generate_org_ldif.py` at UiO, but with
sysadm users.

.. todo::
    It should be possible to build a single script that performs the tasks of
    generate{org,randsone,sysadm}_ldif.py

Configuration
-------------
This script requires a ``sysadm_ldif_conf`` python module to exist, with the
following cereconf-like attributes/settings:

``CLASS_ORGLDIF``
    A tuple of base classes to use.  For now this value should be
    ``Cerebrum.modules.no.uio.sysadm_ldif/SysAdmOrgLdif``

``INSTITUTION_DOMAIN_NAME``
    Value for ``OrgLdifConfig.domain_name``.  Used by schacHomeOrganization and
    related attributes.

``DEFAULT_INSTITUSJONSNR``
    Value for ``OrgLdifConfig.org_id``.  Used by norEduOrgUniqueID and related
    attribtues.

``LDAP``
    Base settings for LDAP exports.

``LDAP_ORG``
    Common settings for OrgLDIF

``LDAP_OU``
    Settings for OU tree

``LDAP_PERSON``
    Settings for person/account tree.
"""
from __future__ import print_function, unicode_literals

import argparse
import importlib
import logging

import six

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Utils import Factory, make_timer
from Cerebrum.modules.OrgLDIF import OrgLdifConfig
from Cerebrum.utils.module import make_class


logger = logging.getLogger(__name__)


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description="Feide sysadm users tree",
    )
    parser.add_argument(
        '-o', '--output',
        dest='filename',
        required=True,
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
    parser.set_defaults({
        'config_module': 'sysadm_ldap_conf',
    })
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)
    logger.info('Start %s', parser.prog)
    logger.debug('args: %s', repr(args))

    ldif_conf = importlib.import_module(args.config_module)
    org_ldif_cls = make_class(ldif_conf.CLASS_ORGLDIF)
    config = OrgLdifConfig.get_default(module=ldif_conf)

    db = Factory.get('Database')()
    ldif = org_ldif_cls(db, config=config)
    timer = make_timer(logger, 'Starting dump')

    # Start generating LDIF
    output_file = config.org.start_outfile(
        filename=args.filename,
        max_change=args.max_change,
    )
    ldif.generate_org_object(output_file)

    ldif.init_ou_dump()
    # No OU-data (for now):
    # ldif.generate_ou(output_file)

    ldif.generate_person(
        outfile=output_file,
        alias_outfile=output_file,
        use_mail_module=True,
    )
    timer("Dump done")

    output_file.close()
    logger.info('OrgLDIF written to %s', args.filename)
    logger.info('Done %s', parser.prog)


if __name__ == '__main__':
    main()
