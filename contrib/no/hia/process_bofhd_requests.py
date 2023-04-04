#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2003-2023 University of Oslo, Norway
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
Process bofhd requests for UiA.

This script reads from the bofhd_request table in the database and picks the
requests of the given types for processing.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import argparse
import logging
import pickle

import six

import cereconf

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum import Errors
from Cerebrum.Utils import Factory, spawn_and_log_output
from Cerebrum.modules import Email
from Cerebrum.modules.bofhd_requests import process_requests
from Cerebrum.utils import json


logger = logging.getLogger(__name__)

EXIT_SUCCESS = 0

operations_map = process_requests.OperationsMap()

constants_cls = Factory.get("Constants")
sympa_create_op = six.text_type(constants_cls.bofh_sympa_create)
sympa_remove_op = six.text_type(constants_cls.bofh_sympa_remove)


@operations_map(sympa_create_op, delay=2*60)
def proc_sympa_create(db, request):
    """Execute the request for creating a sympa mailing list.

    @type request: ??
    @param request:
      An object describing the sympa list creation request.
    """

    try:
        listname = get_address(db, request["entity_id"])
    except Errors.NotFoundError:
        logger.info("Sympa list address %s is deleted! No need to create",
                    listname)
        return True

    try:
        state = json.loads(request["state_data"])
    except ValueError:
        state = None

    # Remove this when there's no chance of pickled data
    if state is None:
        try:
            state = pickle.loads(request["state_data"])
        except Exception:
            pass

    if state is None:
        logger.error("Cannot parse request state for sympa list=%s: %s",
                     listname, request["state_data"])
        return True

    try:
        host = state["runhost"]
        profile = state["profile"]
        description = state["description"]
        admins = state["admins"]
        admins = ",".join(admins)
    except KeyError:
        logger.error("No host/profile/description specified for sympa list %s",
                     listname)
        return True

    # 2008-08-01 IVR FIXME: Safe quote everything fished out from state.
    cmd = [cereconf.SYMPA_SCRIPT, host, 'newlist',
           listname, admins, profile, description]
    return spawn_and_log_output(cmd) == EXIT_SUCCESS


@operations_map(sympa_remove_op, delay=2*60)
def proc_sympa_remove(db, request):
    """Execute the request for removing a sympa mailing list.

    @type request: ??
    @param request:
      A dict-like object containing all the parameters for sympa list
      removal.
    """

    try:
        state = json.loads(request["state_data"])
    except ValueError:
        state = None

    # Remove this when there's no chance of pickled data
    if state is None:
        try:
            state = pickle.loads(request["state_data"])
        except Exception:
            pass

    if state is None:
        logger.error("Cannot parse request state for sympa request %s: %s",
                     request["request_id"], request["state_data"])
        return True

    try:
        listname = state["listname"]
        host = state["run_host"]
    except KeyError:
        logger.error("No listname/runhost specified for request %s",
                     request["request_id"])
        return True

    cmd = [cereconf.SYMPA_SCRIPT, host, 'rmlist', listname]
    return spawn_and_log_output(cmd) == EXIT_SUCCESS


def get_address(db, address_id):
    ea = Email.EmailAddress(db)
    ea.find(address_id)
    ed = Email.EmailDomain(db)
    ed.find(ea.email_addr_domain_id)
    return "%s@%s" % (ea.email_addr_local_part,
                      ed.rewrite_special_domains(ed.email_domain_name))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-t', '--type',
        dest='types',
        action='append',
        choices=['sympa'],
        required=True,
    )
    parser.add_argument(
        '-m', '--max',
        dest='max_requests',
        default=999999,
        help='Perform up to this number of requests',
        type=int,
    )
    parser.add_argument(
        '-p', '--process',
        dest='process',
        action='store_true',
        help='Perform the queued operations',
    )

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args()
    Cerebrum.logutils.autoconf('bofhd_req', args)

    logger.info('Start %s', parser.prog)
    logger.debug('args: %r', args)

    db = Factory.get('Database')()
    db.cl_init(change_program='process_bofhd_r')
    const = constants_cls(db)

    if args.process:
        rp = process_requests.RequestProcessor(db, const)
        rp.process_requests(operations_map, args.types, args.max_requests)

    logger.info('Done %s', parser.prog)


if __name__ == '__main__':
    main()
