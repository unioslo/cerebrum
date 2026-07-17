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
""" Create and fetch bofhd requests for sympa. """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import datetime
import logging
import pickle

from Cerebrum.modules.bofhd_requests.request import BofhdRequests
from Cerebrum.utils import date as date_utils
from Cerebrum.utils import json

logger = logging.getLogger(__name__)


# IVR 2009-04-17 +30 minute delay to allow changes to spread to
# LDAP. The postmasters are nagging for that delay. All questions
# should be directed to them (this is similar to delaying a delete
# request).
DELAY_NEWLIST = datetime.timedelta(minutes=30)

# IVR 2008-08-04 +1 hour to allow changes to spread to
# LDAP. This way we'll have a nice SMTP-error, rather
# than a confusing error burp from sympa.
DELAY_RMLIST = datetime.timedelta(hours=1)


def request_newlist(operator_id, address, runhost, admins, profile,
                    description):
    """
    Add request to create a sympa list.

    :param int operator_id: the operator that requests the list
    :param address: the EmailAddress that the list should use
    :param str runhost: the host that serves this list
    :param list admins: A list of admin email addresses
    :param str profile: A profile to use
    :param str description: A list description
    """
    db = address._db
    const = address.const
    br = BofhdRequests(db, const)
    address_id = int(address.entity_id)
    operator_id = int(operator_id)
    state = {
        "runhost": runhost,
        "admins": admins,
        "profile": profile,
        "description": description,
    }

    br.add_request(
        operator=operator_id,
        when=date_utils.now() + DELAY_NEWLIST,
        op_code=const.bofh_sympa_create,
        entity_id=address_id,
        destination_id=address_id,
        state_data=json.dumps(state),
    )


def request_rmlist(operator_id, address, runhost, listname):
    """
    Add request to remove a sympa list.

    :param int operator_id: the operator that requests the removal
    :param address: the EmailAddress that the list uses
    :param str runhost: the host that serves this list
    :param str listname: name of the email list
    """
    db = address._db
    const = address.const
    br = BofhdRequests(db, const)
    address_id = int(address.entity_id)
    operator_id = int(operator_id)
    state = {
        'run_host': runhost,
        'listname': listname,
    }

    br.add_request(
        operator=operator_id,
        when=date_utils.now() + DELAY_RMLIST,
        op_code=const.bofh_sympa_remove,
        entity_id=address_id,
        destination_id=None,
        state_data=json.dumps(state),
    )


def _deserialize_state(request):
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


def get_params_newlist(request):
    """
    Extract parameters for creating a sympa list.

    Note that the listname is not included in the request, and must be fetched
    separately from the request entity (address_id).
    """
    state = _deserialize_state(request)
    if not state:
        logger.warning("no params for sympa create request id=%d: %s",
                       request['request_id'], repr(request["state_data"]))
        return {}

    retval = {}
    for k in ("runhost", "admins", "profile", "description"):
        if not state.get(k):
            logger.warning("no %s param for sympa create request id=%d: %s",
                           k, request['request_id'],
                           repr(request["state_data"]))
            return {}
        retval[k] = state[k]
    # admins is serialized as a list, but we need a single comma-separated
    # string
    retval['admins'] = ",".join(retval['admins'])
    return retval


def get_params_rmlist(request):
    """ Extract parameters for removing a sympa list. """
    state = _deserialize_state(request)
    if not state:
        logger.warning("no params for sympa remove request id=%d: %s",
                       request['request_id'], repr(request["state_data"]))
        return {}

    retval = {}
    for old_key, new_key in [("run_host", "runhost"),
                             ("listname", "listname")]:
        if not state.get(old_key):
            logger.warning("no %s param for sympa remove request id=%d: %s",
                           old_key, request['request_id'],
                           repr(request["state_data"]))
            return {}
        retval[new_key] = state[old_key]
    return retval
