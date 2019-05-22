#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2002-2019 University of Oslo, Norway
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
from __future__ import print_function, unicode_literals

import getopt
import logging
import os
import sys
import time

import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.legacy_users import LegacyUsers
from Cerebrum.modules.no.uit import Email
from Cerebrum.utils.email import mail_template, sendmail

logger = logging.getLogger(__name__)
today = time.strftime("%Y%m%d")


class Changer(object):

    def __init__(self, db):
        self.db = db
        self.co = Factory.get('Constants')(self.db)
        self.account_old = Factory.get('Account')(self.db)
        self.account_new = Factory.get('Account')(self.db)
        self.constants = Factory.get('Constants')(self.db)
        self.db.cl_init(change_program='ren_acc')

    def rename_account(self, old_name, new_name):
        logger.info("Renaming account from=%r to=%r", old_name, new_name)
        ret_value = None

        try:
            # self.pu_old.find_by_name(old_name)
            self.account_old.find_by_name(old_name)
        except Errors.NotFoundError:
            logger.error("Account name=%r not found!", old_name)
            # TODO: re-raise?
            sys.exit(-1)
        else:
            logger.info("Account name=%r (id=%r) located...",
                        old_name, self.account_old.entity_id)

        try:
            self.account_new.find_by_name(new_name)
        except Errors.NotFoundError:
            logger.info("Account name=%r is free, GOOOODIE", new_name)
            self.account_new.clear()
        else:
            logger.info("Account name=%r is already in use. Cannot continue!",
                        new_name)
            # TODO: re-raise?
            sys.exit(-1)

        self.account_old.update_entity_name(self.co.account_namespace,
                                            new_name)
        self.account_old.write_db()

        # write_db does not update object instace variables (ie account_name
        # after a call to update_entity_name. so create a new object instance
        # based on new account name, and update its email and homes.
        self.account_new.find_by_name(new_name)
        spreads = self.account_new.get_spread()
        for s in spreads:
            int_s = int(s[0])
            self.account_new.set_home_dir(int_s)
            logger.info(" - updated homedir for spread code=%r", int_s)

        ret_value = self.update_email(self.account_new, old_name, new_name)
        try:
            self.account_new.write_db()
        except Exception:
            # TODO: Why continue here? Re-raise exception?
            logger.error("Failed writing updates to database", exc_info=True)
        return ret_value

    def commit(self):
        self.db.commit()
        logger.info("Commited all changes to database")

    def rollback(self):
        self.db.rollback()
        logger.info("DRYRUN: Rolled back all changes")

    def update_email(self, account_obj, old_name, new_name):
        ret_value = None

        current_email = ""
        try:
            current_email = account_obj.get_primary_mailaddress()
        except Errors.NotFoundError:
            # no current primary mail.
            pass

        em = Email.email_address(self.db)
        ad_email = em.get_employee_email(account_obj.account_name)
        if len(ad_email) > 0:
            ad_email = ad_email[account_obj.account_name]

        try:
            current_email.split('@')[1] == cereconf.NO_MAILBOX_DOMAIN_EMPLOYEES
            if current_email.split('@')[0] == account_obj.account_name:
                ad_email = current_email
            else:
                ad_email = "%s@%s" % (account_obj.account_name,
                                      cereconf.NO_MAILBOX_DOMAIN_EMPLOYEES)
        except IndexError:
            # no email in ad_email table for this account.
            # IF this account has a student affiliation.
            #   do not update primary email address with an invalid code.
            # IF this account does NOT have a student affiliation.
            #   update the email primary address with the invalid code.
            acc_type = account_obj.list_accounts_by_type(
                account_id=account_obj.entity_id,
                affiliation=self.constants.affiliation_student)
            if len(acc_type) > 0:
                ad_email = "%s@%s" % (account_obj.account_name,
                                      cereconf.NO_MAILBOX_DOMAIN)
            else:
                no_mailbox_domain = cereconf.NO_MAILBOX_DOMAIN
                logger.warning("No ad email for account_id=%r, name=%r, "
                               "defaulting to domain=%r",
                               account_obj.entity_id, account_obj.account_name,
                               no_mailbox_domain)
                ad_email = "%s@%s" % (account_obj.account_name,
                                      no_mailbox_domain)
                # TODO: warning?
                logger.warning("ad_email=%r", ad_email)

        if current_email.lower() != ad_email.lower():
            # update email!
            logger.debug("Email update needed old=%r, new=%r",
                         current_email, ad_email)
            try:
                em.process_mail(account_obj.entity_id, ad_email, True)

                # MAIL PERSON INFO
                person_info = {
                    'OLD_USER': old_name,
                    'NEW_USER': new_name,
                    'OLD_MAIL': current_email,
                    'NEW_MAIL': ad_email,
                }
                ret_value = person_info

            except Exception:
                logger.critical("Email update failed for account_id=%r, "
                                "email=%r", account_obj.entity_id, ad_email)
                # TODO: re-raise?
                sys.exit(2)
        else:
            # current email = ad_email :=> we need to do nothing. all is ok....
            logger.debug("Email update not needed (old=%r, new=%r)",
                         current_email, ad_email)
            pass

        return ret_value


