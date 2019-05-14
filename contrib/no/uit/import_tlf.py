#! /bin/env python
# -*- coding: utf-8 -*-
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

"""
UiT specific extension to Cerebrum

This program imports data from the phone system and populates
entity_contact_info tables in Cerebrum.
"""


from __future__ import unicode_literals

import argparse
import csv
import datetime
import logging
import mx.DateTime
from sets import Set
import time

import Cerebrum.logutils
import cereconf
from Cerebrum.Utils import Factory
from Cerebrum.utils.email import sendmail
from Cerebrum import Errors

logger = logging.getLogger(__name__)

# CSV field positions
FNAME = 0
LNAME = 1
PHONE = 2
FAX = 3
MOB = 4
PHONE_2 = 5
MAIL = 6
USERID = 7
ROOM = 8
BUILDING = 9
RESERVATION = 10

db = Factory.get('Database')()
db.cl_init(change_program='import_tlf')
p = Factory.get('Person')(db)
co = Factory.get('Constants')(db)
ac = Factory.get('Account')(db)
ac_phone = Factory.get('Account')(db)


class PhoneNumberImporter(object):

    def __init__(self,
                 filename,
                 notify_recipient=False,
                 checknames=False,
                 checkmail=False):

        # Config
        self.checknames = checknames
        self.checkmail = checkmail
        self.notify_recipient = notify_recipient
        self.filename = filename

        # Variables
        self.num_changes = 0
        self.s_errors = {}
        self.processed = []

        # Remove?
        self.source_errors = None
        self.notify_queue = None

        # Caches
        self.uname_to_mail = None
        self.uname_to_ownerid = {}
        self.uname_to_expire = {}
        self.person_to_contact = {}
        self.name_cache = None

        self.init_cache(checknames)

    def str_upper_no(self, string, encoding='iso-8859-1'):
        '''Converts Norwegian iso strings to upper correctly. Eg. ��� -> ���
        Ex. Usage: my_string = str_upper_no('a�e��')'''
        return unicode(string, encoding).upper().encode(encoding)

    def init_cache(self):
        """Create caches."""
        if self.checkmail:
            logger.info("Caching account email addresses")
            self.uname_to_mail = ac.getdict_uname2mailaddr(
                filter_expired=False)
        logger.info("Caching account owners")
        for a in ac.search(expire_start=None,
                           expire_stop=datetime.datetime(
                               datetime.MAXYEAR,
                               12,
                               31)):
            self.uname_to_ownerid[a['name']] = a['owner_id']
            self.uname_to_expire[a['name']] = a['expire_date']
        if self.checknames:
            logger.info("Caching person names")
            self.name_cache = p.getdict_persons_names(
                name_types=(
                    co.name_first,
                    co.name_last,
                    co.name_work_title))
        logger.info("Caching contact info")
        for c in p.list_contact_info(source_system=co.system_tlf,
                                     entity_type=co.entity_person):
            idx = "%s:%s" % (c['contact_type'], c['contact_pref'])
            tmp = self.person_to_contact.get(c['entity_id'], dict())
            tmp[idx] = c['contact_value']
            self.person_to_contact[c['entity_id']] = tmp
        logger.info("Caching finished")

    def handle_changes(self, p_id, changes):
        """Process a change list of contact info for a given person id."""

        p.clear()
        try:
            p.find(p_id)
        except Errors.NotFoundError:
            logger.error("Person with id %s not found", p_id)
            return

        for change in changes:
            self.num_changes += 1
            change_code = change[0]
            change_value = change[1]
            idx, value = change_value
            contact_type, pref = [int(x) for x in idx.split(':')]

            if change_code == 'add_contact':
                # imitate an p.update_contact_info()
                for c in p.get_contact_info(source=co.system_tlf,
                                            type=contact_type):
                    if pref == c['contact_pref']:
                        p.delete_contact_info(co.system_tlf, contact_type,
                                              c['contact_pref'])
                p.add_contact_info(co.system_tlf,
                                   contact_type,
                                   value=value,
                                   pref=pref)

                logger.info("Add: %d:%d:%d=%s",
                            co.system_tlf,
                            contact_type,
                            pref,
                            value)

            elif change_code == 'del_contact':
                p.delete_contact_info(co.system_tlf,
                                      int(contact_type),
                                      int(pref))
                logger.info("Delete: %s, %s", change_code, change_value)
            else:
                logger.error("Unknown change_code: %s, value: &%s",
                             change_code, change_value)
        # Remove variable?
        op = p.write_db()

    def process_contact(self, user_id, data):

        owner_id = self.uname_to_ownerid.get(user_id, None)

        if owner_id is None:
            logger.error("user_id: %s not found in Cerebrum!?", user_id)
            self.s_errors.setdefault(user_id, []).append(
                "Account {0} not found in BAS".format(user_id))
            return

        # Remove MX
        if self.uname_to_expire.get(user_id, mx.DateTime.today()) < \
                mx.DateTime.today():
            self.s_errors.setdefault(user_id, []).append(
                "WARN: account {0} expired {1} in BAS".format(
                    user_id,
                    self.uname_to_expire.get(user_id).Format('%Y-%m-%d')))

        cinfo = self.person_to_contact.get(owner_id, {})
        logger.debug("Process userid=%s (owner=%s) CBData=%s",
                     user_id,
                     owner_id,
                     cinfo)
        changes = []
        idxlist = []
        contact_pref = 0
        for item in data:
            contact_pref += 1
            phone = item['phone']
            phone_2 = item['phone_2']
            mobile = item['mobile']
            mail = item['mail']
            fax = item['fax']
            room = item['room']
            tlf_fname = item['firstname']
            tlf_lname = item['lastname']
            building = item['building']

            # check contact info fields
            for value, type in ((phone, int(co.contact_phone)),
                                (mobile, int(co.contact_mobile_phone)),
                                (fax, int(co.contact_fax)),
                                (phone_2, int(co.contact_workphone2)),
                                (room, int(co.contact_room)),
                                (building, int(co.contact_building))):
                idx = "%s:%s" % (type, contact_pref)
                idxlist.append(idx)
                if value:
                    if value != cinfo.get(idx):
                        if type == int(co.contact_phone):
                            # only add contact_phone if it really is a new
                            # phone number
                            if self.is_new_number(value, owner_id):
                                changes.append(('add_contact', (idx, value)))
                        else:
                            changes.append(('add_contact', (idx, value)))
                else:
                    if cinfo.get(idx):
                        changes.append(('del_contact', (idx, None)))

            # check if sourcesys has same mailaddr as we do
            if self.checkmail and mail and self.uname_to_mail.get(
                    user_id,
                    "").lower() != mail.lower():

                self.s_errors.setdefault(user_id, []).append(
                    "Email wrong: yours=%s, ours=%s" % (
                        mail,
                        self.uname_to_mail.get(user_id)))

            # check name spelling.
            if self.checknames:
                namelist = self.name_cache.get(owner_id, None)
                if namelist:
                    cb_fname = namelist.get(int(co.name_first), "")
                    cb_lname = namelist.get(int(co.name_last), "")

                    worktitle = namelist.get(int(co.name_work_title), "")
                    if cb_fname != tlf_fname or cb_lname != tlf_lname:
                        self.s_errors.setdefault(user_id, []).append(
                            "Name spelling differ: yours=%s %s, ours=%s %s" %
                            (tlf_fname, tlf_lname, cb_fname, cb_lname))

        db_idx = Set(cinfo.keys())
        src_idx = Set(idxlist)
        for idx in db_idx - src_idx:
            changes.append(('del_contact', (idx, None)))

        if changes:
            logger.info("Changes [%s/%s]: %s" % (user_id, owner_id, changes))
            self.handle_changes(owner_id, changes)
            logger.info("Update contact and write_db done")
        self.processed.append(owner_id)

    def update_phonenr(self, uid, phone):
        """
        Write modified phone number to database.

        Do not update the database if the phone/contact info already exists
        in the database
        """
        ac_phone.clear()
        try:
            ac_phone.find_by_name(uid)
        except Errors.NotFoundError:
            logger.error("Unable to find user:%s", uid)
            return
        logger.debug("Writeback: uid: %s - %s", uid, phone)
        ac_phone.populate_contact_info(co.system_tlf, co.contact_phone, phone)
        ac_phone.write_db()

    def delete_phonenr(self, uid, phone):
        """
        Delete the (work) phonenumber for a given uid with source = telefoni.
        """
        ac_phone.clear()
        try:
            ac_phone.find_by_name(uid)
        except Errors.NotFoundError:
            logger.error("unable to find user:'%s' Continue with next user",
                         uid)
            return

        logger.debug("%s has account id:%s", uid, ac_phone.entity_id)

        if len(phone) == 5:
            # sanity check. only delete 5digit numbers
            logger.debug("Deleting phone number: %s", phone)
            ac_phone.delete_contact_info(source=co.system_tlf,
                                         contact_type=co.contact_phone)
            ac_phone.write_db()
        else:
            logger.debug("Not deleting phone number: %s", phone)

    def is_new_number(self, phone_number, owner_id):
        """
        Check if a phone number is new for a owner_id.

        Note: Only checks for phone numbers of type co.contact_phone.
        """
        number_found = False
        is_new_number = False
        data_phone_len = len(phone_number)

        if owner_id in self.person_to_contact.keys():
            for key, val in self.person_to_contact[owner_id].iteritems():
                contact_type = int(key[:3])
                if contact_type == int(co.contact_phone):
                    num_to_compare = val
                    if len(num_to_compare) > data_phone_len:
                        num_to_compare = num_to_compare[-data_phone_len:]
                    if num_to_compare == phone_number:
                        number_found = True
        if not number_found:
            is_new_number = True
        return is_new_number

    def convert(self, data, encoding='utf-8'):
        if isinstance(data, dict):
            return {self.convert(key): self.convert(value, encoding)
                    for key, value in data.iteritems()}
        elif isinstance(input, list):
            return [self.convert(element, encoding) for element in data]
        elif isinstance(data, bytes):
            return data.decode(encoding)
        else:
            return data

    def process_telefoni(self):
        """
        we will add a prefix to internal phone numbers based on their first
        digits.
        and we will mark some numbers for deletion, also based on prefix.
        """
        prefix_table = [
            # (internal number first digits, prefix to add or "DELETE")
            ("207", "776"),
            ("208", "776"),
            ("209", "776"),
            ("231", "776"),
            ("232", "776"),
            ("233", "776"),
            ("251", "776"),
            ("252", "776"),
            ("26", "DELETE"),
            ("27", "DELETE"),
            ("28", "DELETE"),
            ("44", "776"),
            ("45", "776"),
            ("46", "776"),
            ("483", "776"),
            ("490", "776"),
            ("491", "776"),
            ("492", "776"),
            ("50", "784"),
            ("505", "784"),
            ("55", "DELETE"),
            ("58", "770"),
            ("602", "776"),
            ("603", "776"),
            ("604", "776"),
            ("605", "776"),
            ("606", "776"),
            ("607", "776"),
            ("608", "776"),
            ("609", "776"),
            ("62", "769"),
            ("660", "769"),
            ("661", "769"),
            ("662", "769"),
            ("663", "769"),
            ("664", "769"),
            ("665", "769"),
            ("66", "769"),
            ("69", "DELETE"),
        ]

        reader = csv.reader(open(self.filename, 'r'), delimiter=str(';'))
        phonedata = {}

        for row in reader:
            # convert to unicode
            row = self.convert(row, 'iso-8859-1')
            # print type(row)

            if row[RESERVATION].lower() == 'kat' and row[USERID].strip():

                if row[USERID].strip() != row[USERID]:
                    logger.error("Userid %s has blanks in it. Notify " +
                                 "telefoni!", row[USERID])

                data = {'phone': row[PHONE],
                        'mobile': row[MOB],
                        'room': row[ROOM],
                        'mail': row[MAIL],
                        'fax': row[FAX],
                        'phone_2': row[PHONE_2],
                        'firstname': row[FNAME],
                        'lastname': row[LNAME],
                        'building': row[BUILDING]}

                if row[USERID] not in self.uname_to_ownerid:
                    logger.warn("Unknown user: %s, continue with next user",
                                row[USERID])
                    continue

                # Set phone extension or mark for deletion based on the first
                # internal number's digits
                added_prefix = False
                changed_phone = False

                for internal_first_digits, prefix in prefix_table:

                    if len(data['phone']) == 5 and data['phone'].startswith(
                            internal_first_digits):

                        if prefix == "DELETE":
                            logger.debug("DELETE: %s - %s",
                                         row[USERID],
                                         data['phone'])

                            # Delete the phonenumber from the database
                            self.delete_phonenr(row[USERID], data['phone'])

                        else:
                            logger.debug('unmodified phone:%s', data['phone'])
                            data['phone'] = "%s%s" % (prefix, data['phone'])
                            logger.debug('modified phone:%s', data['phone'])

                            if self.is_new_number(
                                    data['phone'],
                                    self.uname_to_ownerid[row[USERID]]):
                                changed_phone = True
                        added_prefix = True
                        break
                if data['phone'] and not added_prefix:
                    logger.warning(
                        'Userid %s has a malformed internal phone number '
                        'or a number that does not have a match '
                        'in our number prefix table:%s', row[USERID], data)
                    logger.debug("INVALID: %s - %s",
                                 row[USERID],
                                 data['phone'])

                # add "+47" phone number prefix
                if data['phone'] and (self.is_new_number(
                        data['phone'],
                        self.uname_to_ownerid[row[USERID]])):

                    changed_phone = True
                    if not data['phone'].startswith('+47'):
                        data['phone'] = "%s%s" % ("+47", data['phone'])
                    logger.debug("%s's phone number with +47 prefix: %s",
                                 row[USERID],
                                 data['phone'])

                if changed_phone:
                    self.update_phonenr(row[USERID], data['phone'])
                phonedata.setdefault(row[USERID].strip(), []).append(data)

        for user_id, pdata in phonedata.items():
            self.process_contact(user_id, pdata)

        unprocessed = set(self.person_to_contact.keys()) - set(self.processed)

        for p_id in unprocessed:
            changes = list()
            contact_info = self.person_to_contact[p_id]

            for idx, value in contact_info.items():
                changes.append(('del_contact', (idx, None)))
            logger.debug("person(id=%s) not in source data, changes=%s",
                         p_id,
                         changes)

            self.handle_changes(p_id, changes)

        if self.s_errors:
            msg = {}
            for userid, error in self.s_errors.items():
                fname = phonedata[userid][0]['firstname']
                lname = phonedata[userid][0]['lastname']
                key = '%s %s (%s)' % (fname, lname, userid)
                msg[key] = list()
                for i in error:
                    msg[key].append("\t%s\n" % (i,))

            keys = msg.keys()
            keys.sort()
            mailmsg = ""
            for k in keys:
                mailmsg += k + '\n'
                for i in msg[k]:
                    mailmsg += i

            self.notify_phoneadmin(mailmsg)

    def notify_phoneadmin(self, msg):
        """Send email with import errors."""
        recipient = cereconf.TELEFONIERRORS_RECEIVER
        sender = cereconf.SYSX_EMAIL_NOTFICATION_SENDER
        subject = 'Import telefoni errors from Cerebrum {0}'.format(
            time.strftime('%Y%m%d'))
        if self.notify_recipient:
            sendmail(recipient, sender, subject, msg)
        else:
            logger.warn("Do not notify phone admin via email")


