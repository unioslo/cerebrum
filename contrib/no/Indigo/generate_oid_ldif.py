#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

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
from Cerebrum.Utils import SimilarSizeWriter
from Cerebrum.modules import Email, LDIFutils
from Cerebrum.modules.LDIFutils import entry_string, iso2utf
from Cerebrum.Constants import _PersonAffStatusCode

LDIFutils.needs_base64 = LDIFutils.needs_base64_safe
LDIFutils.base64_attrs.update({
    'userpassword': 0, 'ofkpassword': 0, 'userpasswordct': 0})


def get_person_contact():
    global p_id2cont

    p_id2cont = dict()
    for row in p.list_contact_info(contact_type=co.contact_mobile_phone,
                                   entity_type=co.entity_person):
        # Assume we have only one contact type of this sort
        p_id2cont[row['entity_id']] = row['contact_value']
        


def get_account_info():
    global a_id2email, p_id2name, p_id2fnr, a_id2auth
    global a_id2p_id, p_id2a_id, ou_id2name, const2str

    a_id2email = dict()
    for row in et.list_email_target_primary_addresses():
        a_id2email[int(row['entity_id'])] = "%s@%s" % (row['local_part'], row['domain'])

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
        if len(a_id2auth[aid]) <> 2:
            a_id2auth[aid].insert(0, row['entity_name'])
            a_id2auth[aid].insert(1, dict())
        a_id2auth[aid][1].setdefault(int(row['method']), row['auth_data'])

    a_id2p_id = dict()
    p_id2a_id = dict()
    for row in ac.list():
        a_id2p_id[row['account_id']] = (int(row['owner_type']),
                                         row['owner_id'])
        if int(row['owner_type']) == int(co.entity_person):
            p_id2a_id[int(row['owner_id'])] = int(row['account_id'])
    ou_id2name = dict()
    for row in ou.search():
        ou_id2name[int(row['ou_id'])] = str(row['acronym'])

    const2str = dict()
    const2str[int(co.affiliation_ansatt)] = "ANSATTE"
    const2str[int(co.affiliation_elev)] = "ELEVER"
    const2str[int(co.affiliation_tilknyttet)] = "TILKNYTTET"
    
    
def process_txt_file(file):
    users_ou = dict()

    for row in p.list_affiliations():
        id = int(row['person_id'])
        aff = int(row['affiliation'])
        ou_id = int(row['ou_id'])
        if not p_id2a_id.has_key(id):
            # no user
            logger.warning("No user found for '%s'" % id)
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
        if not (p_id2name.has_key(id) or \
                p_id2name[id].get(int(co.name_first)) or \
                p_id2name[id].get(int(co.name_last))):
            logger.warning("Names not found for '%s'" % id)
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
        users_ou.setdefault(ou_id2name[ou_id], {}).setdefault(aff, []).append(uname)
    return users_ou
        

def process_users(affiliation, file):    
    known_dns = dict()
    
    for row in ac.list_accounts_by_type(affiliation=int(affiliation)):
        id = row['account_id']
        if not (a_id2auth.has_key(id) and a_id2auth[id][0]):
            # No username
            logger.warning("pu: No username found for account '%s'" % id)
            continue
        uname = a_id2auth[id][0]
        plain = "*notfound"
        md4 = "*notfound"
        ssha = "*notfound"
        if a_id2auth[id][1] is not None:
            plain = a_id2auth[id][1][int(co.auth_type_plaintext)]
            md4 = a_id2auth[id][1][int(co.auth_type_md4_nt)]
            ssha = a_id2auth[id][1][int(co.auth_type_ssha)]
        first = last = None
        if not a_id2p_id.has_key(id):
            logger.warning("No owner-ID and type for '%s'" % id)
            continue
        if a_id2p_id[id][0] == int(co.entity_person):
            p_names = p_id2name[a_id2p_id[id][1]]
            if not (p_names.get(int(co.name_first)) or \
                    p_names.get(int(co.name_last))):
                logger.warning("Names not found for '%s'" % id)
                continue
            first = p_names[int(co.name_first)]
            last = p_names[int(co.name_last)]
        else:
            logger.warning("Wrong owner-type for '%s'" % id)
            continue
        if not p_id2fnr.has_key(a_id2p_id[id][1]):
            logger.warning("Fnr not found for '%s'" % id)
            continue
        # Skip duplicates
        if known_dns.has_key(uname):
            continue
        else:
            known_dns[uname] = True
        
        u_uname = iso2utf(uname)
        dn = "cn=%s,cn=users,dc=ovgs,dc=no" % u_uname
        entry = {
            'givenname': (iso2utf(first),),
            'orcldefaultprofilegroup': ("cn=%s,cn=groups,dc=ovgs,dc=no"
                                        % const2str[int(affiliation)],),
            'orcltimezone': ("Europe/Oslo",),
            'objectclass': ("top", "person", "inetorgperson",
                            "organizationalperson", "orcluser", "orcluserv2"),
            'orclsamaccountname': (u_uname,),
            'sn': (iso2utf(last),),
            'uid': (u_uname,),
            'userpassword': ("{SSHA}%s" % ssha,),
            'ofkpassword': ("{MD4}%s" % md4,),
            'userpasswordct': (plain,),
            'fnr': (p_id2fnr[a_id2p_id[id][1]],)}
        if a_id2email.has_key(id):
            entry['mail'] = (a_id2email[id],)
        if p_id2cont.has_key(a_id2p_id[id][1]):
            entry['mobile'] = (p_id2cont[a_id2p_id[id][1]],)
        file.write(entry_string(dn, entry, False))
    return known_dns.keys()
        

