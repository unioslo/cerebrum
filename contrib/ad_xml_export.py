#!/usr/bin/env python2.2
# -*- coding: iso-8859-1 -*-
#
# Copyright 2002, 2003 University of Oslo, Norway
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
import time
import string
import re

import cerebrum_path
import cereconf
from Cerebrum import Constants
from Cerebrum import Errors
from Cerebrum import OU
from Cerebrum import Account
from Cerebrum import Group
from Cerebrum import Entity
from Cerebrum.Utils import Factory
from Cerebrum.modules import CLHandler
import nwutils



db = Factory.get('Database')()
const = Factory.get('CLConstants')(db)
co = Factory.get('Constants')(db)
ou = OU.OU(db)
ent_name = Entity.EntityName(db)

global f, dbg_level, spread_id, user_cache

f = None
user_cache = {}

dbg_level = -1
NONE = 0
ERROR = 1
WARN = 2
INFO = 3
DEBUG = 4


def dbg_print(lvl, str):
    if dbg_level >= lvl:
        print str



def escape_xml_attr(a):
    """Escapes XML attributes.  Expected input format is iso-8859-1"""
    a = str(a).replace('&', "&amp;")
    a = a.replace('"', "&quot;")
    a = a.replace('<', "&lt;")
    a = a.replace('>', "&gt;")
    # http://www.w3.org/TR/1998/REC-xml-19980210.html#NT-Char
    # x9 | #xA | #xD | [#x20-#xD7FF] | [#xE000-#xFFFD] |
    # [#x10000-#x10FFFF] /* any Unicode character, excluding the
    # surrogate blocks, FFFE, and FFFF. */
    a = re.sub('[^\x09\x0a\x0d\x20-\xff]', '.', a)
    return '"%s"' % a


def xml_dump(spread_str):
    spread_id = int(getattr(co, spread_str))
    f.write("<?xml version=\"1.0\" encoding=\"ISO8859-1\"?>\n")
    f.write("<spread_data>\n")
    do_ous()
    do_users(spread_id)
    f.write("</spread_data>\n")



def do_ous():
    #Will not delete OUs only create new ones.
    OUs = []
   
    def find_children(parent_id,parent_acro):

        ou.clear()
        ou.find(parent_id)
        chldrn = ou.list_children(co.perspective_fs)

        for child in chldrn:
            name=parent_acro
            ou.clear()
            ou.find(child['ou_id'])
            if ou.acronym:
                name = 'ou=%s,%s' % (ou.acronym, parent_acro)
                if not name in OUs:
    		    f.write("<OU>\n")
                    write_ou(name)
                    f.write("</OU>\n")
            chldrn = ou.list_children(co.perspective_fs)
            find_children(child['ou_id'], name)
        
    ou.clear()
    root_id = cereconf.NW_CERE_ROOT_OU_ID # ou.root()
    children = find_children(root_id, cereconf.NW_LDAP_ROOT)
 


def write_ou(name):
    f.write("\t\t<add name = \"%s\"/>\n" % name)



def do_users(spread_id):
    account = Account.Account(db)
    group = Group.Group(db)
    namespace = int(co.account_namespace)
    for row in ent_name.list_all_with_spread(spread_id):
        id = row['entity_id']
        ent_name.clear()
        ent_name.find(id)
        if ent_name.entity_type != int(co.entity_account): continue
        account.clear()
        account.find(id)
        (user_dn, attrs) = nwutils.get_account_dict(id, spread_id)
        # Split user_dn i loginname og ou
        (foo, ou_dn) = user_dn.split(",", 1)
        login_name = ent_name.get_name(co.account_namespace)
	f.write("<user account_id=\"%d\">" % id)
        write_user(login_name, ou_dn, attrs)
        user_cache[id] = user_dn
    	f.write("</user>\n")


def do_groups(spread_id):
    group = Group.Group(db)
    namespace = int(co.account_namespace)
    f.write("<group>\n")
    for row in ent_name.list_all_with_spread(spread_id):
        id = row['entity_id']
        ent_name.clear()
        ent_name.find(id)
        if ent_name.entity_type != int(co.entity_group): continue
        f.write("<add>\n")
    
        group.clear()
        group.find(id)
        for mem in group.get_members():
            if user_cache.has_key(mem):
                f.write("<group member = %s/>" % user_cache[id])
    f.write("</group>\n")


def write_user(login_name, ou_dn, attrs):
        f.write("\t<add ")
        f.write("login_name=\"%s\" " % login_name)
        f.write("OU=\"%s\" " % ou_dn)
        for item in attrs:
            f.write("%s=%s " % (item, unicode(escape_xml_attr(attrs[item]), 'utf-8').encode('iso-8859-1')) )
#		f.write("%s=\"%s\" " % (item, attrs[item]) )
        f.write("/>\n")
        


def usage(exitcode=0):
    print """Usage: ad_xml_export.py -s spread -f outfile"""
    sys.exit(exitcode)



def main():
    global f
    spread = filename = None
    try:
        opts, args = getopt.getopt(sys.argv[1:], 's:f:d:', ['help'])
    except getopt.GetoptError:
        usage(1)

    if args:
        usage(1)
    for opt, val in opts:
        if opt == '--help':
            usage()
        elif opt == '-s':
            spread_str = val
        elif opt == '-f':
            filename = val
        elif opt == '-d':
            dbg_level = val
    if spread is not None or filename is not None:
        f = file(filename, 'w')
        dbg_print(INFO, 'INFO: AD XML export starting at %s' % nwutils.now())
        xml_dump(spread_str)
        dbg_print(INFO, 'INFO: AD XML export done at %s' % nwutils.now())
    else:
        usage(1);
    
    
        
        
if __name__ == '__main__':
    main()
