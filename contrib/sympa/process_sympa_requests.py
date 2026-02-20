#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2008-2026 University of Oslo, Norway
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
Process email-related bofhd requests.

sympa requests
    This script processes *create* and *remove* bofhd requests,
    which creates and deletes email lists on sympa hosts.

email requests
    This script processes legacy email requests.

    These requests are no-ops, and no longer in use.  They are processed in
    this script, simply because they were *always* processed at the same time
    as the sympa-related requests.
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

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum import Errors
from Cerebrum import Utils
from Cerebrum.modules import Email
from Cerebrum.modules.bofhd_requests import process_requests
from Cerebrum.modules.sympa.commands import SympaCommands
from Cerebrum.utils import date as date_utils
from Cerebrum.utils import json

logger = logging.getLogger(__name__)


RequestProcessor = process_requests.SimpleRequestProcessor


def get_address_from_id(db, address_id):
    ea = Email.EmailAddress(db)
    ea.find(address_id)
    ed = Email.EmailDomain(db)
    ed.find(ea.email_addr_domain_id)
    return "%s@%s" % (ea.email_addr_local_part,
                      ed.rewrite_special_domains(ed.email_domain_name))


def _get_request_data(request):
    """ Unserialize request state data. """
    try:
        state = json.loads(request["state_data"])
    except ValueError:
        state = None

    # Remove this when there's no chance of pickled data
    if state is None:
        try:
            state = pickle.loads(request["state_data"])
            logger.warning("legacy pickle state for request id=%d",
                           request['request_id'])
        except Exception:
            pass

    if state is None:
        state = {}
        logger.warning("no state for request id=%d", request['request_id'])

    return state


def sympa_create(db, request, dryrun=True, **kwargs):
    """
    Create mailing list from a bofhd request.

    :param request:
        a dict-like object with request parameters
    """
    logger.info("creating sympa list (request id: %d)", request['request_id'])
    try:
        listname = get_address_from_id(db, request["entity_id"])
    except Errors.NotFoundError:
        # This means that the address for the email list was deleted after
        # the request was created.  This *basically* means someone created
        # an email list, and then immediately deleted it.
        logger.info("No address id=%d for sympa list",
                    request['entity_id'])
        return True

    state = _get_request_data(request)
    if not state:
        logger.error("Missing data for sympa create request id=%d: %s",
                     request['request_id'], repr(request["state_data"]))
        return True

    try:
        runhost = state["runhost"]
        admins = ",".join(state["admins"])
        profile = state["profile"]
        description = state["description"]
    except (KeyError, ValueError, TypeError):
        logger.error("Missing params for sympa create request id=%d: %s",
                     request['request_id'], repr(request["state_data"]))
        return True

    runner = SympaCommands(dryrun)
    return runner.newlist(runhost, listname, admins, profile, description)


def sympa_remove(db, request, dryrun=True, **kwargs):
    """
    Remove mailing list from a bofhd request.

    :param request:
        a dict-like object with request parameters
    """
    logger.info("removing sympa list (request id: %d)", request['request_id'])
    state = _get_request_data(request)
    if not state:
        logger.error("Missing data for sympa create request id=%d: %s",
                     request['request_id'], repr(request["state_data"]))
        return True

    try:
        runhost = state["run_host"]
        listname = state["listname"]
    except KeyError:
        logger.error("Missing params for sympa delete request id=%d: %s",
                     request['request_id'], repr(request["state_data"]))
        return True

    runner = SympaCommands(dryrun)
    return runner.rmlist(runhost, listname)


def _drop_request(op, request, dryrun=True, **kwargs):
    """ This is a workaround to deal with obsolete operations. """
    logger.info("dropping obsolete request type=%s: %s",
                op, repr(dict(request)))
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Process sympa bofhd requests",
    )

    # TODO: For proper debugging and testing, We may want separate --dryrun
    # override flags for the clhandler and the sympa commands
    commit_mutex = parser.add_mutually_exclusive_group()
    commit_mutex.add_argument(
        "--commit",
        action="store_true",
        dest="commit",
        help="Run remote scripts and commit changes",
    )
    commit_mutex.add_argument(
        "--dryrun",
        action="store_false",
        dest="commit",
        help="Don't run scripts or commit changes (default)",
    )
    commit_mutex.set_defaults(commit=False)
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args()
    Cerebrum.logutils.autoconf("daily", args)
    dryrun = not args.commit

    logger.info('start %s', parser.prog)
    logger.debug('args: %r', args)

    db = Utils.Factory.get('Database')()
    db.cl_init(change_program=parser.prog)
    const = Utils.Factory.get('Constants')(db)
    process_operation = RequestProcessor(db, dryrun=dryrun)

    operations = [
        {
            'op_type': const.bofh_sympa_create,
            'callback': sympa_create,
            'delay': date_utils.to_seconds(hours=2),
        },
        {
            'op_type': const.bofh_sympa_remove,
            'callback': sympa_remove,
            'delay': date_utils.to_seconds(hours=2),
        },
        {
            'op_type': const.bofh_email_create,
            'callback': _drop_request,
        },
        {
            'op_type': const.bofh_email_delete,
            'callback': _drop_request,
        },
    ]

    logger.debug("processing requests...")
    for kwargs in operations:
        process_operation(**kwargs)

    logger.info('done %s', parser.prog)


if __name__ == '__main__':
    main()
