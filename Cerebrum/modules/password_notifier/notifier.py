#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2016-2018 University of Oslo, Norway
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

from __future__ import unicode_literals

"""Module for handling notifications of passwords that are running out of date.

Institutions could have security related policies in that passwords must be
changed after a given number of days.

The module makes use of traits for saving the state for targetet accounts. This
module:

1. Finds accounts that have passwords that is reaching its time limit. Expired
   and quarantined accounts are ignored, as well as accounts with an except
   trait.

2. Removes the password trait for accounts that have already changed their
   password.

3. Quarantines accounts for where the deadline has passed.

4. Sends accounts an e-mail and/or SMS, saying that they have to change their
   password, if the password trait has not already been set. The password trait
   gets set for logging this, with numval 1.

5. Sends accounts another e-mail when closer to the deadline, if the password
   trait has not already been set to 2. The trait's numval gets incremented.

A trait is used for excepting specific users from being processed.
"""

import io
import email
import email.Header
import locale
import os
import smtplib
import time
import warnings
from functools import partial

import mx.DateTime as dt

import cereconf

from Cerebrum import Errors
from Cerebrum import Utils
from Cerebrum.utils.email import sendmail
from Cerebrum.utils.sms import SMSSender
from Cerebrum.QuarantineHandler import QuarantineHandler
from Cerebrum.modules.password_notifier.config import load_config
from Cerebrum.modules.pwcheck.history import PasswordHistory


# Default date format (non-localized)
DATE_FORMAT = '%Y-%m-%d'


def _get_notifier_classes(values):
    """
    """
    def _import_cls(spec):
        mod, name = spec.split('/')
        mod = Utils.dyn_import(str(mod))
        cls = getattr(mod, str(name))
        return cls

    cls_list = []
    for idx, class_str in enumerate(values):
        cls_list.append(_import_cls(class_str))
        for prev in range(idx):
            if issubclass(cls_list[idx], cls_list[prev]):
                raise RuntimeError(
                    'class_notifier[{:d}] ({!r}) is a subclass of '
                    'class_notifier[{:d}] ({!r})'.format(idx,
                                                         cls_list[idx],
                                                         prev,
                                                         cls_list[prev]))
    return cls_list


