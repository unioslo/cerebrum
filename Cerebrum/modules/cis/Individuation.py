#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2010, 2011 University of Oslo, Norway
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


# TBD: Være forsiktig med å gi detaljert tilbakemelding i exceptions?
#      Hvis noen kobler seg på og prøver å hente ut data vil de kunne
#      lære hva som er riktig id_type, id, etc.

# TODO:
#   * Gjenbruk kode som sjekker og finner person og bruker

"""
Interface to Cerebrum for the Individuation service.
"""

import random
import string
from mx.DateTime import RelativeDateTime, now
import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory, SMSSender
from Cerebrum.modules import PasswordChecker


class SimpleLogger(object):
    """
    Very simple logger that just writes to stdout. Main reason for a
    class is to have the same api as Cerebrum logger.
    """
    def __init__(self):
        pass

    # Logging functions use print since twisted logger logs everything
    # written to stdout
    def error(self, msg):
        print "ERROR: " + msg
        
    def warning(self, msg):
        print "WARNING: " + msg    

    def info(self, msg):
        print "INFO: " + msg    
            
    def debug(self, msg):
        print "DEBUG: " + msg    

    
## Globals

db = Factory.get('Database')()
db.cl_init(change_program='individuation_service')
co = Factory.get('Constants')(db)
log = SimpleLogger()



def get_person_accounts(id_type, ext_id):
    """
    Find Person given by id_type and external id and return a list of
    dicts with username, status and priority. 

    The status should say if the user is:
      - Inactive: reserved, deleted, expired or with quarantines other than
        autopassord
      - PasswordQuarantined: if only with quarantine autopassord 
      - Active: active account

    @param id_type: type of external id
    @type  id_type: string 
    @param ext_id: external id
    @type  ext_id: string
    @return: list of dicts with username, status and priority, sorted
    by priority
    @rtype: list of dicts
    """

    # Check if person exists
    ac = Factory.get('Account')(db)
    pe = get_person(id_type, ext_id)
    accounts = dict((a['account_id'], 9999999) for a in
                     ac.list_accounts_by_owner_id(owner_id=pe.entity_id,
                                                  filter_expired=False))
    for row in ac.get_account_types(all_persons_types=True,
                                    owner_id=pe.entity_id,
                                    filter_expired=False):
        if accounts[row['account_id']] > int(row['priority']):
            accounts[row['account_id']] = int(row['priority'])
    ret = list()
    for (ac_id, pri) in accounts.iteritems():
        ac.clear()
        try:
            ac.find(ac_id)
        except Errors.NotFoundError:
            log.error("Couldn't find account with id %s" % ac_id)
            continue
        if ac.is_expired() or ac.is_deleted():
            status = "Inactive"
        else:
            quartypes = [q['quarantine_type'] for q in
                         ac.get_entity_quarantine(only_active=True)]
            if len(quartypes) == 0:
                status = "Active"
            elif (len(quartypes) == 1 and int(co.quarantine_autopassord) in
                    quartypes):
                status = "PasswordQuarantined"
            else:
                status = "Inactive"
        ret.append({'uname': ac.account_name,
                    'priority': pri,
                    'status': status})
    # Sort by priority
    ret.sort(key=lambda x: x['priority'])
    return ret

def generate_token(id_type, ext_id, uname, phone_no, browser_token):
    """
    Generate a token that functions as a short time password.
    
    @param id_type: type of external id
    @type  id_type: string 
    @param ext_id: external id
    @type  ext_id: string
    @param uname: username 
    @type  uname: string
    @param phone_no: phone number
    @type  phone_no: string
    @param browser_token: browser id
    @type  browser_token: string
    @return: True if success, False otherwise
    @rtype: bool
    """

    # Check if person exists
    pe = get_person(id_type, ext_id)
    ac = get_account(uname)
    if not ac.owner_id == pe.entity_id:
        log.error("Account %s doesn't belong to person %d" % (uname,
                                                              pe.entity_id))
        return False
    
    # Check phone_no
    if not check_phone(phone_no, pe.entity_id):
        log.error("phone_no %s is not registered for person %s" % (phone_no,
                                                                   pe.entity_id))
        return False
    # Create and send token
    token = create_token()
    log.debug("Generated token: " + token)
    if not send_token(phone_no, token):
        log.error("Couldn't send token to %s" % phone_no)
        return False

    # store password token as a trait
    ac.populate_trait(co.trait_password_token, strval=token, date=now(),
                      numval=0)
    # store browser token as a trait
    ac.populate_trait(co.trait_browser_token, strval=browser_token)
    ac.write_db()
    db.commit()
    return True