def process_prof_group(name, users, file):

    file.write(entry_string(
        "cn=%s,cn=groups,dc=ovgs,dc=no" % name, {
        'objectclass': ("top", "groupOfUniqueNames", "orclGroup"),
        'displayname': (name,),
        'description': (name,),
        'uniquemember': ["cn=%s,cn=users,dc=ovgs,dc=no" % iso2utf(u)
                         for u in users]
        }, False))


def process_aff_groups(users, file):
    for ou, ou_aff in users.iteritems():
        u_ou = iso2utf(ou)
        for aff, aff_users in ou_aff.iteritems():
            name = "%s:%s" % (u_ou, const2str[int(aff)])
            dn = "cn=%s,cn=groups,dc=ovgs,dc=no" % (name)
            file.write(entry_string(dn, {
                'objectclass': ("top", "groupOfUniqueNames", "orclGroup"),
                'displayname': (name,),
                'description': (name,),
                'uniquemember': ["cn=%s,cn=users,dc=ovgs,dc=no" % iso2utf(u)
                                 for u in aff_users]}, False))
        # Make "pure" OU groups as well
        dn = "cn=%s,cn=groups,dc=ovgs,dc=no" % (u_ou)
        file.write(entry_string(dn, {
            'objectclass': ("top", "groupOfUniqueNames", "orclGroup"),
            'displayname': (u_ou,),
            'description': (u_ou,),
            'uniquemember': ["cn=%s,cn=users,dc=ovgs,dc=no" % iso2utf(u)
                             for aff_users in ou_aff.values()
                             for u in aff_users]}, False))


def process_groups(spread, file):
    g = Factory.get('Group')(db)
    for row in g.search(spread=int(spread)):
        id = row['group_id']
        u_name = iso2utf(row['name'])
        desc = row['description']
        g.clear()
        g.find(id)

        uniques = []
        members = g.list_members()[0]
        for type,a_id in members:
            if type == int(co.entity_account):
                if a_id2auth.has_key(a_id):
                    uniques.append("cn=%s,cn=users,dc=ovgs,dc=no"
                                   % iso2utf(a_id2auth[a_id][0]))
                else:
                    logger.warning("pg: No username found for: %s" % a_id)
                    continue
            else:
                logger.warning("Member not account: %s" % a_id)
                continue

        dn = "cn=%s,cn=groups,dc=ovgs,dc=no" % u_name
        file.write(entry_string(dn, {
            'description': (u_name,),
            'displayname': (u_name,),
            'objectclass': ("top", "groupOfUniqueNames", "orclGroup"),
            'uniquemember': uniques}, False))
        

def main():
    global db, co, ac, p, ou, et, logger

    logger = Factory.get_logger("cronjob")
    
    db = Factory.get('Database')()
    co = Factory.get('Constants')(db)
    ac = Factory.get('Account')(db)
    p = Factory.get('Person')(db)
    ou = Factory.get('OU')(db)
    et = Email.EmailTarget(db) 

    txt_path = "/cerebrum/dumps/txt"
    oid_path = "/cerebrum/dumps/OID"
    
    options, rest = getopt.getopt(sys.argv[1:],
                                  "o:t:",
                                  ["oid-path=", "txt-path="])
    for option, value in options:
        if option in ("-o", "--oid-path"):
            oid_path = value
        elif option in ("-t", "--txt-path"):
            txt_path = value

    # Load dicts with misc info.
    get_account_info()
    get_person_contact()

    # Dump OFK info 
    f = SimilarSizeWriter("%s/ofk.txt" % txt_path, "w")
    f.set_size_change_limit(10)
    users = process_txt_file(f)
    f.close()

    # Dump info about OU groups
    f = SimilarSizeWriter("%s/affiliation_groups_oid.ldif" % oid_path, "w")
    f.set_size_change_limit(10)
    process_aff_groups(users, f)
    f.close()

    # Dump info about users with co.affiliation_ansatt
    f = SimilarSizeWriter("%s/ans_user_oid.ldif" % oid_path, "w")
    f.set_size_change_limit(10)
    users = process_users(co.affiliation_ansatt, f)
    f.close()

    # Make a group out of these users
    f = SimilarSizeWriter("%s/ans_group_oid.ldif" % oid_path, "w")
    f.set_size_change_limit(10)
    process_prof_group("ANSATTE", users, f)
    f.close()

    # Dump info about users with co.affiliation_elev 
    f = SimilarSizeWriter("%s/elev_user_oid.ldif" % oid_path, "w")
    f.set_size_change_limit(10)
    users = process_users(co.affiliation_elev, f)
    f.close()
    
    # Make a group out of these users
    f = SimilarSizeWriter("%s/elev_group_oid.ldif" % oid_path, "w")
    f.set_size_change_limit(10)
    process_prof_group("ELEVER", users, f)
    f.close()

    # Dump info about users with co.affiliation_affiliate 
    f = SimilarSizeWriter("%s/tilk_user_oid.ldif" % oid_path, "w")
    f.set_size_change_limit(10)
    users = process_users(co.affiliation_tilknyttet, f)
    f.close()
    
    # Make a group out of these users
    f = SimilarSizeWriter("%s/tilk_group_oid.ldif" % oid_path, "w")
    f.set_size_change_limit(10)
    process_prof_group("TILKNYTTET", users, f)
    f.close()

            
    # Make and populate groups with spread spread_oid_grp
    f = SimilarSizeWriter("%s/group_oid.ldif" % oid_path, "w")
    f.set_size_change_limit(10)
    process_groups(co.spread_oid_grp, f)
    f.close()
    
if __name__ == '__main__':
    main()

# arch-tag: 75324f2e-70b6-11da-843e-cd5dc72a02e6
