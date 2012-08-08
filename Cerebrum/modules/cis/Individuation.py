#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 
# Copyright 2010-2012 University of Oslo, Norway
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
"""Basic Cerebrum functionality for the Individuation service.

"""

import random, hashlib
import string, pickle
from mx.DateTime import RelativeDateTime, now

import cereconf
import cerebrum_path
from Cerebrum import Errors
from Cerebrum.Utils import Factory, SMSSender, sendmail
from Cerebrum.modules import PasswordChecker
from cisconf import individuation as cisconf

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
log = SimpleLogger()

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
        'error_unknown':     
            {'en': u'An unknown error occured',
             'no': u'En ukjent feil oppstod'},
        'person_notfound':
            {'en': u'Could not find a person by given data, please try again.',
             'no': u'Kunne ikke finne personen ut fra oppgitte data, vennligst'
                   u' prøv igjen.',},
        'person_notfound_usernames':   
            {'en': u'You are either reserved or have given wrong information.'
                   u' If you are reserved, an SMS have been sent to you, as'
                   u' long as your cell phone number is registered in our'
                   u' systems.',
             'no': u'Du er reservert eller har gitt feil info. Hvis du er'
                   u' reservert skal du nå ha mottatt en SMS, såfremt ditt'
                   u' mobilnummer er registrert i våre systemer.'},
        'person_miss_info':  
            {'en': u'Not all your information is available. Please contact'
                   u' your HR department or student office.',
             'no': u'Ikke all din informasjon er tilgjengelig. Vennligst ta'
                   u' kontakt med din personalavdeling eller studentkontor.'},
        'account_blocked':
            {'en': u'This account is inactive. Please contact your local IT.',
             'no': u'Denne brukerkontoen er ikke aktiv. Vennligst ta kontakt'
                   u' med din lokale IT-avdeling.'},
        'account_reserved':
            {'en': u'You are reserved from using this service. Please contact'
                   u' your local IT.',
             'no': u'Du er reservert fra å bruke denne tjenesten. Vennligst ta'
                   u'kontakt med din lokale IT-avdeling.'},
        'account_self_reserved':
            {'en': u'You have reserved yourself from using this service. Please'
                   u' contact your local IT.',
             'no': u'Du har reservert deg fra å bruke denne tjenesten.'
                   u' Vennligst ta kontakt med din lokale IT-avdeling.'},
        'token_notsent':
            {'en': u'Could not send one time password to phone',
             'no': u'Kunne ikke sende engangspassord til telefonen'},
        'toomanyattempts':
            {'en': u'Too many attempts. You have temporarily been blocked from'
                   u' this service',
             'no': u'For mange forsøk. Du er midlertidig utestengt fra denne'
                   u' tjenesten'},
        'toomanyattempts_check':
            {'en': u'Too many attempts, one time password got invalid',
             'no': u'For mange forsøk, engangspassordet er blitt gjort'
                   u' ugyldig'},
        'timeout_check':
            {'en': u'Timeout, one time password got invalid',
             'no': u'Tidsavbrudd, engangspassord ble gjort ugyldig'},
        'fresh_phonenumber':
            {'en': u'Your phone number has recently been changed in StudWeb,'
                   u' which can not, due to security reasons, be used in a few'
                   u' days. Please contact your local IT-department.',
             'no': u'Ditt mobilnummer er nylig byttet i StudentWeb, og kan av'
                   u' sikkerhetsmessige årsaker ikke benyttes før etter noen'
                   u' dager. Vennligst ta kontakt med din lokale IT-avdeling.'},
        'password_invalid':
            {'en': u'Bad password: %s',
             'no': u'Ugyldig passord: %s'},
        }

    def __init__(self):
        self.db = Factory.get('Database')()
        self.db.cl_init(change_program='individuation_service')
        self.co = Factory.get('Constants')(self.db)

        # Do some tests, just to make sure that the service is set up properly.
        # This is so that the service crashes at once, and not after the first
        # client has connected and called a few commands.
        int(self.co.trait_public_reservation)
        int(self.co.trait_reservation_sms_password)
        # TODO: more should be tested

    def close(self):
        """Explicitly close this instance of the class. This is to make sure
        that all is closed down correctly, even if the garbace collector can't
        destroy the instance."""
        if hasattr(self, 'db'):
            try:
                self.db.close()
            except Exception, e:
                log.warning("Problems with db.close: %s" % e)
        else:
            # TODO: this could be removed later, when it is considered stable
            log.warning("db doesn't exist")

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
            log.info("Person id=%s is reserved from publication" % person.entity_id)
            # if person has a phone number, we could send the usernames by SMS:
            phone_nos = self.get_phone_numbers(person,
                                               only_first_affiliation=False)
            if phone_nos:
                accounts = [a['uname'] for a in self.get_account_list(person)]
                log.debug('Sending SMS with usernames: %s' % ', '.join(accounts))
                self.send_sms(phone_nos[0]['number'],
                              cisconf.SMS_MSG_USERNAMES % '\n'.join(accounts))
            else:
                log.debug('No phone number for person %s' % person.entity_id)
            raise Errors.CerebrumRPCException('person_notfound_usernames')
        return self.get_account_list(person)

    def get_account_list(self, person):
        """Return a list of a person's accounts and a short status. The accounts
        are sorted by priority.

        @type  person: Cerebrum.Person instance 
        @param person: A Person instance, set with the person to get the
                       accounts from.
        """
        account = Factory.get('Account')(self.db)
        accounts = dict((a['account_id'], 9999999) for a in
                        account.list_accounts_by_owner_id(owner_id=person.entity_id,
                                                          filter_expired=False))
        for row in account.get_account_types(all_persons_types=True,
                                             owner_id=person.entity_id,
                                             filter_expired=False):
            if accounts[row['account_id']] > int(row['priority']):
                accounts[row['account_id']] = int(row['priority'])
        ret = list()
        for (ac_id, pri) in accounts.iteritems():
            account.clear()
            try:
                account.find(ac_id)
            except Errors.NotFoundError:
                log.error("Couldn't find account with id %s" % ac_id)
                continue
            status = 'status_inactive'
            if not (account.is_expired() or account.is_deleted()):
                status = 'status_active'
                accepted_quars = [int(getattr(self.co, q)) for q in
                                  cereconf.INDIVIDUATION_ACCEPTED_QUARANTINES]
                if any(q['quarantine_type'] not in accepted_quars
                       for q in account.get_entity_quarantine(only_active=True)):
                    status = 'status_inactive'
            ret.append({'uname': account.account_name,
                        'priority': pri,
                        'status': status})
        # Sort by priority
        ret.sort(key=lambda x: x['priority'])
        return ret

    def generate_token(self, id_type, ext_id, uname, phone_no, browser_token=''):
        """Generate a token that functions as a short time password for the user
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
            log.info("Account %s doesn't belong to person %d" % (uname,
                                                                  person.entity_id))
            raise Errors.CerebrumRPCException('person_notfound')
        # Check if account is blocked
        if not self.check_account(account):
            log.info("Account %s is blocked" % (account.account_name))
            raise Errors.CerebrumRPCException('account_blocked')
        # Check if person/account is reserved
        if self.is_reserved(account=account, person=person):
            log.info("Account %s (or person) is reserved" % (account.account_name))
            raise Errors.CerebrumRPCException('account_reserved')
        # Check if person/account is self reserved
        if self.is_self_reserved(account=account, person=person):
            log.info("Account %s (or person) is self reserved" % (account.account_name))
            raise Errors.CerebrumRPCException('account_self_reserved')
        # Check phone_no
        phone_nos = self.get_phone_numbers(person)
        if not phone_nos:
            log.info("No relevant affiliation or phone registered for %s" % account.account_name)
            raise Errors.CerebrumRPCException('person_miss_info')
        if not self.check_phone(phone_no, numbers=phone_nos, person=person,
                                account=account):
            log.info("phone_no %s not found for %s" % (phone_no, account.account_name))
            raise Errors.CerebrumRPCException('person_notfound')
        # Create and send token
        token = self.create_token()
        log.debug("Generated token %s for %s" % (token, uname)) # TODO: remove when done testing
        if not self.send_token(phone_no, token):
            log.error("Couldn't send token to %s for %s" % (phone_no, uname))
            raise Errors.CerebrumRPCException('token_notsent')
        account._db.log_change(subject_entity=account.entity_id,
                      change_type_id=self.co.account_password_token,
                      destination_entity=None,
                      change_params={'phone_to': phone_no})
        # store password token as a trait
        account.populate_trait(self.co.trait_password_token, date=now(), numval=0,
                          strval=self.hash_token(token, uname))
        # store browser token as a trait
        if type(browser_token) is not str:
            log.err("Invalid browser_token, type='%s', value='%s'" % (type(browser_token), 
                                                                      browser_token))
            browser_token = ''
        account.populate_trait(self.co.trait_browser_token, date=now(),
                          strval=self.hash_token(browser_token, uname))
        account.write_db()
        account._db.commit()
        return True

    def create_token(self):
        """Return random sample of alphanumeric characters"""
        alphanum = string.digits + string.ascii_letters
        return ''.join(random.sample(alphanum, cereconf.INDIVIDUATION_TOKEN_LENGTH))

    def send_sms(self, phone_no, msg):
        """Send an SMS with the given msg to the given phone number."""
        sms = SMSSender(logger=log)
        return sms(phone_no, msg)

    def send_token(self, phone_no, token):
        """Send token as a SMS message to phone_no"""
        msg = getattr(cereconf, 'INDIVIDUATION_SMS_MESSAGE', 
                                'Your one time password: %s')
        return self.send_sms(phone_no, msg % token)

    def hash_token(self, token, uname):
        """Generates a hash of a given token, to avoid storing tokens in
        plaintext."""
        return hashlib.sha1(uname + token).hexdigest()

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
            log.info("Incorrect browser_token %s for user %s" % (browser_token, uname))
            return False

        # Check password token. Keep track of how many times a token is
        # checked to protect against brute force attack (defaults to 20).
        pt = account.get_trait(self.co.trait_password_token)
        no_checks = int(pt['numval'])
        if no_checks > getattr(cereconf, 'INDIVIDUATION_TOKEN_ATTEMPTS', 20):
            log.info("No. of token checks exceeded for user %s" % uname)
            raise Errors.CerebrumRPCException('toomanyattempts_check')
        # Check if we're within time limit
        time_limit = now() - RelativeDateTime(minutes=cereconf.INDIVIDUATION_TOKEN_LIFETIME)
        if pt['date'] < time_limit:
            log.debug("Password token's timelimit for user %s exceeded" % uname)
            raise Errors.CerebrumRPCException('timeout_check')

        if pt and pt['strval'] == self.hash_token(token, uname):
            # All is fine
            return True
        log.debug("Token %s incorrect for user %s" % (token, uname))
        account.populate_trait(self.co.trait_password_token, strval=pt['strval'],
                          date=pt['date'], numval=no_checks+1)
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
        except Errors.NotFoundError, m:
            log.error("Couldn't delete password token trait for %s. %s" % (uname, m))
        return True

    def validate_password(self, password):
        return self._check_password(password)

    def _check_password(self, password, account=None):
        pc = PasswordChecker.PasswordChecker(self.db)
        try:
            pc.goodenough(account, password, uname="foobar")
        except PasswordChecker.PasswordGoodEnoughException, m:
            # The PasswordChecker is in iso8859-1, so we need to convert its
            # message to unicode before we raise it.
            m = unicode(str(m), 'iso8859-1')
            raise Errors.CerebrumRPCException('password_invalid', m)
        else:
            return True

    def set_password(self, uname, new_password, token, browser_token):
        if not self.check_token(uname, token, browser_token):
            return False
        account = self.get_account(uname)
        if not self._check_password(new_password, account):
            return False
        # All data is good. Set password
        account.set_password(new_password)
        try:
            account.write_db()
            account._db.commit()
            log.info("Password for %s altered." % uname)
        except self.db.DatabaseError, m:
            log.error("Error when setting password for %s: %s" % (uname, m))
            raise Errors.CerebrumRPCException('error_unknown')
        # Remove "weak password" quarantine
        for r in account.get_entity_quarantine():
            for qua in (self.co.quarantine_autopassord, self.co.quarantine_svakt_passord):
                if int(r['quarantine_type']) == qua:
                    account.delete_entity_quarantine(qua)
                    account.write_db()
                    account._db.commit()
        # TODO: move these checks up and raise exceptions? Wouldn't happen,
        # since generate_token() checks this already, but might get other
        # authentication methods later.
        if account.is_deleted():
            log.warning("user %s is deleted" % uname)
        elif account.is_expired():
            log.warning("user %s is expired" % uname)
        elif account.get_entity_quarantine(only_active=True):
            log.info("user %s has an active quarantine" % uname)
        return True

    def get_person(self, id_type, ext_id):
        person = Factory.get('Person')(self.db)
        person.clear()
        try:
            person.find_by_external_id(getattr(self.co, id_type), ext_id)
        except AttributeError, e:
            log.error("Wrong id_type: '%s'" % id_type)
            raise Errors.CerebrumRPCException('person_notfound')
        except Errors.NotFoundError:
            log.debug("Couldn't find person with %s='%s'" % (id_type, ext_id))
            raise Errors.CerebrumRPCException('person_notfound')
        else:
            return person

    def get_account(self, uname):
        account = Factory.get('Account')(self.db)
        try:
            account.find_by_name(uname)
        except Errors.NotFoundError:
            log.info("Couldn't find account %s" % uname)
            raise Errors.CerebrumRPCException('person_notfound')
        else:
            return account

    def _get_priorities(self):
        """Return a double list with the source systems in the prioritized order
        as defined in the config."""
        if not hasattr(self, '_priorities_cache'):
            priorities = {}
            for sys, values in cereconf.INDIVIDUATION_PHONE_TYPES.iteritems():
                if not values.has_key('priority'):
                    log.error('config missing priority for system %s' % sys)
                    values['priority'] = 999999
                pri = priorities.setdefault(values['priority'], {})
                pri[sys] = values
            self._priorities_cache = [priorities[x] for x in sorted(priorities)]
            log.debug("Priorities: %s" % self._priorities_cache)
        return self._priorities_cache

    def get_phone_numbers(self, person, only_first_affiliation=True):
        """Return a list of the registered phone numbers for a given person.
        Only the defined source systems and contact types are searched for, and
        the person must have an active affiliation from a system before a number
        could be retrieved from that same system.

        Note that only the person affiliation with the highest priority is
        checked for phone numbers, as long as L{only_first_affiliation} is True.
        This is to separate the user types and avoid e.g. a student's phone
        getting changed and thus be able to get hold of the employee account for
        the same person.

        """
        old_limit = now() - RelativeDateTime(days=cereconf.INDIVIDUATION_AFF_GRACE_PERIOD)
        pe_systems = [int(af['source_system']) for af in
                      person.list_affiliations(person_id=person.entity_id, include_deleted=True)
                      if (af['deleted_date'] is None or af['deleted_date'] > old_limit)]
        log.debug("Person has affiliations in the systems: %s" % pe_systems)
        phones = []
        for systems in self._get_priorities():
            sys_codes = [getattr(self.co, s) for s in systems]
            if not any(s in sys_codes for s in pe_systems):
                # person has no affiliation at this priority go to next priority
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
                    phones.append({'number': row['contact_value'],
                                   'system': sys,
                                   'system_name': system,
                                   'type':   self.co.ContactInfo(row['contact_type']),})
            log.debug("Phones for person_id:%s from (%s): %s" % (person.entity_id,
                      ','.join(s for s in systems), 
                      ','.join('%s:%s:%s' % (p['system_name'], p['type'], p['number']) for p in phones)))
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

            for row in self.db.get_log_events(types=self.co.entity_cinfo_add,
                                              any_entity=person.entity_id,
                                              sdate=delay):
                data = pickle.loads(row['change_params'])
                if num['number'] == data['value']:
                    log.info('person_id=%s recently changed phoneno' % person.entity_id)
                    self.mail_warning(person=person, account=account,
                            reason=("Your phone number has recently been"
                                + " changed. Due to security reasons, it"
                                + " can not be used by the password service"
                                + " for a few days."))
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
                log.debug('Fresh trait %s for account %s, so considered fresh' %
                          (tr, account.account_name))
                return True
        # Check if person has recently been created:
        for row in self.db.get_log_events(types=(self.co.person_create),
                                          any_entity=person.entity_id,
                                          sdate=delay):
            log.debug("Person %s is fresh" % person.entity_id)
            return True
        log.debug("Person %s (account %s) is not fresh" % (person.entity_id,
                                                           account.entity_id))
        return False

    def number_match(self, stored, given):
        """Checks if a given number matches a stored number. Checks, e.g.
        removing spaces, could be put here, if necessary, but note that the best
        place to fix such mismatches is in the source system.
        """
        if given.strip() == stored.strip():
            return True
        # TODO: more checks here?
        return False

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
            log.error('get_delay: Unknown system defined: %s' % system)
            delay = 0
        else:
            for t in types:
                if int(getattr(self.co, t, 0)) == int(type):
                    delay = int(types[t].get('delay', 0))
                    break
        return now() - RelativeDateTime(days=delay)

    def mail_warning(self, person, account, reason):
        """Warn a person by sending an e-mail to all its accounts."""
        msg  = "Someone has tried to recover the password for your account: %s.\n" % account.account_name
        msg += "This has failed, due to the following reason:\n\n  %s\n\n" % reason
        msg += "If this was not you, please contact your local IT-department as soon as possible."
        msg += "\n\n-- \n%s\n" % self.email_signature
        account2 = Factory.get('Account')(self.db)
        for row in person.get_accounts():
            account2.clear()
            account2.find(row['account_id'])
            try:
                primary = account2.get_primary_mailaddress()
            except Errors.NotFoundError, e:
                log.error("Couldn't warn user %s, no primary mail: %s" %
                          (account.account_name, e))
                continue
            log.debug("Emailing user %s (%d)" % (account2.account_name, account2.entity_id))
            try:
                sendmail(primary, self.email_from, self.email_subject, msg)
            except Exception, e:
                log.error("Error for %s from Utils.sendmail: %s" % (primary, e))

    def check_too_many_attempts(self, account):
        """Checks if a user has tried to use the service too many times. Creates
        the trait if it doesn't exist, and increments the numval. Raises an
        exception when too many attempts occur in the block period.

        """
        attempts = 0
        trait = account.get_trait(self.co.trait_password_failed_attempts)
        block_period = now() - RelativeDateTime(seconds=cereconf.INDIVIDUATION_ATTEMPTS_BLOCK_PERIOD)
        if trait and trait['date'] > block_period:
            attempts = int(trait['numval'])
        log.debug('User %s has tried %d times' % (account.account_name,
                                                  attempts))
        if attempts > cereconf.INDIVIDUATION_ATTEMPTS:
            log.info("User %s too many attempts, temporarily blocked" %
                     account.account_name)
            raise Errors.CerebrumRPCException('toomanyattempts')
        account.populate_trait(code=self.co.trait_password_failed_attempts,
                target_id=account.entity_id, date=now(), numval=attempts + 1)
        account.write_db()
        account._db.commit()

    def check_account(self, account):
        """Check if the account is not blocked from changing password.
        """
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
        """Check that the person/account isn't reserved from using the service."""
        group = Factory.get('Group')(account._db)
        # Check if superuser or in any reserved group
        for gname in (getattr(cereconf, 'INDIVIDUATION_PASW_RESERVED', ()) +
                      (cereconf.BOFHD_SUPERUSER_GROUP,)):
            group.clear()
            try:
                group.find_by_name(gname)
            except Errors.NotFoundError:
                log.warning("Group %s deleted, but tagged for reservation" % gname)
                continue
            if account.entity_id in (int(row["member_id"]) for row in
                                     group.search_members(group_id=group.entity_id,
                                                          indirect_members=True,
                                                          member_type=self.co.entity_account)):
                return True
            # TODO: these two loops should be merged!
            if person.entity_id in (int(row["member_id"]) for row in
                                     group.search_members(group_id=group.entity_id,
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
