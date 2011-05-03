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

import random, hashlib
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

    # Check reservation
    if is_reserved_publication(pe):
        log.info("Person id=%s is reserved from publication" % pe.entity_id)
        # Returns same error message as for non existing persons, to avoid
        # leaking information that a person actually exists in our systems.
        raise Errors.CerebrumRPCException('person_notfound')
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
            status = 'status_inactive'
        else:
            quartypes = [q['quarantine_type'] for q in
                         ac.get_entity_quarantine(only_active=True)]
            if len(quartypes) == 0:
                status = 'status_active'
            elif (len(quartypes) == 1 and int(co.quarantine_autopassord) in
                    quartypes):
                status = 'status_passw_quar'
            else:
                status = 'status_inactive'
        ret.append({'uname': ac.account_name,
                    'priority': pri,
                    'status': status})
    # Sort by priority
    ret.sort(key=lambda x: x['priority'])
    return ret

def generate_token(id_type, ext_id, uname, phone_no, browser_token):
    """
    Generate a token that functions as a short time password for the
    user and send it by SMS.
    
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
        log.debug("Account %s doesn't belong to person %d" % (uname,
                                                              pe.entity_id))
        raise Errors.CerebrumRPCException('person_notfound')
    # Check if account is blocked
    if not check_account(ac):
        log.info("Account %s is blocked" % (ac.account_name))
        raise Errors.CerebrumRPCException('account_blocked')
    # Check if person/account is reserved
    if is_reserved(account=ac, person=pe):
        log.info("Account %s (or person) is reserved" % (ac.account_name))
        raise Errors.CerebrumRPCException('account_reserved')
    # Check phone_no
    if not check_phone(phone_no, pe):
        log.debug("phone_no %s not found for %s" % (phone_no, ac.account_name))
        raise Errors.CerebrumRPCException('person_notfound')
    # Create and send token
    token = create_token()
    log.debug("Generated token %s for %s" % (token, uname))
    if not send_token(phone_no, token):
        log.error("Couldn't send token to %s for %s" % (phone_no, uname))
        raise Errors.CerebrumRPCException('token_notsent')

    # store password token as a trait
    ac.populate_trait(co.trait_password_token, date=now(), numval=0,
                      strval=hash_token(token, uname))
    # store browser token as a trait
    ac.populate_trait(co.trait_browser_token, date=now(),
                      strval=hash_token(browser_token, uname))
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
    sms = SMSSender(logger=log)
    msg = getattr(cereconf, 'INDIVIDUATION_SMS_MESSAGE', 
                            'Your one time password: %s')
    return sms(phone_no, msg % token)

def hash_token(token, uname):
    """
    Generates a hash of a given token, to avoid storing tokens in plaintext.
    """
    return hashlib.md5(uname + token).hexdigest()

def check_token(uname, token, browser_token):
    """
    Check if token and other data from user is correct.
    """
    try:
        ac = get_account(uname)
    except Errors.CerebrumRPCException:
        # shouldn't tell what went wrong
        return False

    # Check browser_token. The given browser_token may be "" but if so
    # the stored browser_token must be "" as well for the test to pass.
    
    bt = ac.get_trait(co.trait_browser_token)
    if not bt or bt['strval'] != hash_token(browser_token, uname):
        log.info("Incorrect browser_token %s for user %s" % (browser_token, uname))
        return False

    # Check password token. Keep track of how many times a token is
    # checked to protect against brute force attack (defaults to 20).
    pt = ac.get_trait(co.trait_password_token)
    no_checks = int(pt['numval'])
    if no_checks > getattr(cereconf, 'INDIVIDUATION_NO_CHECKS', 20):
        log.info("No. of token checks exceeded for user %s" % uname)
        raise Errors.CerebrumRPCException('toomanyattempts_check')
    # Check if we're within time limit
    time_limit = now() - RelativeDateTime(minutes=cereconf.INDIVIDUATION_TOKEN_LIFETIME)
    if pt['date'] < time_limit:
        log.debug("Password token's timelimit for user %s exceeded" % uname)
        raise Errors.CerebrumRPCException('timeout_check')

    if pt and pt['strval'] == hash_token(token, uname):
        # All is fine
        return True
    log.debug("Token %s incorrect for user %s" % (token, uname))
    ac.populate_trait(co.trait_password_token, strval=pt['strval'],
                      date=pt['date'], numval=no_checks+1)
    ac.write_db()
    db.commit()
    return False

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
    return _check_password(password)

def _check_password(password, account=None):
    pc = PasswordChecker.PasswordChecker(db)
    try:
        pc.goodenough(account, password, uname="foobar")
    except PasswordChecker.PasswordGoodEnoughException, m:
        raise Errors.CerebrumRPCException('password_invalid', m)
    else:
        return True

def set_password(uname, new_password, token, browser_token):
    if not check_token(uname, token, browser_token):
        return False
    ac = get_account(uname)
    if not _check_password(new_password, ac):
        return False
    # All data is good. Set password
    ac.set_password(new_password)
    try:
        ac.write_db()
        db.commit()
        log.info("Password for %s altered." % uname)
    except db.DatabaseError, m:
        log.error("Error when setting password for %s: %s" % (uname, m))
        raise Errors.CerebrumRPCException('error_unknown')
    # Remove "weak password" quarantine
    for r in ac.get_entity_quarantine():
        for qua in (co.quarantine_autopassord, co.quarantine_svakt_passord):
            if int(r['quarantine_type']) == qua:
                ac.delete_entity_quarantine(qua)
                ac.write_db()
                db.commit()
    if ac.is_deleted():
        log.warning("user %s is deleted" % uname)
    elif ac.is_expired():
        log.warning("user %s is expired" % uname)
    elif ac.get_entity_quarantine(only_active=True):
        log.info("user %s has an active quarantine" % uname)
    return True

def get_person(id_type, ext_id):
    pe = Factory.get('Person')(db)
    pe.clear()
    try:
        pe.find_by_external_id(getattr(co, id_type), ext_id)
    except AttributeError, e:
        log.error("Wrong id_type: '%s'" % id_type)
        raise e # unknown error
    except Errors.NotFoundError:
        log.debug("Couldn't find person with %s='%s'" % (id_type, ext_id))
        raise Errors.CerebrumRPCException('person_notfound')
    else:
        return pe

def get_account(uname):
    ac = Factory.get('Account')(db)
    try:
        ac.find_by_name(uname)
    except Errors.NotFoundError:
        log.info("Couldn't find account %s" % uname)
        raise Errors.CerebrumRPCException('person_notfound')
    else:
        return ac

def check_phone(phone_no, person):
    """
    Check if given phone_no belongs to person. The phone number is only searched
    for in source systems that the person has active affiliations from and
    contact types as defined in INDIVIDUATION_PHONE_TYPES. Other numbers are
    ignored.
    """
    pe_systems = [int(af['source_system']) for af in
                  person.list_affiliations(person_id=person.entity_id)]
    for sys, types in cereconf.INDIVIDUATION_PHONE_TYPES.iteritems():
        system = getattr(co, sys)
        if int(system) not in pe_systems:
            continue
        phone_types = [getattr(co, t) for t in types]
        for row in person.list_contact_info(entity_id=person.entity_id,
                                            contact_type=phone_types,
                                            source_system=system):
            # Crude test. We should probably do this more carefully
            if phone_no == row['contact_value']:
                return True
    return False

def check_account(account):
    """
    Check if the account is not blocked from changing password.
    """
    if account.is_deleted() or account.is_expired():
        return False
    # Check quarantines
    quars = [int(getattr(co, q)) for q in
             getattr(cereconf, 'INDIVIDUATION_ACCEPTED_QUARANTINES', ())]
    for q in account.get_entity_quarantine(only_active=True):
        if q['quarantine_type'] not in quars:
            return False
    # TODO: more to check?
    return True
    
def is_reserved(account, person):
    """
    Check that the person/account isn't reserved from using the service.
    """
    # Check if superuser or in any reserved group
    group = Factory.get('Group')(db)
    for gname in (getattr(cereconf, 'INDIVIDUATION_PASW_RESERVED', ()) +
                  (cereconf.BOFHD_SUPERUSER_GROUP,)):
        group.clear()
        group.find_by_name(gname) # TODO: if groups doesn't exist it should fail!
        if account.entity_id in (int(row["member_id"]) for row in
                                 group.search_members(group_id=group.entity_id,
                                                      indirect_members=True,
                                                      member_type=co.entity_account)):
            return True
        # TODO: these two loops should be merged!
        if person.entity_id in (int(row["member_id"]) for row in
                                 group.search_members(group_id=group.entity_id,
                                                      indirect_members=True,
                                                      member_type=co.entity_account)):
            return True

    # Check if person is reserved
    for reservation in person.list_traits(code=co.trait_reservation_sms_password,
                                          target_id=person.entity_id):
        if reservation['numval'] > 0:
            return True
    # Check if account is reserved
    for reservation in account.list_traits(code=co.trait_reservation_sms_password,
                                           target_id=account.entity_id):
        if reservation['numval'] > 0:
            return True
    return False

def is_reserved_publication(person):
    """
    Check if a person is reserved from being published on the instance's web
    pages.
    """
    return False






