# -*- coding: iso-8859-1 -*-

# Copyright 2003, 2004 University of Oslo, Norway
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
Uit specific extension to access a simple role source system

We need something now!
Refine later....

"""
import os
import sys
import time

import cerebrum_path
import cereconf

from Cerebrum import Database
from Cerebrum.Utils import Factory, AtomicFileWriter
from Cerebrum.extlib import xmlprinter


db = None

TODAY=time.strftime("%Y%m%d")
sys_y_default_file = os.path.join(cereconf.DUMPDIR,
                                  'sysY','sysY_%s.xml' % (TODAY))


class SystemY:


    def __init__(self,output_file):

        items = self.list_roles()
        stream = AtomicFileWriter(output_file, "w")
        writer = xmlprinter.xmlprinter(stream,
                                       indent_level = 2,
                                       data_mode = True,
                                       input_encoding = "latin1")
        self.write_roles(writer, items)
        stream.close()

        pass

    def list_role_types(self):
        pass

    def list_role_members(self,role):
        pass

    def _rolefilter(self,rolename):

        excluded_roles = ['administrator']
        if rolename in excluded_roles:
            return True
        if rolename.endswith('_admin'):
            return True

        return False
        

    def list_roles(self,):

        items = []

        sql = """
        SELECT  u.uname,gg.gname
        FROM grp_group gg
             JOIN grp_member gm ON gm.gid=gg.gid
             JOIN users u on gm.uid=u.uid
        """

        rows  = db.query(sql)
        
        for r in rows:
            if not self._rolefilter(r['gname']):
                items.append({ 'uname': r['uname'], 'gname': r['gname']})

##         items = [{'uname':'pde000','gname':'sut-itadmins'},
##                  {'uname':'ajo008','gname':'orakel'},
##                  {'uname':'ksc000','gname':'medfak-itadmins'},
##                  {'uname':'bto001','gname':'ita-admins'},
##                  {'uname':'rbe000','gname':'nfh-itadmins'},
##                  {'uname':'kso000','gname':'medfak-itadmins'},
##                  {'uname':'rbe001','gname':'medfak-itadmins'},
##                  {'uname':'mwr000','gname':'nfh-itadmins'},
##                  {'uname':'rbu000','gname':'nfh-itadmins'}
##                  ]

                 
        return items


    def write_roles(self,writer,items):
        xml_data = {}
        for data in items:
            current = xml_data.get(data['gname'])
            if (current):
                xml_data[data['gname']].append(data['uname'])
            else:
                xml_data[data['gname']] = [data['uname']]
        keys = xml_data.keys()
        keys.sort()
        
        writer.startDocument(encoding = "iso8859-1")
        writer.startElement("roles")
        for data in keys:
            admin = 'no'
            if data.find('admin') >= 0:
                admin = 'yes'
            writer.startElement("role", { "name" : data, "admin": admin })
            list = xml_data.get(data)
            for x in list:
                writer.dataElement("member", x)
            writer.endElement("role")

        writer.endElement("roles")
        writer.endDocument()



def try_connect():
    global db
    user = cereconf.SYS_Y['db_user']
    service = cereconf.SYS_Y['db_service']
    host = cereconf.SYS_Y['db_host']
    try:
        db = Database.connect(user=user, service=service, host=host,
                              DB_driver='PsycoPG')
    except Exception,m:
        print "Failed to connect to %s@%s. Reason:%s" % (service,host,m)
        sys.exit(1)
        
    
def main():
    try_connect()
    work = SystemY(sys_y_default_file)


if __name__ == '__main__':
    main()
