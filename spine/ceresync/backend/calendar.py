# -*- coding: latin-1 -*-

# -*- coding: iso-8859-1 -*-

# Copyright 2008 University of Oslo, Norway
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

"""Calendar-backend. Talking to both LDAP and Oracle Calendar. """

import os
import ldap
from ldap import modlist
from ceresync import config
from errors import ServerError
from backend.ldap import LdapBack

class CalendarUser(LdapBack):
    """LDIF-representation of an Oracle Calendar Account.
    When using Oracle Calendar with Oracle Internet Directory we can configure
    OC to auto-provision Calendar Accounts with notify-events sent from OID.
    """
    def __init__(self,base=config.sync.get("ldap","calendar_base")):
        self.base = base
        self.filter = config.sync.get("ldap","calendarfilter")
        self.obj_class = ['inetOrgPerson','shadowAccount','ctCalUser']

    def _caladd(self,dn,node):
        _cmd = 'uniuser -user -add "%s" -n %s"' % (dn,node)
        os.system(_cmd)
        return

    def _caldeactivate(self,dn,node):
        _cmd = 'uniuser -user -mod "%s" -m "ENABLE=FALSE" -n %s"' % (dn,node)
        os.system(_cmd)
        return

    def _get_node(self,obj):
        """Returns a given node.. a default or a student/employee-node
        Make it configurable.
        """
        return 23

    def delete(self,obj):
        """Deactivate the CalendarObject.. no actual delete is done.
        """
        dn = self.get_dn(obj)
        node = self._get_node(obj)
        self._caldeactivate(dn,node)
        return
            

    def add(self,obj,update_if_exists=True):
        # First search LDAP if user exists
        dn = self.get_dn(obj)
        ldif = self.get_attributes(obj)
        node = self._get_node(obj)
        res = []
        try:
            res = self.search(dn,ldap.SCOPE_BASE,"objectclass=*")
            if len(res) == 1:
                dn,ldif = res[0]
            if ldif.has_key("ctCalxItemId") and update_if_exists:
                self.update(obj)
            elif ldif.has_key("ctCalUser"):
                # User has LDAP-user, but not Calendar-user
                self._caladd(dn,node)
        except ldap.NO_SUCH_OBJECT:
            attrs = modlist.addModlist(ldif)
            self.l.add_s(dn,attrs)
            self._caladd(dn,node)
        return

    def update(self,obj,add_if_missing=True):
        # First search LDAP if user exists
        dn = self.get_dn(obj)
        new = self.get_attributes(obj)
        node = self._get_node(obj)
        res = []
        try:
            res = self.search(dn,ldap.SCOPE_BASE,"objectclass=*")
            if len(res) == 1:
                dn,old = res
        except ldap.NO_SUCH_OBJECT:
            self.add(obj)
            return
        if old == new:
            return
        else:
            self.update(obj)
        return

    def get_attributes(self,obj):
        # Do not care about password - we use Kerberos for Calendar
        s = {}
        s['o']           = ["%s" % config.sync.get("calendar","acronym")]
        s['uid']         = ["%s" % obj.name]
        s['cn']          = ["%s" %  self.iso2utf(obj.full_name)]
        # Presume last name in full_name is surname
        s['sn']          = ["%s" %  self.iso2utf(obj.full_name.split()[len(obj.full_name)-1])]
        s['objectClass'] = self.obj_class
        s['description'] = ["%s" % obj.description]
        # Need to provide these attributes in the struct first
        # s['mail'] = obj.mail
        # s['ou'] = obj.orgunits
        # s['title'] = obj.title
        return s

