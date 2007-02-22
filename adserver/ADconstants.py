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

class Constants(object):
	#Constants used with the AD sync.
	def __init__(self):
		#AD options
		self.AD_LDAP_ROOT = 'OU=Skoler,DC=cerebrum,DC=no'

		#Secure XMLRPC server options
		self.KEYFILE = 'c:\\temp\\server.pem'   # Your PEM formatted key file
		self.CERTFILE = 'c:\\temp\\server.pem'  # Your PEM certificate file
		self.LISTEN_HOST = ''
		self.LISTEN_PORT = 8000
		self.UNSECURE = False
		self.ACCESSLIST = ('129.240.14.46','158.36.190.36','129.240.2.126')
		#User in AD used to check basic HTML authentication.
		self.AUTH = 'cerebrum'
		#Must run under loglevel DEBUG or in DEBUG mode.
		self.LOGTRAFFIC = False

		#Logger options.
		self.loglevel = 'DEBUG'
		self.logformat = '%(asctime)s %(levelname)s %(message)s'
		self.logfilename = 'C:\\temp\\ADserver.log'
		self.logfilemode = 'a'


#Mixin class of imported modules needed for service to work.
import ADobject, ADhomedir
		
class MixIn(ADobject.Account, ADobject.Group, 
            ADobject.Search, ADhomedir.Homedir):
	
	def __init__(self, *args, **kwargs):
		super(MixIn, self).__init__(*args, **kwargs)