class PasswordNotifier(object):
    """
    Sends password notifications to users with old passwords, and
    can query information about passwords notifications.
    """

    def __init__(self, db=None, logger=None, dryrun=False, *rest, **kw):
        """ Constructs a PasswordNotifier.

        :param Cerebrum.database.Database db:
            Database object to use. If `None`, this object will fetch a new db
            connection with `Factory.get('Database')`. This is the default.

        :param logging.Logger logger:
            Logger object to use. If `None`, this object will fetch a new
            logger with `Factory.get_logger('crontab')`. This is the default.

        :param bool dryrun:
            If this object should refrain from doing changes, and only print
            debug info. Default is `False`.
        """

        self.logger = logger or Utils.Factory.get_logger('console')
        self.db = db or Utils.Factory.get("Database")()
        self.dryrun = bool(dryrun)

        self.now = dt.Date(*(time.localtime()[:3]))
        self.today = dt.Date(*(time.localtime()[:3]))

        account = Utils.Factory.get("Account")(self.db)
        account.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
        self.splattee_id = account.entity_id
        self.constants = Utils.Factory.get('Constants')(db)
        self.splatted_users = []

    def get_old_account_ids(self):
        """ Returns the ID of candidate accounts with old affiliations.

        :return set:
            A set with Account entity_ids.
        """
        def _with_aff(affiliation=None, max_age=None):
            old = set()
            person = Utils.Factory.get("Person")(self.db)

            aff_or_status = self.constants.human2constant(affiliation)
            if not aff_or_status:
                self.logger.error('Unknown affiliation "%s"', affiliation)
                return old

            lookup = {'status' if '/' in affiliation
                      else 'affiliation': aff_or_status}
            for row in person.list_affiliations(**lookup):
                person_id = row['person_id']
                # if person_id in old_ids:
                #     continue
                person.clear()
                person.find(person_id)
                # account_id = person.get_primary_account()
                for account_row in person.get_accounts():
                    # consider all accounts belonging to this person
                    account_id = account_row['account_id']
                    if account_id:
                        history = [x['set_at'] for x in ph.get_history(
                            account_id)]
                        if history and (self.today - max(history) > max_age):
                            old.add(account_id)
                        else:
                            # The account does not have an expired password
                            # according to the special rules.
                            # Remove it from old_ids if it was put there
                            # by the default rules.
                            try:
                                old_ids.remove(account_id)
                            except KeyError:
                                pass
            self.logger.info(
                'Accounts with affiliation %s with old password: %s',
                str(affiliation), len(old))
            return old

        ph = PasswordHistory(self.db)

        self.logger.info('Fetching accounts with password older than %d days',
                         self.config.max_password_age)
        old_ids = set(
            [int(x['account_id']) for x in ph.find_old_password_accounts((
                self.today - dt.DateTimeDelta(
                    self.config.max_password_age)).strftime(DATE_FORMAT))])
        self.logger.info('Fetching accounts with no password history')
        old_ids.update(
            set([int(x['account_id']) for x in ph.find_no_history_accounts()]))
        # Do we have special rules for certain person affiliations?
        # We want to end with the smallest 'max_password_age'
        aff_mappings = sorted(self.config.affiliation_mappings,
                              key=lambda k: k['max_password_age'],
                              reverse=True)
        for aff_mapping in aff_mappings:
            self.logger.info(
                'Fetching accounts with affiliation %s '
                'with password older than %d days',
                str(aff_mapping['affiliation']),
                aff_mapping['max_password_age'])
            old_ids.update(_with_aff(
                affiliation=aff_mapping['affiliation'],
                max_age=dt.DateTimeDelta(aff_mapping['max_password_age'])))
        self.logger.info('Fetching quarantines')
        # TODO: Select only autopassword quarantines?
        quarantined_ids = QuarantineHandler.get_locked_entities(
            self.db,
            entity_types=self.constants.entity_account,
            entity_ids=old_ids)

        old_ids = old_ids - quarantined_ids
        return old_ids

    def get_notified_ids(self):
        """
        Returns a set of account_id's which have a password trait
        """
        account = Utils.Factory.get("Account")(self.db)
        return set([x['entity_id'] for x in account.list_traits(
            code=self.constants.EntityTrait(self.config.trait))])

    def remove_trait(self, account):
        """
        Removes pw trait, if any, and logs it.
        """
        try:
            account.delete_trait(self.constants.EntityTrait(self.config.trait))
            account.write_db()
            self.logger.info("Deleting passwd trait for %s",
                             account.account_name)
        except Errors.NotFoundError:
            # raised if account does not have trait
            pass

    def get_num_notifications(self, account):
        """
        Returns the number of previous notifications
        """
        try:
            traits = account.get_trait(
                self.constants.EntityTrait(self.config.trait))
            return int(traits['numval'])
        except (Errors.NotFoundError, TypeError):
            return 0

    def rec_fail_notification(self, account):
        """
        If a notification fails, set a 0 value, and record a failed attempt.
        If a trait already exists, log it, it should not be used that way.
        """
        traits = account.get_trait(
            self.constants.EntityTrait(self.config.trait))
        if traits is None:
            account.populate_trait(
                code=self.constants.EntityTrait(self.config.trait),
                target_id=None,
                date=self.now,
                numval=0,
                strval=self.today.strftime("Failed: " + DATE_FORMAT))
            account.write_db()
        else:
            if int(traits['numval']) != 0:
                self.logger.error("Notification has already succeeded "
                                  "(this should not happen)")

    def inc_num_notifications(self, account):
        """ Update trait to indicate that account has been notified.

        This increases the trait `intval` by one, and adds the date to the
        trait `strval`.
        """
        traits = account.get_trait(
            self.constants.EntityTrait(self.config.trait))
        if traits is not None:
            traits = dict(
                [(x, traits[x])
                 for x in ('code', 'target_id', 'date', 'numval', 'strval')])
            traits['numval'] = int(traits['numval']) + 1
            self.logger.info("Increasing trait for %s: %d",
                             account.account_name, traits['numval'])
            if traits['strval']:
                strval = ", ".join((str(traits['strval']),
                                    self.today.strftime(DATE_FORMAT)))
            else:
                strval = self.today.strftime(DATE_FORMAT)
            traits['strval'] = strval
        else:
            self.logger.info("Adding passwd trait for %s",
                             account.account_name)
            traits = {
                'code': self.constants.EntityTrait(self.config.trait),
                'target_id': None,
                'date': self.now,
                'numval': 1,
                'strval': self.today.strftime(DATE_FORMAT)
            }
        account.populate_trait(**traits)
        account.write_db()

    def get_notification_time(self, account):
        """ Fetches previous notification time.

        The notification time is stored in the date field of the notification
        trait.

        :param Cerebrum.Account account:
            The account to fetch notification time for.

        :return DateTime:
            Returns the DateTime for the previous notification, or None if the
            account has not been notified.
        """
        traits = account.get_trait(
            self.constants.EntityTrait(self.config.trait))
        if traits is None:
            return None
        else:
            return traits['date']

    def get_deadline(self, account):
        """ Calculates the deadline for password change.

        The returned datetime is when the account should be terminated.

        :param Cerebrum.Account account:
            The account to fetch a deadline time for.

        :return DateTime:
            Returns the deadline datetime.
        """
        d = self.get_notification_time(account)
        if d is None:
            d = self.today
        return d + dt.DateTimeDelta(self.config.grace_period)

    def get_account_affiliation_mapping(self, account):
        """
        Returns the affiliation_mappings value for the given account,
        based on the affiliations of the account's owner.

        :return dict or None (if no matching mapping is found in the config)
        """
        if not self.config.affiliation_mappings:
            # No mappings set
            return None
        # We want to start with the smallest 'max_password_age'
        aff_mappings = sorted(self.config.affiliation_mappings,
                              key=lambda k: k['max_password_age'])
        person = Utils.Factory.get("Person")(self.db)
        person.find(account.owner_id)
        affiliations = person.get_affiliations()
        for aff_mapping in aff_mappings:
            try:
                person_aff_code_str = self.constants.human2constant(
                    aff_mapping['affiliation'])
                if person_aff_code_str is None:
                    self.logger.error('Unknown affiliation-string "%s"',
                                      aff_mapping['affiliation'])
                    continue
                aff_code = int(person_aff_code_str)
            except KeyError:
                self.logger.error('Key "affiliation" not found in the '
                                  '"affiliation_mappings" list')
                return None
            for row in affiliations:
                if row['affiliation'] == aff_code:
                    return aff_mapping
        return None

    def remind_ok(self, account):
        """Returns true if it is time to remind"""
        n = self.get_num_notifications(account)

        try:
            a_mapping = self.get_account_affiliation_mapping(account)
        except Errors.NotFoundError:
            a_mapping = None

        if a_mapping is not None:
            reminder_delay_values = a_mapping['warn_before_expiration_days']
        else:
            reminder_delay_values = self.config.reminder_delay_values
        if 0 < n <= len(reminder_delay_values):
            delay = dt.DateTimeDelta(reminder_delay_values[n-1])
            if self.get_notification_time(account) <= self.today - delay:
                return True
        return False

    def splat_user(self, account):
        """Sets a quarantine_autopassord for account"""
        self.splatted_users.append(account.account_name)
        if not account.get_entity_quarantine(
                qtype=self.constants.quarantine_autopassord,
                only_active=True,
                ignore_disable_until=True):
            self.logger.debug("Splatting {}".format(account.account_name))
            account.delete_entity_quarantine(
                self.constants.quarantine_autopassord)
            account.add_entity_quarantine(
                self.constants.quarantine_autopassord,
                self.splattee_id,
                "password not changed",
                self.now,
                None)
            return True
        else:
            return False

    def process_accounts(self):
        self.logger.info("process_accounts started")
        if self.dryrun:
            self.logger.info("Running dry")

        old_ids = self.get_old_account_ids()
        all_ids = self.get_notified_ids().union(old_ids)
        self.logger.debug("Found %d users with old passwords", len(old_ids))

        # variables for statistics
        num_mailed = num_splatted = num_previously_warned = num_reminded = 0
        num_skipped_new_notifications = num_excepted = num_lifted = 0

        account = Utils.Factory.get("Account")(self.db)
        if self.config.change_log_account:
            account.find_by_name(self.config.change_log_account)
            cl_acc = account.entity_id
        else:
            cl_acc = None
        self.db.cl_init(change_by=cl_acc,
                        change_program=self.config.change_log_program)
        for account_id in all_ids:
            account.clear()
            account.find(account_id)
            reason = self.except_user(account)
            if reason:
                num_excepted += 1
                self.logger.info("Skipping %s -- %s",
                                 account.account_name, reason)
                continue
            if account_id not in old_ids:
                # Has new password, but may have notify trait
                num_lifted += 1
                if not self.dryrun:
                    self.remove_trait(account)
                else:
                    self.logger.info("Removing trait for %s",
                                     account.account_name)
                continue

            # now, I know the password should be old,
            if self.get_deadline(account) <= self.today:
                # Deadline given in notification is passed, splat.
                if not self.dryrun:
                    num_splatted += 1 if self.splat_user(account) else 0
                else:
                    self.logger.info("Splat user %s", account.account_name)
                    num_splatted += 1
            elif self.get_num_notifications(account) == 0:
                # Should we limit the number of new notifications?
                if (self.config.max_new_notifications and
                        num_mailed >= self.config.max_new_notifications):
                    self.logger.info(
                        "Skipping %s -- Maximum number of new notifications "
                        "reached", account.account_name)
                    num_skipped_new_notifications += 1
                    continue

                # No previously notification/warning sent. Send first-mail
                if self.notify(account):
                    if not self.dryrun:
                        self.inc_num_notifications(account)
                    else:
                        self.logger.info("First notify %s",
                                         account.account_name)
                    num_mailed += 1
                else:
                    self.rec_fail_notification(account)
                    self.logger.error("User %s not modified",
                                      account.account_name)
            else:
                num_previously_warned += 1
                if self.remind_ok(account):
                    if self.notify(account):
                        if not self.dryrun:
                            self.inc_num_notifications(account)
                        else:
                            self.logger.info(
                                "Remind %d for %s",
                                self.get_num_notifications(account),
                                account.account_name)
                        num_reminded += 1
                    else:
                        self.logger.error("User %s not modified",
                                          account.account_name)

        skipped_warnings = (
            "({} skipped, limit reached)".format(num_skipped_new_notifications)
            if num_skipped_new_notifications
            else '')

        stats = ("Users with old passwords: {}\n"
                 "Excepted users: {}\n"
                 "Splatted users: {}\n"
                 "Warned users: {} {}\n"
                 "Reminded users: {}\n"
                 "Users warned previously: {}\n"
                 "Users with new passwords: {}\n").format(
                     len(old_ids),
                     num_excepted,
                     num_splatted,
                     num_mailed,
                     skipped_warnings,
                     num_reminded,
                     num_previously_warned,
                     num_lifted)

        if self.dryrun:
            print(stats)
        elif self.config.summary_to and self.config.summary_from:
            _send_mail(
                mail_to=', '.join(self.config.summary_to),
                mail_from=self.config.summary_from,
                subject='Statistics from password notifier',
                body=stats,
                logger=self.logger,
                mail_cc=', '.join(self.config.summary_cc))

        if self.dryrun:
            self.logger.info('Rolling back changes')
            self.db.rollback()
        else:
            self.logger.info('Committing changes')
            self.db.commit()

    def except_user(self, account):
        """
        Returns a false value, or a reason for skipping this user.
        This could be overridden in a subclass to match different
        criteria.
        """
        trait = account.get_trait(
            self.constants.EntityTrait(self.config.except_trait))
        if trait:
            return "User is excepted by trait"
        return False

    def get_account_email_addr(self, account):
        """ Get email address for a given account.

        :param Cerebrum.Account account:
            The account object to fetch an email address for.

        :return str:
            Returns the account email address, or `None` if no email address
            can be found.
        """
        # Look for a primary email address
        try:
            primary = account.get_primary_mailaddress()
            self.logger.debug("Found primary email address for '%s'",
                              account.account_name)
            return primary
        except Errors.NotFoundError:
            pass

        # We try pulling out the contact type constant for e-mail via
        # ContactInfo, and use that as a forward address. If there is
        # no e-mail type in ContactInfo, we simply wont get any results
        # from the lookup of other email-addresses.
        #
        # IndexError is raised both if the e-mail ContactInfo is not
        # defined and if no e-mail address was found for the entity.
        get_entity_email = partial(account.list_contact_info,
                                   contact_type=self.constants.contact_email)
        try:
            # Look for forward addresses registered on the account:
            account_addr = get_entity_email(
                entity_id=account.entity_id)[0]['contact_value']
            self.logger.debug("Found email address for '%s' in contact info",
                              account.account_name)
            return account_addr
        except IndexError:
            pass

        # Next, look for forward addresses registered on the owner:
        try:
            owner_addr = get_entity_email(
                entity_id=account.owner_id)[0]['contact_value']
            self.logger.debug("Found email address for '%s' in contact info",
                              account.account_name)
            return owner_addr
        except IndexError:
            pass

        self.logger.warn("No email-address for %s" % account.account_name)
        return None

    def notify(self, account):
        """Placeholder for sending notifications to a user.

        This function does not implement notification. Appropriate classes
        should be mixed in for notifications to be sent.

        :param Cerebrum.Account account:
            The account object to notify.

        :return bool:
            Returns whether the notification could be sent or not.
        """
        return True

    @staticmethod
    def get_notifier(config=None):
        """ Factories a notifier class object.

        Secondary calls to get_notifier will always return the same class,
        regardless of the argument.

        :param object config:
            Any object with attributes from
            `Cerebrum.modules.password_notifier.config`.

            If `None`, an object will be generated using the default config

        :return PasswordNotifier:
            Configured PasswordNotifier class.
        """
        try:
            # If called previously, the class has been cached in
            # PasswordNotifier
            return PasswordNotifier._notifier
        except AttributeError:
            pass

        if config is None:
            config = load_config()
        else:
            config = load_config(filepath=config)

        comp_class = type(
            str('_dynamic_notifier'),
            tuple(_get_notifier_classes(config.class_notifier_values)),
            {'config': config, })
        PasswordNotifier._notifier = comp_class
        return comp_class


