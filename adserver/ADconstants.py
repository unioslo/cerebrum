
#Constants used with the AD sync.


class Constants(object):

	def __init__(self):
		#AD options
		self.AD_LDAP_ROOT = 'DC=cerebrum,DC=no'

		#Secure XMLRPC server options
		self.KEYFILE = 'c:\\temp\\server.pem'   # Your PEM formatted key file
		self.CERTFILE = 'c:\\temp\\server.pem'  # Your PEM certificate file
		self.LISTEN_HOST = 'dctest'
		self.LISTEN_PORT = 8000
		self.UNSECURE = False
		self.ACCESSLIST = ('129.240.2.126')

		#Logger options.
		self.loglevel = 'DEBUG'
		self.logformat = '%(asctime)s %(levelname)s %(message)s'
		self.logfilename = '/temp/ADserver.log'
		self.logfilemode = 'a'

		