def usage(exitcode=0):
    print("""Usage: extend_account.py -o name -n newname [-h] [-d]
    -h | --help : show this message
    -d | --dryrun : do not commit changes to database
    -o | --old <name> : old account name to change (REQUIRED)
    -n | --new <name> : new account name set as new (REQUIRED)
    -N | --no-email   : do not send out email to user
    """)
    if exitcode == 1:
        print("You must supply a old account name!")
    elif exitcode == 2:
        print("You must supply a new account name!")
    sys.exit(exitcode)


def ask_yn(question, default=False):
    if question:
        print(question)
    if default:
        prompt = '[Y]/n'
    else:
        prompt = 'y/[N]'

    while True:
        resp = raw_input(prompt + ': ').strip().lower()
        if resp == 'y':
            return True
        elif resp == 'n':
            return False
        elif resp == '':
            return default
        else:
            print('Invalid input')
            continue


def main():
    dryrun = False
    old_name = None
    new_name = None
    notify_user = True
    try:
        opts, args = getopt.getopt(
            sys.argv[1:],
            'hdn:o:N',
            ['help', 'dryrun', 'new=', 'old=', 'no_email'])
    except getopt.GetoptError as m:
        print("wrong arguments: %s" % m)
        usage(1)

    for opt, val in opts:
        if opt in ['-h', '--help']:
            usage(0)
        elif opt in ['-d', '--dryrun']:
            dryrun = True
        elif opt in ['-n', '--new']:
            new_name = val
        elif opt in ['-N', '--no-email']:
            notify_user = False
        elif opt in ['-o', '--old']:
            old_name = val

    if not old_name:
        usage(1)

    if not new_name:
        usage(2)

    db = Factory.get('Database')()
    worker = Changer(db)
    send_user_mail = None

    co = Factory.get('Constants')(db)
    ac = Factory.get('Account')(db)
    pe = Factory.get('Person')(db)

    # Find person full name (old)
    ac.find_by_name(old_name)
    pe.find(ac.owner_id)
    old_person_name = pe.get_name(co.system_cached, co.name_full)
    ac.clear()
    pe.clear()

    print("old_name:%s" % old_name)
    print("new name:%s" % new_name)
    send_user_mail = worker.rename_account(old_name, new_name)

    if dryrun:
        worker.rollback()
    else:

        # Find person full name (new)
        ac.find_by_name(new_name)
        pe.find(ac.owner_id)
        new_person_name = pe.get_name(co.system_cached, co.name_full)

        print("Old name:", new_person_name)
        print("New name:", old_person_name)
        print("Notify user:", notify_user)
        is_sure = ask_yn("Are you sure you want to write changes?")

        if is_sure:
            print(old_name, new_name)

            legacy_info = {}
            legacy_info['username'] = old_name
            try:
                legacy_info['ssn'] = pe.get_external_id(
                    id_type=co.externalid_fodselsnr)[0]['external_id']
            except Exception:
                legacy_info['ssn'] = None
            legacy_info['source'] = 'MANUELL'
            legacy_info['type'] = 'P'
            legacy_info['comment'] = '%s - Renamed from %s to %s.' % (today,
                                                                      old_name,
                                                                      new_name)
            legacy_info['name'] = pe.get_name(co.system_cached, co.name_full)

            try:
                mydb = Factory.get('Database')()
                lu = LegacyUsers(mydb)
                lu.set(**legacy_info)
                mydb.commit()
            except Exception:
                # TODO: Still continue?
                print("Could not write to legacy_users. "
                      "Username is probably already reserved")

            # Sending email to SUT queue in RT
            if not dryrun:
                # account_expired = ''
                # if ac.is_expired():
                #     account_expired = (' Imidlertid er ikke kontoen aktiv, '
                #                        'men kan reaktiveres når som helst.')

                # TBD : remove comment below when leetah is removed
                # sendmail(
                #     toaddr='star-gru@orakel.uit.no',
                #     fromaddr='bas-admin@cc.uit.no',
                #     subject=('Brukernavn endret (%s erstattes av %s)' %
                #              (old_name, new_name)),
                #     body=('Brukernavnet %s er endret til %s. Videresend '
                #           'e-post, flytt filer, e-post, osv. fra %s til '
                #           '%s.%s' %
                #           (old_name, new_name, old_name, new_name,
                #            account_expired)),
                #     cc=None,
                #     charset='iso-8859-1',
                #     debug=False)
                # print("mail sent to star-gru@orakel.uit.no")
                pass

            # Sending email to PORTAL queue in RT
            if False and not dryrun:
                # account_expired = ''
                # if ac.is_expired():
                #     account_expired = (' Imidlertid er ikke kontoen aktiv, '
                #                        'men kan reaktiveres når som helst.')

                sendmail(
                    toaddr='vevportal@rt.uit.no',
                    fromaddr='bas-admin@cc.uit.no',
                    subject=('Brukernavn endret (%s erstattes av %s)' %
                             (old_name, new_name)),
                    body=('Brukernavnet %s er endret til %s.' %
                          (old_name, new_name)),
                    cc=None,
                    charset='iso-8859-1',
                    debug=False)
                print("mail sent to vevportal@rt.uit.no")

            # Sending email to AD nybrukere if necessary
            mailto_ad = False
            try:
                spreads = ac.get_spread()
                for spread in spreads:
                    if spread['spread'] == co.spread_uit_ad_account:
                        mailto_ad = True
                        break
            except Exception:
                print("No AD spread found.")

            riktig_brukernavn = ' Nytt brukernavn er %s.' % (new_name)

            if ac.is_expired():
                riktig_brukernavn += (' Imidlertid er ikke kontoen aktiv, og '
                                      'vil kun sendes til AD når den blir '
                                      'reaktivert.')

            if False and mailto_ad and not dryrun:
                sendmail(
                    toaddr='nybruker2@asp.uit.no',
                    fromaddr='bas-admin@cc.uit.no',
                    subject='Brukernavn endret',
                    body=('Brukernavnet %s er endret i BAS.%s' %
                          (old_name, riktig_brukernavn)),
                    cc=None,
                    charset='iso-8859-1',
                    debug=False)
                print("mail sent to nybruker2@asp.uit.no")

            pe.clear()
            ac.clear()
            if not notify_user:
                print("not sending email to user")
            elif send_user_mail is not None:
                # SEND MAIL TO OLD AND NEW ACCOUNT + "BCC" to bas-admin!
                sender = 'orakel@uit.no'
                recipient = send_user_mail['OLD_MAIL']
                cc = [send_user_mail['NEW_MAIL']]
                template = os.path.join(cereconf.CB_SOURCEDATA_PATH,
                                        'templates/rename_account.tmpl')

                # TBD: remove below comment when leetah is removed
                # result = mail_template(
                #     recipient=recipient,
                #     template_file=template,
                #     sender=sender,
                #     cc=cc,
                #     substitute=send_user_mail,
                #     charset='utf-8',
                #     debug=dryrun)

                print("Mail sent to: %s" % (recipient))
                print("cc to %s" % (cc))

                # if dryrun:
                #     print("\nDRYRUN: mailmsg=\n%s" % result)

                # BCC
                recipient = 'bas-admin@cc.uit.no'
                template = os.path.join(cereconf.CB_SOURCEDATA_PATH,
                                        'templates/rename_account.tmpl')
                mail_template(
                    recipient=recipient,
                    template_file=template,
                    sender=sender,
                    substitute=send_user_mail,
                    charset='utf-8',
                    debug=dryrun)

                print("BCC sent to: %s" % (recipient))
            worker.commit()
        else:
            worker.rollback()


if __name__ == '__main__':
    main()