class EmailPasswordNotifier(PasswordNotifier):
    """ Send password notifications by E-mail. """
    def __init__(self, db=None, logger=None, dryrun=False, *rest, **kw):
        """ Constructs a PasswordNotifier that notifies by E-mail.

        :param Cerebrum.database.Database db:
            Database object to use. If `None`, this object will fetch a new db
            connection with `Factory.get('Database')`. This is the default.

        :param logging.Logger logger:
            Logger object to use. If `None`, this object will fetch a new
            logger with `Factory.get_logger('crontab')`. This is the default.

        :param bool dryrun:
            If this object should refrain from doing changes, and only print
            debug info. Default is `False`.
        """
        super(EmailPasswordNotifier,
              self).__init__(db, logger, dryrun, rest, kw)

        self.mail_info = []
        for fn in self.config.templates:
            with io.open(os.path.join(cereconf.TEMPLATE_DIR,
                                      'no_NO',
                                      'email',
                                      fn),
                         'r', encoding='UTF-8') as fp:
                msg = email.message_from_file(fp)
            self.mail_info.append({
                'Subject': email.Header.decode_header(msg['Subject'])[0][0],
                'From': msg['From'],
                'Cc': msg['Cc'],
                'Reply-To': msg['Reply-To'],
                'Body': msg.get_payload(decode=1)
            })

    def notify(self, account):
        def mail_user(account, mail_type, deadline, first_time=''):
            mail_type = min(mail_type, len(self.mail_info)-1)
            if mail_type == -1:
                self.logger.debug("No template defined")
                return False
            to_email = self.get_account_email_addr(account)
            if not to_email:
                return
            subject = self.mail_info[mail_type]['Subject']
            subject = subject.replace('${USERNAME}', account.account_name)
            body = self.mail_info[mail_type]['Body']
            body = body.replace('${USERNAME}', account.account_name)
            body = body.replace('${DEADLINE}', deadline.strftime(DATE_FORMAT))
            if isinstance(first_time, dt.DateTimeType):
                body = body.replace('${FIRST_TIME}',
                                    first_time.strftime(DATE_FORMAT))
            else:
                body = body.replace('${FIRST_TIME}', first_time)

            # add dates for different languages::
            for lang in ('nb_NO', 'nn_NO', 'en_US'):
                tag = '${DEADLINE_%s}' % lang.upper()
                body = body.replace(tag, self._date2human(deadline, lang))
                if first_time:
                    tag = '${FIRST_TIME_%s}' % lang.upper()
                    body = body.replace(tag, self._date2human(first_time,
                                                              lang))
            return _send_mail(
                mail_to=to_email,
                mail_from=self.mail_info[mail_type]['From'],
                subject=subject,
                body=body,
                logger=self.logger,
                debug_enabled=self.dryrun)

        deadline = self.get_deadline(account)
        self.logger.info(
            "Notifying %s, number=%d, deadline=%s",
            account.account_name,
            self.get_num_notifications(account) + 1,
            deadline.strftime(DATE_FORMAT))
        if self.get_num_notifications(account) == 0:
            return mail_user(
                account=account,
                mail_type=0,
                deadline=deadline)
        else:
            return mail_user(
                account=account,
                mail_type=self.get_num_notifications(account),
                deadline=deadline,
                first_time=self.get_notification_time(account))

    def _date2human(self, date, language_code=None):
        """Return a human readable string of a given date, and in the correct
        language. Making it easier for users to be sure of a deadline date."""
        DATE_FORMATS = {
            'nb_NO': '%A %-d. %B %Y',
            'nn_NO': '%x',
            'en_US': '%A, %-d %B %Y',
            None:    '%x',  # default
        }
        if language_code:
            previous = locale.getlocale(locale.LC_TIME)
            try:
                locale.setlocale(locale.LC_TIME, language_code)
            except locale.Error, e:
                warnings.warn('locale.setlocale failed: {}'.format(e),
                              RuntimeWarning)

        date_fmt = DATE_FORMATS.get(language_code) or DATE_FORMATS[None]
        ret = date.strftime(date_fmt)
        if language_code:
            locale.setlocale(locale.LC_TIME, previous)
        return ret


