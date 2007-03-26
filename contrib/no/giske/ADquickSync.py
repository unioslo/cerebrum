#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
# Copyright 2003 University of Oslo, Norway
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


import getopt, sys, pickle
import cerebrum_path
import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum import Entity
from Cerebrum.modules import MountHost
from Cerebrum.modules import ADutilMixIn
from Cerebrum.modules import CLHandler

db = Factory.get('Database')()
co = Factory.get('Constants')(db)
logger = Factory.get_logger("cronjob")


class ADquiSync(ADutilMixIn.ADuserUtil):

	def __init__(self, *args, **kwargs):

		super(ADquiSync, self).__init__(*args, **kwargs)
		self.cl = CLHandler.CLHandler(db)


	def quick_sync(self, spread, dry_run):

		answer = self.cl.get_events('ad', (self.co.account_password,))

		for ans in answer:
			if ans['change_type_id'] == self.co.account_password:

			   	pw = pickle.loads(ans['change_params'])['password']
				self.change_pw(ans['subject_entity'],spread, pw, dry_run)

			else:
				self.logger.debug("unknown change_type_id %i" % ans['change_type_id'])

		    #We always confirm event. Assume fullsync clean missed events.
			self.cl.confirm_event(ans)
        
		self.cl.commit_confirmations()    


	def change_pw(self, account_id, spread, pw, dry_run):

		self.ac.clear()
		self.ac.find(account_id)
		
		if self.ac.has_spread(spread):

			dn = self.server.findObject(self.ac.account_name)
			ret = self.run_cmd('bindObject', dry_run, dn)

			pwUnicode = unicode(pw, 'iso-8859-1')
			ret = self.run_cmd('setPassword', dry_run, pwUnicode)
			if ret[0]:
				self.logger.debug('Changed password: %s' % self.ac.account_name)
				return True
		else:
			#Account without ADspread, do nothing and return.
			return True

		#Something went wrong.
		self.logger.warn('Failed change password: %s' % self.ac.account_name)
		return False

            

def main():

	try:
		opts, args = getopt.getopt(sys.argv[1:],
					   '', ['user_spread=',
						'help',
						'dry_run'])

	except getopt.GetoptError:
		usage(1)

	delete_objects = False
	dry_run = False	
	
	for opt, val in opts:
		if opt == '--user_spread':
			user_spread = getattr(co, val)  # TODO: Need support in Util.py
		elif opt == '--help':
			usage(1)
		elif opt == '--dry_run':
			dry_run = True

	if not user_spread:
		user_spread = co.spread_ad_acc

	ADquickUser = ADquiSync(db, co, logger)	
	ADquickUser.quick_sync(user_spread, dry_run)

if __name__ == '__main__':
    main()
