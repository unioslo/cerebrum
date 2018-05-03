#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2006 University of Oslo, Norway
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

import sys
import getopt

import cerebrum_path
import cereconf

from Cerebrum.Utils import Factory
from Cerebrum.utils.atomicfile import SimilarSizeWriter
from Cerebrum.modules import Email, LDIFutils

LDIFutils.needs_base64 = LDIFutils.needs_base64_safe
LDIFutils.base64_attrs.update({
    'userpassword': 0, 'ofkpassword': 0, 'userpasswordct': 0})


def get_account_info():
    global a_id2email, p_id2name, p_id2fnr, a_id2auth
    global p_id2a_id, ou_id2name
    global acc_spreads, ou_spreads

    acc_spreads = []
    ou_spreads = []
    a_id2email = dict()
    for row in et.list_email_target_primary_addresses():
        a_id2email[int(row['target_entity_id'])] = "%s@%s" % (row['local_part'],
                                                              row['domain'])

    p_id2name = p.getdict_persons_names(source_system=co.system_cached,
                                        name_types=(co.name_first,co.name_last))
    p_id2fnr = dict()
    for row in p.list_external_ids(id_type=co.externalid_fodselsnr):
        p_id2fnr[int(row['entity_id'])] = row['external_id']

    a_id2auth = dict()
    for row in ac.list_account_authentication(auth_type=(co.auth_type_md4_nt,
                                                         co.auth_type_plaintext,
                                                         co.auth_type_ssha)):
        aid = int(row['account_id'])
        if row['method'] is None:
            continue
        a_id2auth.setdefault(aid, [])
        if len(a_id2auth[aid]) != 2:
            a_id2auth[aid].insert(0, row['entity_name'])
            a_id2auth[aid].insert(1, dict())
        a_id2auth[aid][1].setdefault(int(row['method']), row['auth_data'])

    p_id2a_id = dict()
    for row in ac.list_accounts_by_type(primary_only=True):
        p_id2a_id[int(row['person_id'])] = int(row['account_id'])

    ou_id2name = dict((r["entity_id"], r["name"])
                      for r in ou.search_name_with_language(entity_type=co.entity_ou,
                                     name_variant=co.ou_name_acronym,
                                     name_language=co.language_nb))

    for row in ac.list_all_with_spread(co.spread_oid_acc):
        acc_spreads.append(row['entity_id'])

    for row in ou.list_all_with_spread(co.spread_oid_ou):
        ou_spreads.append(row['entity_id'])

def process_txt_file(file):
    users_ou = dict()

    for row in p.list_affiliations():
        id = int(row['person_id'])
        aff = int(row['affiliation'])
        ou_id = int(row['ou_id'])
        if not p_id2a_id.has_key(id):
            # no user
            logger.info("No user found for '%s'" % id)
            continue
        a_id = p_id2a_id[id]
        if not (a_id2auth.has_key(a_id) and a_id2auth[a_id][0]):
            # No username
            logger.warning("ptf: No user found for person '%s'" % id)
            continue
        if not p_id2fnr.has_key(id):
            logger.warning("Fnr not found for '%s'" % id)
            continue
        uname = a_id2auth[a_id][0]
        pwd = ""
        if a_id2auth[a_id][1] is not None:
            pwd = a_id2auth[a_id][1][int(co.auth_type_plaintext)]
        if id not in p_id2name or \
               (int(co.name_first) not in p_id2name[id] or \
                int(co.name_last) not in p_id2name[id]):
            logger.warning("Names not found for person id='%s'" % id)
            continue
        if not ou_id2name.has_key(ou_id):
            logger.warning("OU name not found for '%s'" % ou_id)
            continue
        p_names = p_id2name[id]
        first = p_names[int(co.name_first)]
        last = p_names[int(co.name_last)]
        if not a_id2email.has_key(a_id):
            logger.warning("Mail-addr not found for '%s', '%s'" % (id, uname))
            continue
        txt = '$'.join((p_id2fnr[id], uname, pwd,
                        a_id2email[a_id],
                        ou_id2name[ou_id], first, last)) + '\n'
        file.write(txt)
        if ou_id in ou_spreads and a_id in acc_spreads:
            users_ou.setdefault(ou_id2name[ou_id], {}).setdefault(aff, []).append(uname)
    return users_ou


def main():
    global db, co, ac, p, ou, et, logger

    logger = Factory.get_logger("cronjob")

    db = Factory.get('Database')()
    co = Factory.get('Constants')(db)
    ac = Factory.get('Account')(db)
    p = Factory.get('Person')(db)
    ou = Factory.get('OU')(db)
    et = Email.EmailTarget(db)

    txt_path = "/cerebrum/var/cache/txt"

    options, rest = getopt.getopt(sys.argv[1:],
                                  "t:", ["txt-path=",])
    for option, value in options:
        if option in ("-t", "--txt-path"):
            txt_path = value

    # Load dicts with misc info.
    get_account_info()

    # Dump OFK info
    f = SimilarSizeWriter("%s/ofk.txt" % txt_path, "w")
    f.max_pct_change = 10
    users = process_txt_file(f)
    f.close()

if __name__ == '__main__':
    main()