class SMSPasswordNotifier(PasswordNotifier):
    """ Send password notifications by SMS. """
    def __init__(self, db=None, logger=None, dryrun=False, *rest, **kw):
        """ Constructs a PasswordNotifier that notifies by SMS.

        :param Cerebrum.database.Database db:
            Database object to use. If `None`, this object will fetch a new db
            connection with `Factory.get('Database')`. This is the default.

        :param logging.Logger logger:
            Logger object to use. If `None`, this object will fetch a new
            logger with `Factory.get_logger('crontab')`. This is the default.

        :param bool dryrun:
            If this object should refrain from doing changes, and only print
            debug info. Default is `False`.
        """
        super(SMSPasswordNotifier, self).__init__(db, logger, dryrun, rest, kw)

        from os import path
        with io.open(path.join(cereconf.TEMPLATE_DIR,
                               'warn_before_splat_sms.template'),
                     'r', encoding='UTF-8') as f:
            self.template = f.read()

        self.person = Utils.Factory.get('Person')(db)

    def get_deadline(self, account):
        """ Calculates the deadline for password change.

        The returned datetime is when the account should be terminated.

        :param Cerebrum.Account account:
            The account to fetch a deadline time for.

        :return DateTime:
            Returns the deadline datetime.
        """
        trait = account.get_trait(
            self.constants.EntityTrait(self.config.follow_trait))
        d = trait['date'] if trait else None
        if d is None:
            d = self.today
        return d + dt.DateTimeDelta(self.config.grace_period)

    def remind_ok(self, account):
        """Returns true if it is time to remind"""
        try:
            a_mapping = self.get_account_affiliation_mapping(account)
        except Errors.NotFoundError:
            a_mapping = None

        if a_mapping is not None:
            reminder_delay_values = a_mapping['warn_before_expiration_days']
        else:
            reminder_delay_values = self.config.reminder_delay_values

        if (self.get_notification_time(account) == self.today or
                (self.get_num_notifications(account) >=
                 len(reminder_delay_values))):
            return False

        for days_before in reminder_delay_values:
            if ((self.get_deadline(account) -
                 dt.DateTimeDelta(days_before)) == self.today):
                return True
        return False

    def process_accounts(self):
        self.logger.info("process_accounts started")
        if self.dryrun:
            self.logger.info("Running dry")

        old_ids = self.get_old_account_ids()
        all_ids = self.get_notified_ids().union(old_ids)
        self.logger.debug("Found %d users with old passwords", len(old_ids))

        # variables for statistics
        num_excepted = 0
        num_smsed = 0
        num_lifted = 0

        account = Utils.Factory.get("Account")(self.db)
        if self.config.change_log_account:
            account.find_by_name(self.config.change_log_account)
            cl_acc = account.entity_id
        else:
            cl_acc = None
        self.db.cl_init(change_by=cl_acc,
                        change_program=self.config.change_log_program)
        for account_id in all_ids:
            account.clear()
            account.find(account_id)
            reason = self.except_user(account)
            if reason:
                num_excepted += 1
                self.logger.info("Skipping %s -- %s",
                                 account.account_name, reason)
                continue
            if account_id not in old_ids:
                # Has new password, but may have notify trait
                num_lifted += 1
                if not self.dryrun:
                    self.remove_trait(account)
                else:
                    self.logger.info("Removing trait for %s",
                                     account.account_name)
                continue
            if self.remind_ok(account):
                if self.notify(account):
                    if not self.dryrun:
                        self.inc_num_notifications(account)
                    else:
                        self.logger.info(
                            "Remind %d for %s",
                            self.get_num_notifications(account),
                            account.account_name)
                    num_smsed += 1
                else:
                    self.logger.info("User %s not notified",
                                     account.account_name)

        stats = ("Users with old passwords: {}\n"
                 "Excepted users: {}\n"
                 "SMSed users: {}\n"
                 "Users with new passwords: {}\n").format(
                     len(old_ids),
                     num_excepted,
                     num_smsed,
                     num_lifted)

        if self.dryrun:
            print(stats)
        elif self.config.summary_to and self.config.summary_from:
            _send_mail(
                mail_to=', '.join(self.config.summary_to),
                mail_from=self.config.summary_from,
                subject='Statistics from SMS password notifier',
                body=stats,
                logger=self.logger,
                mail_cc=', '.join(self.config.summary_cc))

        if self.dryrun:
            self.logger.info('Rolling back changes')
            self.db.rollback()
        else:
            self.logger.info('Committing changes')
            self.db.commit()

    def notify(self, account):
        def sms(account, days_until_splat):
            if not account.owner_type == self.constants.entity_person:
                return False
            self.person.clear()
            self.person.find(account.owner_id)
            try:
                spec = map(lambda (s, t): (self.constants.human2constant(s),
                                           self.constants.human2constant(t)),
                           cereconf.SMS_NUMBER_SELECTOR)
                mobile = self.person.sort_contact_info(
                    spec, self.person.get_contact_info())
                person_in_systems = [int(af['source_system']) for af in
                                     self.person.list_affiliations(
                                         person_id=self.person.entity_id)]
                mobile = filter(
                    lambda x: x['source_system'] in person_in_systems,
                    mobile)[0]['contact_value']
            except IndexError:
                self.logger.info(
                    'No applicable phone number for {}'.format(
                        account.account_name))
                return False

            # Send SMS
            if getattr(cereconf, 'SMS_DISABLE', False):
                self.logger.info(
                    'SMS disabled in cereconf, would have '
                    'sent password SMS to {}'.format(mobile))
                return True
            if self.dryrun:
                self.logger.info(
                    'Running in drymode. '
                    'Would have sent password SMS to {mobile}'.format(
                        mobile=mobile))
                return True
            sms = SMSSender(logger=self.logger)
            if sms(mobile, self.template.format(
                    account_name=account.account_name,
                    days_until_splat=days_until_splat)):
                return True
            else:
                self.logger.info(
                    'Unable to send message to {}.'.format(mobile))
                return False
        deadline = self.get_deadline(account)
        self.logger.info(
            "Notifying %s by SMS, number=%d, deadline=%s",
            account.account_name,
            self.get_num_notifications(account) + 1,
            deadline.strftime(DATE_FORMAT))
        return sms(
            account=account,
            days_until_splat=int(deadline - self.today))


def _send_mail(mail_to, mail_from, subject, body, logger,
               mail_cc=None, debug_enabled=False):
    if debug_enabled:
        logger.debug("Sending mail to %s. Subject: %s", mail_to, subject)
        # logger.debug("Body: %s" % body)
        return True

    try:
        sendmail(
            toaddr=mail_to,
            fromaddr=mail_from,
            subject=subject,
            body=body,
            cc=mail_cc,
            debug=debug_enabled)
    except smtplib.SMTPRecipientsRefused as e:
        failed_recipients = e.recipients
        for mail, condition in failed_recipients.iteritems():
            logger.exception("Failed when notifying %s (%s): %s",
                             mail_to, mail, condition)
        return False
    except Exception as e:
        logger.error("Error when notifying %s: %s" % (mail_to, e))
        return False
    return True
