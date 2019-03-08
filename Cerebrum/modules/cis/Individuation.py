# -*- coding: utf-8 -*-
#
# Copyright 2010-2018 University of Oslo, Norway
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
Basic Cerebrum functionality for the Individuation service.
"""
from __future__ import unicode_literals

import hashlib
import logging
import random
import string

from mx.DateTime import RelativeDateTime, now
from six import text_type

import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.utils import json
from Cerebrum.utils.email import sendmail
from Cerebrum.utils.sms import SMSSender
from Cerebrum.modules.pwcheck.checker import (check_password,
                                              PasswordNotGoodEnough,
                                              PhrasePasswordNotGoodEnough)
from Cerebrum.QuarantineHandler import QuarantineHandler
from cisconf import individuation as cisconf


class SimpleLogger(object):
    """Very simple logger that just writes to stdout. Main reason for this
    class is to have the same API as the Cerebrum logger.

    It uses print for now, since twisted's logger logs everything written to
    stdout. It is, however, not the most efficient solution, as printing is
    slow. Services that makes use of this module should therefore override:

        Individuation.log = twisted.log

    """
    def error(self, msg, *args):
        print "ERROR: " + msg % args

    def warning(self, msg, *args):
        print "WARNING: " + msg % args

    def info(self, msg, *args):
        print "INFO: " + msg % args

    def debug(self, msg, *args):
        print "DEBUG: " + msg % args


logger = logging.getLogger(__name__)


class Individuation:
    """The general functionality for the Individuation project that is talking
    with Cerebrum.

    Note that this main class should be independent of what server we use. It
    is important that each thread gets its own instance of this class, to
    avoid race conditions.

    Another thing to remember is that database connections should be closed.
    This is to avoid long hanging database connections if the garbage
    collector can't destroy the instances.

    TBD: Create a core class with methods that is relevant to both bofhd and
    CIS? For examples: _check_password, get_person, get_account.

    """

    # The subject of the warning e-mails
    email_subject = 'Failed password recovery attempt'

    # The signature of the warning e-mails
    email_signature = 'University of Oslo'

    # The from address
    email_from = 'noreply@uio.no'

    # The generic feedback messages
    # TBD: put somewhere else?
    messages = {
        'error_unknown': {
            'en': 'An unknown error occured',
            'no': 'En ukjent feil oppstod'},
        'person_notfound': {
            'en': 'Could not find a person by given data, please try again.',
            'no': 'Kunne ikke finne personen ut fra oppgitte data, vennligst '
                  'prøv igjen.'},
        'person_notfound_usernames': {
            'en': 'You are either reserved or have given wrong information.'
                  ' If you are reserved, an SMS have been sent to you, as'
                  ' long as your cell phone number is registered in our'
                  ' systems.',
            'no': 'Du er reservert eller har gitt feil info. Hvis du er'
                  ' reservert skal du nå ha mottatt en SMS, såfremt ditt'
                  ' mobilnummer er registrert i våre systemer.'},
        'person_miss_info': {
            'en': ('Not all your information is available. Please contact'
                   ' your HR department or student office.'),
            'no': ('Ikke all din informasjon er tilgjengelig. Vennligst ta'
                   ' kontakt med din personalavdeling eller studentkontor.')},
        'account_blocked': {
            'en': 'This account is inactive. Please contact your local IT.',
            'no': ('Denne brukerkontoen er ikke aktiv. Vennligst ta kontakt'
                   ' med din lokale IT-avdeling.')},
        'account_reserved': {
            'en': ('You are reserved from using this service. Please contact'
                   ' your local IT.'),
            'no': ('Du er reservert fra å bruke denne tjenesten. Vennligst ta'
                   'kontakt med din lokale IT-avdeling.')},
        'account_self_reserved': {
            'en': ('You have reserved yourself from using this service. Please'
                   ' contact your local IT.'),
            'no': ('Du har reservert deg fra å bruke denne tjenesten.'
                   ' Vennligst ta kontakt med din lokale IT-avdeling.')},
        'token_notsent': {
            'en': 'Could not send one time password to phone',
            'no': 'Kunne ikke sende engangspassord til telefonen'},
        'toomanyattempts': {
            'en': ('Too many attempts. You have temporarily been blocked from'
                   ' this service'),
            'no': ('For mange forsøk. Du er midlertidig utestengt fra denne'
                   ' tjenesten')},
        'toomanyattempts_check': {
            'en': 'Too many attempts, one time password got invalid',
            'no': 'For mange forsøk, engangspassordet er blitt gjort ugyldig'},
        'timeout_check': {
            'en': 'Timeout, one time password got invalid',
            'no': 'Tidsavbrudd, engangspassord ble gjort ugyldig'},
        'fresh_phonenumber': {
            'en': ('Your phone number has recently been changed in StudWeb,'
                   ' which can not, due to security reasons, be used in a few'
                   ' days. Please contact your local IT-department.'),
            'no': ('Ditt mobilnummer er nylig byttet i StudentWeb, og kan av'
                   ' sikkerhetsmessige årsaker ikke benyttes før etter noen'
                   ' dager. Vennligst ta kontakt med din lokale IT-avdeling.')
        },
        'password_invalid': {
            'en': 'Bad password: %s',
            'no': 'Ugyldig passord: %s'},
        }

    def __init__(self):
        self.db = Factory.get('Database')()
        self.db.cl_init(change_program='individuation_service')
        self.co = Factory.get('Constants')(self.db)
        self.clconst = Factory.get('CLConstants')(self.db)

        # Do some tests, just to make sure that the service is set up properly.
        # This is so that the service crashes at once, and not after the first
        # client has connected and called a few commands.
        int(self.co.trait_public_reservation)
        int(self.co.trait_reservation_sms_password)
        int(self.co.trait_student_new)
        int(self.co.trait_sms_welcome)
        # TODO: more should be tested

    def close(self):
        """Explicitly close this instance of the class. This is to make sure
        that all is closed down correctly, even if the garbace collector can't
        destroy the instance."""
        if hasattr(self, 'db'):
            try:
                self.db.close()
            except Exception as e:
                logger.warning("Problems with db.close: %s", e)
        else:
            # TODO: this could be removed later, when it is considered stable
            logger.warning("db doesn't exist")

    def get_person_accounts(self, id_type, ext_id):
        """Find Person given by id_type and external id and return a list of
        dicts with username, status and priority. Note that if the person is
        reserved from publication, it will get an SMS with its usernames
        instead.

        @param id_type: type of external id
        @type  id_type: string
        @param ext_id: external id
        @type  ext_id: string
        @return: list of dicts with username, status and priority, sorted
        by priority
        @rtype: list of dicts

        """
        # Check if person exists
        try:
            person = self.get_person(id_type, ext_id)
        except Errors.CerebrumRPCException:
            raise Errors.CerebrumRPCException('person_notfound_usernames')

        # Check reservation
        if self.is_reserved_publication(person):
            logger.info("Person id=%s is reserved from publication",
                        person.entity_id)
            # if person has a phone number, we could send the usernames by SMS:
            phone_nos = self.get_phone_numbers(person,
                                               only_first_affiliation=False)
            if phone_nos:
                accounts = [a['uname'] for a in self.get_account_list(person)]
                logger.debug('Sending SMS with usernames: %s',
                             ', '.join(accounts))
                self.send_sms(phone_nos[0]['number'],
                              cisconf.SMS_MSG_USERNAMES % '\n'.join(accounts))
            else:
                logger.debug('No phone number for person %s', person.entity_id)
            raise Errors.CerebrumRPCException('person_notfound_usernames')
        return self.get_account_list(person)

    def get_account_list(self, person):
        """Return a list of a person's accounts and a short status. The
        accounts are sorted by priority.

        @type  person: Cerebrum.Person instance
        @param person: A Person instance, set with the person to get the
                       accounts from.
        """
        account = Factory.get('Account')(self.db)
        accounts = dict((a['account_id'], 9999999) for a in
                        account.list_accounts_by_owner_id(
                            owner_id=person.entity_id,
                            filter_expired=False))
        for row in account.get_account_types(all_persons_types=True,
                                             owner_id=person.entity_id,
                                             filter_expired=False):
            if accounts[row['account_id']] > int(row['priority']):
                accounts[row['account_id']] = int(row['priority'])
        ret = list()
        for (ac_id, pri) in accounts.items():
            account.clear()
            try:
                account.find(ac_id)
            except Errors.NotFoundError:
                logger.error("Couldn't find account with id=%r", ac_id)
                continue
            status = 'status_inactive'
            if not (account.is_expired() or account.is_deleted()):
                status = 'status_active'
                accepted_quars = [int(getattr(self.co, q)) for q in
                                  cereconf.INDIVIDUATION_ACCEPTED_QUARANTINES]
                if any(q['quarantine_type'] not in accepted_quars
                       for q in account.get_entity_quarantine(
                           only_active=True)):
                    status = 'status_inactive'
            ret.append({'uname': account.account_name,
                        'priority': pri,
                        'status': status})
        # Sort by priority
        ret.sort(key=lambda x: x['priority'])
        return ret

    def generate_token(self, id_type, ext_id, uname, phone_no,
                       browser_token=''):
        """
        Generate a token that functions as a short time password for the user
        and send it by SMS.

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
        # Check if account exists
        account = self.get_account(uname)
        # Check if account has been checked too many times
        self.check_too_many_attempts(account)
        # Check if person exists
        person = self.get_person(id_type, ext_id)
        if not account.owner_id == person.entity_id:
            logger.info("Account %r doesn't belong to person_id=%r",
                        uname, person.entity_id)
            raise Errors.CerebrumRPCException('person_notfound')
        # Check if account is blocked
        if not self.check_account(account):
            logger.info("Account %r is blocked", account.account_name)
            raise Errors.CerebrumRPCException('account_blocked')
        # Check if person/account is reserved
        if self.is_reserved(account=account, person=person):
            logger.info("Account %r (or person) is reserved",
                        account.account_name)
            raise Errors.CerebrumRPCException('account_reserved')
        # Check if person/account is self reserved
        if self.is_self_reserved(account=account, person=person):
            logger.info("Account %r (or person) is self reserved",
                        account.account_name)
            raise Errors.CerebrumRPCException('account_self_reserved')
        # Check phone_no
        phone_nos = self.get_phone_numbers(person)
        if not phone_nos:
            logger.info("No relevant affiliation or phone registered for %s",
                        account.account_name)
            raise Errors.CerebrumRPCException('person_miss_info')
        if not self.check_phone(phone_no, numbers=phone_nos, person=person,
                                account=account):
            logger.info("phone_no %s not found for %s",
                        phone_no, account.account_name)
            raise Errors.CerebrumRPCException('person_notfound')
        # Create and send token
        token = self.create_token()
        # TODO: remove when done testing
        logger.debug("Generated token %s for %s", token, uname)
        try:
            if not self.send_token(phone_no, token):
                raise ValueError("negative send_token return value")
        except:
            logger.error("Couldn't send token to %r for %r",
                         phone_no, uname, exc_info=True)
            raise Errors.CerebrumRPCException('token_notsent')
        account._db.log_change(account.entity_id,
                               self.clconst.account_password_token,
                               None,
                               change_params={'phone_to': phone_no})
        # store password token as a trait
        account.populate_trait(self.co.trait_password_token, date=now(),
                               numval=0, strval=self.hash_token(token, uname))
        # store browser token as a trait
        if type(browser_token) is not text_type:
            logger.error("Invalid browser_token, type=%r, value=%r",
                         type(browser_token), browser_token)
            browser_token = ''
        account.populate_trait(self.co.trait_browser_token, date=now(),
                               strval=self.hash_token(browser_token, uname))
        account.write_db()
        account._db.commit()
        return True

    def create_token(self):
        """Return random sample of alphanumeric characters"""
        alphanum = text_type(string.digits + string.ascii_letters)
        return ''.join(random.sample(alphanum,
                                     cereconf.INDIVIDUATION_TOKEN_LENGTH))

    def send_sms(self, phone_no, msg):
        """Send an SMS with the given msg to the given phone number."""
        sms = SMSSender()
        return sms(phone_no, msg)

    def send_token(self, phone_no, token):
        """Send token as a SMS message to phone_no"""
        msg = getattr(cereconf, 'INDIVIDUATION_SMS_MESSAGE',
                                'Your one time password: %s')
        return self.send_sms(phone_no, msg % token)

    def hash_token(self, token, uname):
        """Generates a hash of a given token, to avoid storing tokens in
        plaintext."""
        return text_type(hashlib.sha1((uname + token).encode('UTF-8'))
                         .hexdigest())

    def check_token(self, uname, token, browser_token):
        """Check if token and other data from user is correct."""
        try:
            account = self.get_account(uname)
        except Errors.CerebrumRPCException:
            # shouldn't tell what went wrong
            return False

        # Check browser_token. The given browser_token may be "" but if so
        # the stored browser_token must be "" as well for the test to pass.

        bt = account.get_trait(self.co.trait_browser_token)
        if not bt or bt['strval'] != self.hash_token(browser_token, uname):
            logger.info("Incorrect browser_token=%r for user %r",
                        browser_token, uname)
            return False

        # Check password token. Keep track of how many times a token is
        # checked to protect against brute force attack (defaults to 20).
        pt = account.get_trait(self.co.trait_password_token)
        no_checks = int(pt['numval'])
        if no_checks > getattr(cereconf, 'INDIVIDUATION_TOKEN_ATTEMPTS', 20):
            logger.info("No. of token checks exceeded for user %r", uname)
            raise Errors.CerebrumRPCException('toomanyattempts_check')
        # Check if we're within time limit
        time_limit = now() - RelativeDateTime(
            minutes=cereconf.INDIVIDUATION_TOKEN_LIFETIME)
        if pt['date'] < time_limit:
            logger.debug("Password token's timelimit for user %r exceeded",
                         uname)
            raise Errors.CerebrumRPCException('timeout_check')

        if pt and pt['strval'] == self.hash_token(token, uname):
            # All is fine
            return True
        logger.debug("Token %s incorrect for user %s", token, uname)
        account.populate_trait(self.co.trait_password_token,
                               strval=pt['strval'], date=pt['date'],
                               numval=no_checks+1)
        account.write_db()
        account._db.commit()
        return False

    def delete_token(self, uname):
        """Delete password token for a given user.
        """
        try:
            account = self.get_account(uname)
            account.delete_trait(self.co.trait_password_token)
            account.write_db()
            account._db.commit()
        except Errors.CerebrumRPCException:
            pass
        except Errors.NotFoundError as m:
            logger.error("Couldn't delete password token trait for %r. %s",
                         uname, m)
        return True

    def validate_password(self, password, account_name, structured):
        """
        Validate any password

        :param password: the password to be validated
        :type password: string
        :param account_name: the account name to be used or ''
        :type account_name: string
        :param structured: whether to ask for a strctured (json) output
        :type structured: bool
        """
        account = None
        if account_name:
            try:
                account = Factory.get('Account')(self.db)
                account.find_by_name(account_name)
            except Errors.NotFoundError:
                raise Errors.CerebrumRPCException('unknown_error')
        try:
            result = check_password(password, account, structured)
            # exceptions are obsolete and used only for backward
            # compatibility here (f.i. old brukerinfo clients)
        except PhrasePasswordNotGoodEnough as e:
            # assume that structured is False
            m = text_type(e)
            # separate exception for phrases on the client??
            # no point of having separate except block otherwise
            raise Errors.CerebrumRPCException('password_invalid', m)
        except PasswordNotGoodEnough as e:
            # assume that structured is False
            m = text_type(e)
            raise Errors.CerebrumRPCException('password_invalid', m)
        else:
            if structured:
                # success or error data sent to the caller
                return json.dumps(result, indent=4)
            else:
                # no PasswordNotGoodEnough exception thrown
                return 'OK'

    def set_password(self, uname, new_password, token, browser_token):
        if not self.check_token(uname, token, browser_token):
            return False
        account = self.get_account(uname)
        try:
            check_password(new_password, account)
        except PasswordNotGoodEnough as e:
            m = text_type(e)
            raise Errors.CerebrumRPCException('password_invalid', m)
        # All data is good. Set password
        account.set_password(new_password)
        try:
            account.write_db()
            account._db.commit()
            logger.info("Password for %r altered", uname)
        except self.db.DatabaseError as m:
            logger.error("Error when setting password for %r: %s", uname, m)
            raise Errors.CerebrumRPCException('error_unknown')
        # Remove "weak password" quarantine
        for r in account.get_entity_quarantine():
            for qua in (self.co.quarantine_autopassord,
                        self.co.quarantine_svakt_passord):
                if int(r['quarantine_type']) == qua:
                    account.delete_entity_quarantine(qua)
                    account.write_db()
                    account._db.commit()
        # TODO: move these checks up and raise exceptions? Wouldn't happen,
        # since generate_token() checks this already, but might get other
        # authentication methods later.
        if account.is_deleted():
            logger.warning("user %r is deleted", uname)
        elif account.is_expired():
            logger.warning("user %r is expired", uname)
        elif QuarantineHandler.check_entity_quarantines(
                self.db, account.entity_id).is_locked():
            logger.info("user %r has an active quarantine", uname)
        return True

    def get_person(self, id_type, ext_id):
        person = Factory.get('Person')(self.db)
        person.clear()
        if not hasattr(self.co, id_type):
            logger.error("Wrong id_type=%r", id_type)
            raise Errors.CerebrumRPCException('person_notfound')
        try:
            person.find_by_external_id(getattr(self.co, id_type), ext_id)
            return person
        except Errors.NotFoundError:
            logger.debug("Couldn't find person with %s=%r", id_type, ext_id)

        # Try without leading zeros, as FS use that, and which could confuse
        # students. TODO: Note that this does not help if the external IDs are
        # stored _with_ leading zeros in the database, i.e. the opposite way.
        if ext_id.isdigit():
            try:
                person.find_by_external_id(getattr(self.co, id_type),
                                           text_type(int(ext_id)))
                logger.debug("Found person %r without leading zeros in "
                             "ext_id=%r", person.entity_id, ext_id)
                return person
            except Errors.NotFoundError:
                pass

            # Still not found? Try to padd with zeros if it's a student number
            # with less than 6 digits:
            if (hasattr(self.co, 'externalid_studentnr') and
                    getattr(self.co, id_type) == self.co.externalid_studentnr
                    and len(ext_id) < 6):
                try:
                    person.find_by_external_id(getattr(self.co, id_type),
                                               '%06d' % int(ext_id))
                    logger.debug("Found person %r with padded zeros in "
                                 "ext_id: %r", person.entity_id, ext_id)
                    return person
                except Errors.NotFoundError:
                    pass
        raise Errors.CerebrumRPCException('person_notfound')

    def get_account(self, uname):
        account = Factory.get('Account')(self.db)
        try:
            account.find_by_name(uname)
        except Errors.NotFoundError:
            logger.info("Couldn't find account %r", uname)
            raise Errors.CerebrumRPCException('person_notfound')
        else:
            return account

    def _get_priorities(self):
        """
        Return a double list with the source systems in the prioritized order
        as defined in the config.
        """
        if not hasattr(self, '_priorities_cache'):
            priorities = {}
            for sys, values in cereconf.INDIVIDUATION_PHONE_TYPES.iteritems():
                if 'priority' not in values:
                    logger.error('config missing priority for system %r', sys)
                    values['priority'] = 999999
                pri = priorities.setdefault(values['priority'], {})
                pri[sys] = values
            self._priorities_cache = [priorities[x]
                                      for x in sorted(priorities)]
            logger.debug("Priorities: %r", self._priorities_cache)
        return self._priorities_cache

    def get_phone_numbers(self, person, only_first_affiliation=True):
        """
        Return a list of the registered phone numbers for a given person. Only
        the defined source systems and contact types are searched for, and the
        person must have an active affiliation from a system before a number
        could be retrieved from that same system.

        Note that only the person affiliation with the highest priority is
        checked for phone numbers, as long as L{only_first_affiliation} is
        True. This is to separate the user types and avoid e.g. a student's
        phone getting changed and thus be able to get hold of the employee
        account for the same person.
        """
        old_limit = now() - RelativeDateTime(
            days=cereconf.INDIVIDUATION_AFF_GRACE_PERIOD)
        pe_systems = [int(af['source_system']) for af in
                      person.list_affiliations(person_id=person.entity_id,
                                               include_deleted=True)
                      if (af['deleted_date'] is None
                          or af['deleted_date'] > old_limit)]
        logger.debug("Person has affiliations in the systems: %r", pe_systems)
        phones = []
        for systems in self._get_priorities():
            sys_codes = [getattr(self.co, s) for s in systems]
            if not any(s in sys_codes for s in pe_systems):
                # person has no affiliation at this priority go to next priorit
                continue
            for system, values in systems.iteritems():
                types = [getattr(self.co, t) for t in values['types']]
                sys = getattr(self.co, system)
                if not types:
                    # support empty lists, to be able to block e.g. employees
                    # from the service
                    continue
                for row in person.list_contact_info(entity_id=person.entity_id,
                                                    contact_type=types,
                                                    source_system=sys):
                    phones.append({
                        'number': row['contact_value'],
                        'system': sys,
                        'system_name': system,
                        'type': self.co.ContactInfo(row['contact_type'])})
            logger.debug("Phones for person_id=%r from (%s): %s",
                         person.entity_id,
                         ','.join(s for s in systems),
                         ','.join('%s:%s:%s' % (p['system_name'], p['type'],
                                                p['number'])
                                  for p in phones))
            if only_first_affiliation:
                return phones
        return phones

    def check_phone(self, phone_no, numbers, person, account):
        """Check if given phone_no belongs to person. The phone number is only
        searched for in source systems that the person has active affiliations
        from and contact types as defined in INDIVIDUATION_PHONE_TYPES. Other
        numbers are ignored. Set delays are also checked, to avoid that changed
        phone numbers are used for some period.

        """
        is_fresh = self.entity_is_fresh(person, account)
        for num in numbers:
            if not self.number_match(stored=num['number'], given=phone_no):
                continue
            if is_fresh:
                # delay is ignored for fresh entities
                return True
            delay = self.get_delay(num['system_name'], num['type'])

            for row in self.db.get_log_events(types=self.clconst.entity_cinfo_add,
                                              any_entity=person.entity_id,
                                              sdate=delay):
                data = json.loads(row['change_params'])
                if num['number'] == data['value']:
                    logger.info('person_id=%r recently changed phoneno',
                                person.entity_id)
                    self.mail_warning(
                        person=person, account=account,
                        reason=("Your phone number has recently been"
                                " changed. Due to security reasons, it"
                                " can not be used by the password service"
                                " for a few days."))
                    raise Errors.CerebrumRPCException('fresh_phonenumber')
            return True
        return False

    def entity_is_fresh(self, person, account):
        """Check if a person or account is 'fresh', i.e. if the account or
        person is newly created, or if the account has been restored lately.

        This is to be able to avoid blocking new phone numbers from systems
        where the account is just activated.

        """
        delay = now() - getattr(cisconf, 'FRESH_DAYS', 10)

        # Check for traits only set for 'fresh' accounts:
        for tr in (self.co.trait_student_new, self.co.trait_sms_welcome):
            trait = account.get_trait(tr)
            if trait and trait['date'] > delay:
                logger.debug('Fresh trait %r for account %r, '
                             'so considered fresh', tr, account.account_name)
                return True
        # Check if person has recently been created:
        for row in self.db.get_log_events(types=(self.clconst.person_create),
                                          any_entity=person.entity_id,
                                          sdate=delay):
            logger.debug("Person %r is fresh", person.entity_id)
            return True
        logger.debug("Person %r (account %r) is not fresh",
                     person.entity_id, account.entity_id)
        return False

    def number_match(self, stored, given):
        """Checks if a given number matches a stored number. You could for
        instance check with and without country codes and spaces, to support
        different varieties of phone numbers. Note that you can not change the
        numbers here, so you can not tolerate invalid numbers, that has to be
        fixed in the source system.

        """
        return (self._filter_numbermatch(given) ==
                self._filter_numbermatch(stored))

    def _filter_numbermatch(self, number):
        """Filter a number to be checked for matching."""
        number = number.strip()
        # The Norwegian country code could be removed, so that users could
        # specify it or not, and still let the numbers match.
        if number.startswith('+47'):
            number = number[3:]
        return number

    def get_delay(self, system, type):
        """Return a DateTime set to the correct delay time for numbers of the
        given type and from the given source system. Numbers must be older than
        this DateTime to be accepted.

        If no delay is set for the number, it returns now(), which will be true
        unless you change your number in the exact same time.

        """
        delay = 0
        try:
            types = cereconf.INDIVIDUATION_PHONE_TYPES[system]['types']
        except KeyError:
            logger.error('get_delay: Unknown system defined: %r', system)
            delay = 0
        else:
            for t in types:
                if int(getattr(self.co, t, 0)) == int(type):
                    delay = int(types[t].get('delay', 0))
                    break
        return now() - RelativeDateTime(days=delay)

    def mail_warning(self, person, account, reason):
        """Warn a person by sending an e-mail to all its accounts."""
        msg = '\n'.join([
            "Someone has tried to recover the password for your account: %s."
            % account.account_name,
            "This has failed, due to the following reason:", '',
            " %s" % reason, '',
            "If this was not you, please contact your local IT-department as "
            "soon as possible.", '',
            "-- ", "%s" % self.email_signature])
        account2 = Factory.get('Account')(self.db)
        for row in person.get_accounts():
            account2.clear()
            account2.find(row['account_id'])
            try:
                primary = account2.get_primary_mailaddress()
            except Errors.NotFoundError as e:
                logger.error("Couldn't warn user %r, no primary mail: %s",
                             account.account_name, e)
                continue
            logger.debug("Emailing user %r (%r)",
                         account2.account_name, account2.entity_id)
            try:
                sendmail(primary, self.email_from, self.email_subject, msg)
            except Exception as e:
                logger.error("Error for %r from sendmail: %s", primary, e)

    def check_too_many_attempts(self, account):
        """
        Checks if a user has tried to use the service too many times. Creates
        the trait if it doesn't exist, and increments the numval. Raises an
        exception when too many attempts occur in the block period.

        """
        attempts = 0
        trait = account.get_trait(self.co.trait_password_failed_attempts)
        block_period = now() - RelativeDateTime(
            seconds=cereconf.INDIVIDUATION_ATTEMPTS_BLOCK_PERIOD)
        if trait and trait['date'] > block_period:
            attempts = int(trait['numval'])
        logger.debug('User %r has tried %r times',
                     account.account_name, attempts)
        if attempts > cereconf.INDIVIDUATION_ATTEMPTS:
            logger.info("User %r too many attempts, temporarily blocked",
                        account.account_name)
            raise Errors.CerebrumRPCException('toomanyattempts')
        account.populate_trait(
            code=self.co.trait_password_failed_attempts,
            target_id=account.entity_id, date=now(), numval=attempts + 1)
        account.write_db()
        account._db.commit()

    def check_account(self, account):
        """ Check if the account is not blocked from changing password. """

        if account.is_deleted() or account.is_expired():
            return False
        # Check quarantines
        quars = [int(getattr(self.co, q)) for q in
                 getattr(cereconf, 'INDIVIDUATION_ACCEPTED_QUARANTINES', ())]
        for q in account.get_entity_quarantine(only_active=True):
            if q['quarantine_type'] not in quars:
                return False
        # TODO: more to check?
        return True

    def is_reserved(self, account, person):
        """
        Check that the person/account isn't reserved from using the service.
        """
        group = Factory.get('Group')(account._db)
        # Check if superuser or in any reserved group
        for gname in (getattr(cereconf, 'INDIVIDUATION_PASW_RESERVED', ()) +
                      (cereconf.BOFHD_SUPERUSER_GROUP,)):
            group.clear()
            try:
                group.find_by_name(gname)
            except Errors.NotFoundError:
                logger.warning("Group %r deleted, but tagged for reservation",
                               gname)
                continue
            if account.entity_id in (int(row["member_id"]) for row in
                                     group.search_members(
                                         group_id=group.entity_id,
                                         indirect_members=True,
                                         member_type=self.co.entity_account)):
                return True
            # TODO: these two loops should be merged!
            if person.entity_id in (int(row["member_id"]) for row in
                                    group.search_members(
                                         group_id=group.entity_id,
                                         indirect_members=True,
                                         member_type=self.co.entity_account)):
                return True
        return False

    def is_self_reserved(self, account, person):
        """Check if the user has reserved himself from using the service."""

        # Check if person is reserved
        tr = person.get_trait(self.co.trait_reservation_sms_password)
        if tr and tr['numval'] != 0:
            return True
        # Check if account is reserved
        tr = account.get_trait(self.co.trait_reservation_sms_password)
        if tr and tr['numval'] != 0:
            return True
        return False

    def is_reserved_publication(self, person):
        """Check if a person is reserved from being published on the instance's
        web pages. Most institutions doesn't have this regime.

        """
        if not hasattr(self.co, 'trait_public_reservation'):
            return False
        trait = person.get_trait(self.co.trait_public_reservation)
        if trait and trait['numval'] != 0:
            return True
        return False
