#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2017 University of Oslo, Norway
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

"""Set quarantine auto_inaktiv on people with only STUDENT/opptak as
affiliation and (optionally) a invalid registerkort."""

import datetime
import collections
import functools

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.utils.email import mail_template
from Cerebrum.modules.no.access_FS import make_fs

logger = Factory.get_logger('cronjob')


def notify(commit, logger, days_to_start, ac):
    try:
        mailaddress = ac.get_primary_mailaddress()
    except Errors.NotFoundError:
        logger.warning('No E-mail address for {}'.format(ac.account_name))
        return

    try:
        mail_template(mailaddress,
                      'no_NO/email/karantenesetting.txt',
                      'noreply@usit.uio.no',
                      substitute={
                          'USERNAME': ac.account_name,
                          'DAYS_TO_START': str(days_to_start)
                      },
                      debug=not commit)
    except Exception as e:
        logger.warning('Could not send email to {}: {}'.format(mailaddress, e))

    if commit:
        logger.info('Sent email to {}'.format(mailaddress))
    else:
        logger.info('Would have sent message to {}'.format(
            ac.get_primary_mailaddress()))


def get_db(commit):
    db = Factory.get('Database')()
    from sys import argv
    db.cl_init(change_program=argv[0].split('.', 1)[0])
    if not commit:
        db.commit = db.rollback
    return db


def commit(db):
    db.commit()
    if db.commit != db.rollback:
        return True
    else:
        return False


def regkort_ok(db, fs_db, person_id):
    pe = Factory.get('Person')(db)
    co = Factory.get('Constants')(db)
    pe.clear()
    pe.find(person_id)
    try:
        fnr = pe.get_external_id(co.system_fs,
                                 co.externalid_fodselsnr)[0]['external_id']
    except IndexError:
        # Cannot look up person, be polite
        return True
    return True if fs_db.student.get_semreg(fnr[:6],
                                            fnr[6:]) else False


def get_targets(db, regkort_check=True):
    fs_db = make_fs()
    co = Factory.get('Constants')(db)
    pe = Factory.get('Person')(db)
    t = collections.defaultdict(list)
    for r in pe.list_affiliations(fetchall=False):
        t[r['person_id']].append(r['status'])
    for k in t:
        if [co.affiliation_status_student_opptak] == t[k]:
            if regkort_check and regkort_ok(db, fs_db, k):
                continue
            yield k


def alter_quarantines(db, logger, targets, notify, expire_in_days=0):
    co = Factory.get('Constants')(db)
    pe = Factory.get('Person')(db)
    ac = Factory.get('Account')(db)
    ac.find_by_name('bootstrap_account')
    bootstrap_id = ac.entity_id
    quarantines_start = (datetime.datetime.now() +
                         datetime.timedelta(days=expire_in_days))
    quarantined = []
    for row in ac.list_entity_quarantines(
            entity_types=co.entity_account,
            quarantine_types=co.quarantine_auto_inaktiv):
        if (row['start_date'] <= quarantines_start and
                not row['disable_until'] and
                not row['end_date']):
            quarantined.append(row['entity_id'])

    for t in targets(db):
        pe.clear()
        pe.find(t)
        for a in pe.get_accounts():
            ac.clear()
            ac.find(a['account_id'])
            if a['account_id'] not in quarantined:
                ac.delete_entity_quarantine(co.quarantine_auto_inaktiv)
                ac.add_entity_quarantine(co.quarantine_auto_inaktiv,
                                         bootstrap_id,
                                         start=quarantines_start)
            notify(ac)
            logger.info('Added quarantine {} to {}'.format(
                co.quarantine_auto_inaktiv,
                ac.account_name))


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description='Set quarantine auto_inaktiv on people with only '
                    'STUDENT/opptak as affiliation and an invalid '
                    'registerkort')
    parser.add_argument('--commit',
                        action='store_true',
                        help='Run in commit-mode')
    parser.add_argument('--skip-regkort-check',
                        action='store_false',
                        default=True,
                        dest='regkort_check',
                        help='Don\'t exclude persons with a valid '
                             'registerkort')
    parser.add_argument('--expire-in-days',
                        dest='expire_in_days',
                        type=int,
                        default=0,
                        metavar='N',
                        help='Quarantine starts in N days')
    args = parser.parse_args()

    db = get_db(args.commit)
    logger.info('Starting in {} mode with regkort check {}…'.format(
        'commit' if args.commit else 'rollback',
        'enabled' if args.regkort_check else 'disabled'))
    alter_quarantines(db,
                      logger,
                      functools.partial(get_targets,
                                        regkort_check=args.regkort_check),
                      functools.partial(notify,
                                        args.commit,
                                        logger,
                                        args.expire_in_days),
                      args.expire_in_days)
    if commit(db):
        logger.info('Commited changes')
    else:
        logger.info('Rolled changes back')


if __name__ == "__main__":
    main()
