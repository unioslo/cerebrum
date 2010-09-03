#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2010 University of Oslo, Norway
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

from Cerebrum.Utils import Factory
from Cerebrum import Errors

db = Factory.get('Database')()
co = Factory.get('Constants')(db)
pe = Factory.get('Person')(db)
ac = Factory.get('Account')(db)
ac2 = Factory.get('Account')(db)
logger = Factory.get_logger("console")


def get_person_accounts(id_type, ext_id):
    """
    Find Person given by id_type and external id and return a list of
    dicts with username, status and priority. 

    Don't catch NotFoundError if person isn't found. Exception should
    be handled by caller.

    @param id_type: type of external id
    @type  id_type: string 
    @param ext_id: external id
    @type  ext_id: string
    @return: list of dicts with username, status and priority, sorted
    by priority
    @rtype: list of dicts
    """

    pe.clear()
    pe.find_by_external_id(getattr(co, id_type), ext_id)

    ret = list()
    for row in ac.get_account_types(all_persons_types=True,
                                    owner_id=pe.entity_id,
                                    filter_expired=False):
        ac2.clear()
        try:
            ac2.find(row['account_id'])
        except Errors.NotFoundError:
            logger.error("Couldn't find account with id %s" % row['account_id'])
            continue
        
        if ac2.is_expired() or ac2.is_deleted():
            status = "Expired"
        else:
            status = "Active"
        ret.append({'uname': ac2.account_name,
                    'priority': row['priority'],
                    'status': status})
    # Sort by priority
    ret.sort(key=lambda x: x['priority'])
    return ret


# TBD: If person doesn't exists or phone_no is wrong we should perhaps
# throw an exception?
def generate_token(id_type, ext_id, username, phone_no, browser_token):
    # Check if person exists
    try:
        pe.clear()
        pe.find_by_external_id(getattr(co, id_type), ext_id)
    except Errors.NotFoundError:
        logger.error("Couldn't find person with id %s:%s" % (id_type, ext_id))
        return False

    try:
        ac.clear()
        ac.find_by_name(username)
    except Errors.NotFoundError:
        logger.error("Couldn't find account %s" % username)
        return False

    if not ac.owner_id == pe.entity_id:
        logger.error("Account %s doesn't belong to person %d" % (username,
                                                                 pe.entity_id))
        return False
        
    # Check phone_no?
    # TODO: check if phone constants are correct.
    tmp = []
    for row in pe.get_contact_info(contact_type=(co.contact_phone,
                                                 co.contact_mobile_phone,
                                                 co.contact_phone_private)):
        tmp.append(row['contact_value'])
    if not phone_no not in tmp:
        logger.error("Given phone no is not registered in Cerebrum")
        return False
        
    # Generate token
    # TODO: jokim, this is your job. :)
    token = create_token()
    if not send_token(phone_no, token):
        logger.error("Couldn't send token to %s" % phone_no)
        return False
        
    # store token as a trait
    # TBD: What about browser_token?
    ac.populate_trait(co.trait_individuation_token, strval=token)
    return True


def create_token():
    pass


def send_token(phone_no, token):
    pass