def main():
    parser = argparse.ArgumentParser(description=__doc__)

    global dryrun
    default_phonefile = '%s/telefoni/user_%s.txt' % (cereconf.DUMPDIR,
                                                     time.strftime('%Y%m%d'))
    parser.add_argument(
        '-f',
        '--file',
        dest='file',
        default=default_phonefile,
        help='Contact info source file. Default is user_yyyymmdd.txt in '
             'dumps/telefon',
    )
    parser.add_argument(
        '--commit',
        dest='commit',
        action='store_true',
        help='Commit changes to DB',
    )
    parser.add_argument(
        '-F',
        '--force',
        dest='force',
        action='store_true',
        help='force write, ignoring cereconf.MAX_NUM_ALLOWED_CHANGES',
    )
    parser.add_argument(
        '-e',
        '--no-email',
        dest='notify_recipient)',
        action='store_false',
        help='do not notify cereconf.TELEFONIERRORS_RECEIVER with log '
             'messages',
    )
    parser.add_argument(
        '--checknames',
        dest='checknames',
        action='store_true',
        help='Check name spelling.',
    )
    parser.add_argument(
        '--checkmail',
        dest='checkmail',
        action='store_true',
        help='Check mails.',
    )
    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args()
    Cerebrum.logutils.autoconf('cronjob', args)
    logger.info('Starting phone number import')

    phone_importer = PhoneNumberImporter(
        args.file,
        notify_recipient=args.notify_recipient,
        checkmail=args.checkmail,
        checknames=args.checknames,
    )

    logger.info('Using sourcefile: %s', args.phonefile)

    phone_importer.process_telefoni()

    num_changes = phone_importer.num_changes
    max_changes_allowed = int(cereconf.MAX_NUM_ALLOWED_CHANGES)
    logger.debug("Max number of allowed changes:%s", max_changes_allowed)
    logger.debug("Number of changes:%s", num_changes)

    if args.commit:
        if args.force:
            db.commit()
            logger.warning("Forced writing: %s changes in phone processing")
        elif num_changes <= max_changes_allowed:
            db.commit()
            logger.info("Committing changes")
        else:
            db.rollback()
            logger.error("Too many changes: %s. Rolling back changes",
                         num_changes)
    else:
        db.rollback()
        logger.info("Dryrun, Rolling back changes")
    logger.info('End of phone number import.')


if __name__ == "__main__":
    main()
