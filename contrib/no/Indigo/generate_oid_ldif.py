#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2005 University of Oslo, Norway
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

import cerebrum_path
import cereconf
from Cerebrum.Utils import Factory
from Cerebrum.Constants import _PersonAffStatusCode

def get_account_info():
    global uname2mailaddr, p_id2name, a_id2auth, a_id2owner, const2str
    
    uname2mailaddr = ac.getdict_uname2mailaddr()
    p_id2name = p.getdict_persons_names(source_system=co.system_cached,
                                        name_types=(co.name_first,co.name_last))
    a_id2auth = dict()
    for row in ac.list_account_authentication(auth_type=co.auth_type_md5_crypt):
        a_id2auth[int(row['account_id'])] = (row['entity_name'], row['auth_data'])

    a_id2owner = dict()
    for row in ac.list():
        a_id2owner[row['account_id']] = (int(row['owner_type']),
                                         row['owner_id'])

    const2str = dict()
    const2str[int(co.affiliation_ansatt)] = "cn=ANSATTE"
    const2str[int(co.affiliation_elev)] = "cn=ELEVER"
    
    


def process_users(affiliation, file):    

    known_dns = dict()
    
    for row in ac.list_accounts_by_type(affiliation=int(affiliation)):
        id = row['account_id']
        if not (a_id2auth.has_key(id) and a_id2auth[id][0]):
            # No username
            print "No username found for '%s'" % id
            continue
        uname = a_id2auth[id][0]
        if a_id2auth[id][1] is not None:
            pwd = a_id2auth[id][1]
        else:
            pwd = "*notfound"
        first = last = None
        if not a_id2owner.has_key(id):
            print "No owner-ID and type for '%s'" % id
            continue
        if a_id2owner[id][0] == int(co.entity_person):
            p_names = p_id2name[a_id2owner[id][1]]
            if not (p_names.get(int(co.name_first)) or \
                    p_names.get(int(co.name_last))):
                print "Names not found for '%s'" % id
                continue
            first = p_names[int(co.name_first)]
            last = p_names[int(co.name_last)]
        else:
            print "Wrong owner-type for '%s'" % id
            continue
        # Skip duplicates
        if known_dns.has_key(uname):
            continue
        else:
            known_dns[uname] = True
        
        txt = ["dn: cn=%s,cn=users,dc=ovgs,dc=no" % uname, 
               "givenname: %s" % first]
        if uname2mailaddr.has_key(uname):
            txt += ["mail: %s" % uname2mailaddr[uname]]
        txt += ["orcldefaultprofilegroup: %s,cn=groups,dc=ovgs,dc=no" % const2str[int(affiliation)], 
                "orcltimezone: Europe/Oslo", 
                "sn: %s" % last, 
                "uid: %s" % uname, 
                "userpassword: %s" % pwd,
                "\n"]
        file.write('\n'.join(txt))
    return known_dns.keys()
        

def process_prof_group(dn, users, file):

    txt = ["dn: cn=%s,cn=groups,dc=ovgs,dc=no" % dn,
           "objectclass: top",
           "objectclass: groupOfUniqueNames",
           "objectclass: orclGroup"]
    for u in users:
        txt += ["uniquemember: cn=%s,cn=users,dc=ovgs,dc=no" % u]
    file.write('\n'.join(txt))

def process_groups(spread, file):
    g = Factory.get('Group')(db)
    for row in g.search(spread=int(spread)):
        id = row['group_id']
        name = row['group_id']
        desc = row['description']
        g.clear()
        g.find(id)
        txt = ["dn: cn=%s,cn=groups,dc=ovgs,dc=no" % name,
               "description: %s" % desc,
               "displayname: %s" % desc,
               "objectclass: top",
               "objectclass: groupOfUniqueNames",
               "objectclass: orclGroup"]

        members = g.list_members()[0]
        for type,a_id in members:
            if type == int(co.entity_account):
                if a_id2auth.has_key(a_id):
                    txt += ["uniquemember: cn=%s,cn=users,dc=ovgs,dc=no" % a_id2auth[a_id][0]]
                else:
                    print "No username found for: %s" % a_id
                    continue
            else:
                print "Member not account: %s" % a_id
                continue
        txt += ["\n"]
        file.write('\n'.join(txt))
        

def main():
    global db, co, ac, p
    db = Factory.get('Database')()
    co = Factory.get('Constants')(db)
    ac = Factory.get('Account')(db)
    p = Factory.get('Person')(db)

    # Load dicts with misc info.
    get_account_info()

    # Dump info about users with co.affiliation_ansatt
    f = open("ans_user_oid.ldif", 'w')
    users = process_users(co.affiliation_ansatt, f)
    f.close()

    # Make a group out of these users
    f = open("ans_group_oid.ldif", 'w')
    process_prof_group("ANSATTE", users, f)
    f.close()

    # Dump info about users with co.affiliation_elev    
    f = open("elev_user_oid.ldif", 'w')
    users = process_users(co.affiliation_elev, f)
    f.close()
    
    # Make a group out of these users
    f = open("elev_group_oid.ldif", 'w')
    process_prof_group("ELEVER", users, f)
    f.close()
            
    # Make and populate groups with spread spread_oid_grp
    f = open("group_oid.ldif", 'w')
    process_groups(co.spread_oid_grp, f)
    f.close()
    
if __name__ == '__main__':
    main()