def create_token():
    """
    Return random sample of alphanumeric characters
    """
    alphanum = string.digits + string.ascii_letters
    return ''.join(random.sample(alphanum, cereconf.INDIVIDUATION_TOKEN_LENGTH))


def send_token(phone_no, token):
    """
    Send token as a SMS message to phone_no
    """
    #sms = SMSSender(logger=log)
    #sms(phone_no, token)
    return True


def check_token(uname, token, browser_token):
    """
    Check if token and other data from user is correct.
    """
    # Check if person exists
    ac = get_account(uname)

    # Check browser_token. The given browser_token may be "" but if so
    # the stored browser_token must be "" as well for the test to pass.
    
    bt = ac.get_trait(co.trait_browser_token)
    if not bt or bt['strval'] != browser_token:
        log.error("Given browser_token %s not equal to stored %s" % (
            browser_token, bt['strval']))
        return False

    # Check password token. Keep track of how many times a token is
    # checked to protect against brute force attack.
    pt = ac.get_trait(co.trait_password_token)
    no_checks = int(pt['numval'])
    if no_checks > getattr(cereconf, 'INDIVIDUATION_NO_CHECKS', 100):
        log.warn("No of legal token checks is exceeded")
        return False
    if not pt or pt['strval'] != token:
        log.error("Given token %s not equal to stored %s" % (token, pt['strval']))
        ac.populate_trait(co.trait_password_token, strval=pt['strval'],
                          date=pt['date'], numval=no_checks+1)
        ac.write_db()
        db.commit()
        return False
    
    # Check if we're within time limit
    time_limit = now() - RelativeDateTime(minutes=cereconf.INDIVIDUATION_TOKEN_LIFETIME)
    if pt['date'] < time_limit:
        log.info("Password tokens timelimit for %s exceeded" % uname)
        return False
    # All is fine
    return True


def delete_token(uname):
    """
    Delete password token for a given user
    """
    try:
        ac = get_account(uname)
        ac.delete_trait(co.trait_password_token)
        ac.write_db()
        db.commit()
    except Errors.NotFoundError, m:
        log.error("Couldn't delete password token trait for %s. %s" % (uname, m))
        return False
    return True


def validate_password(password):
    pc = PasswordChecker.PasswordChecker(db)
    try:
        pc.goodenough(None, password, uname="foobar")
    except PasswordChecker.PasswordGoodEnoughException, m:
        raise Errors.CerebrumError, "Bad password: %s" % m
    else:
        return True


def set_password(uname, new_password, token, browser_token):
    if not check_token(uname, token, browser_token):
        return False
    # All data is good. Set password
    ac = get_account(uname)
    ac.set_password(new_password)
    try:
        ac.write_db()
        db.commit()
        log.info("Password for %s altered." % uname)
    except db.DatabaseError, m:
        raise Errors.CerebrumError, "Database error: %s" % m
    # Remove "weak password" quarantine
    for r in ac.get_entity_quarantine():
        for qua in (co.quarantine_autopassord, co.quarantine_svakt_passord):
            if int(r['quarantine_type']) == qua:
                ac.delete_entity_quarantine(qua)
                ac.write_db()
                db.commit()
    
    if ac.is_deleted():
        log.warn("user is deleted")
    elif ac.is_expired():
        log.warn("user is expired")
    elif ac.get_entity_quarantine(only_active=True):
        log.warn("user has an active quarantine")

    return True
    
    

def get_person(id_type, ext_id):
    pe = Factory.get('Person')(db)
    pe.clear()
    try:
        pe.find_by_external_id(getattr(co, id_type), ext_id)
    except AttributeError:
        log.error("Wrong id_type: %s" % id_type)
        raise Errors.CerebrumError("Wrong id_type or id")
    except Errors.NotFoundError:
        log.error("Couldn't find person with ext_id %s" % ext_id)
        raise Errors.CerebrumError("Wrong id_type or id")
    else:
        return pe


def get_account(uname):
    ac = Factory.get('Account')(db)
    ac.clear()
    try:
        ac.find_by_name(uname)
    except Errors.NotFoundError:
        log.error("Couldn't find account %s" % uname)
    else:
        return ac


def check_phone(phone_no, person_id):
    """
    Check if given phone_no belongs to person. 
    """
    pe = Factory.get('Person')(db)
    for row in pe.list_contact_info(entity_id=person_id,
                                    contact_type=(co.contact_phone,
                                                  co.contact_mobile_phone,
                                                  co.contact_phone_private)):
        # Crude test. We should probably do this more carefully
        if phone_no == row['contact_value']:
            return True
    return False

