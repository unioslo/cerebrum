# -*- coding: iso-8859-1 -*-
# Copyright 2004 University of Oslo, Norway
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

import random
from Cerebrum.Entity import EntityName
from Cerebrum import Account
from Cerebrum import Errors
from Cerebrum.modules import Email


class AccountHiSTMixin(Email.AccountEmailMixin):
    """Delete an account, does not handle group memberships""" 
    def delete(self):
        for s in self.get_account_types():
          self.del_account_type(s['ou_id'], s['affiliation'])
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=account_authentication]
        WHERE account_id=:acc_id""", {'acc_id' : self.entity_id})
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=account_home]
        WHERE account_id=:acc_id""", {'acc_id' : self.entity_id})
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=account_type]
        WHERE account_id=:acc_id""", {'acc_id' : self.entity_id})
        self.execute("""  
        DELETE FROM [:table schema=cerebrum name=account_info] 
        WHERE account_id=:acc_id""", {'acc_id' : self.entity_id})
        self.__super.delete()
     
    def add_spread(self, spread):
	#
	# Because the EmailAccountMixin doesn't add EmailServerTarget
	# and thereby no email address we need to do it ourselves.

        state = {}
	if spread == self.const.spread_HiST_Hist_epost:
            est = Email.EmailServerTarget(self._db)
            try:
                est.find_by_entity(self.entity_id)
                state['email_server_id'] = est.email_server_id
            except Errors.NotFoundError:
                pass

	# If it's not about email the standard stuff seems to be ok
        ret = self.__super.add_spread(spread)

	if spread == self.const.spread_HiST_Hist_epost:
            est = self._HiST_update_email_server(
                self.const.email_server_type_shist)
	
	 
     
    def _HiST_update_email_server(self, server_type):
        est = Email.EmailServerTarget(self._db) 
        es = Email.EmailServer(self._db) 
        old_server = srv_id = None 
        try:
            est.find_by_entity(self.entity_id) 
            old_server = est.email_server_id 
            es.find(est.email_server_id) 
            if es.email_server_type == server_type:
                # All is well
                print "All well" 
                return est 
	except Errors.NotFoundError: 
            pass
       
        # Choose a server..
        if old_server is None:
            srvlist = es.list_email_server_ext()
	    for svr in srvlist:
                if svr['server_type'] == server_type:
		    srv_id = svr['server_id']
                try:
                    et = Email.EmailTarget(self._db)
                    et.find_by_email_target_attrs(entity_id = self.entity_id)
                except Errors.NotFoundError:
                    et.clear()
                    et.populate(self.const.email_target_account,
                                self.entity_id,
                                self.const.entity_account)
                    et.write_db()
            if srv_id == None:
                raise RuntimeError, "srv_id is not set."
            est.clear()
	    est.populate(srv_id, parent = et)
            est.write_db()
	else:
	    est.populate(srv_id)
        return est   
 

  
    def make_passwd(self, uname):
        vowels = 'aeiouyAEIOUY'
	consonants = 'bdghjlmnpqrstvwxzBDGHJLMNPQRSTVWXZ0123456789'
	r = ''
	alt = random.randint(0, 1)
	while len(r) < 8:
    	  if alt is 1:
            r += consonants[random.randint(0, len(consonants)-1)]
            alt = 0;
          else:
            r += vowels[random.randint(0, len(vowels)-1)]
            alt = 1;
        return r


    def validate_new_uname(self, domain, uname):
        """Check that the requested username is legal and free"""
        try:
            # We instantiate EntityName directly because find_by_name
            # calls self.find() whose result may depend on the class
            # of self
            lc_name = uname.lower()
            en = EntityName(self._db)
            en.find_by_name(lc_name, domain)
            return False
        except Errors.NotFoundError:
            if lc_name == uname:
              return True
            else:
              return False

