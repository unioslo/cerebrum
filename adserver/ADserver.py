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

import win32com.client
import pythoncom
import logging
import SimpleXMLRPCServer
import SocketServer
import BaseHTTPServer
import socket, sys, getopt
import win32serviceutil
import win32service
import win32event
import base64
import traceback
from OpenSSL import SSL
import ADconstants

const = ADconstants.Constants()

#Starting logger.
loglevel = getattr(logging, const.loglevel)
logging.basicConfig(level = loglevel,	
		format = const.logformat,
		filename = const.logfilename,
		filemode = const.logfilemode)


class baseServer(ADconstants.MixIn):
	
	def __init__(self, *args, **kwargs):		
		super(baseServer, self).__init__(*args, **kwargs)

	def response(self, string):
		logging.debug('Received:%s' % string)
		return string

	def location(self):
		return win32com.client.GetObject('LDAP://rootDSE').Get("defaultNamingContext")


########################################
#
# SecureXMLRPCServer stuff under here.
#
#########################################

class SecureXMLRPCServer(BaseHTTPServer.HTTPServer,SimpleXMLRPCServer.SimpleXMLRPCDispatcher):
    def __init__(self, server_address, HandlerClass, logRequests=True):
        """Secure XML-RPC server.

        It it very similar to SimpleXMLRPCServer but it uses HTTPS for transporting XML data.
        """
        self.logRequests = logRequests

        SimpleXMLRPCServer.SimpleXMLRPCDispatcher.__init__(self)
        SocketServer.BaseServer.__init__(self, server_address, HandlerClass)
        ctx = SSL.Context(SSL.SSLv23_METHOD)
        ctx.use_privatekey_file (const.KEYFILE)
        ctx.use_certificate_file(const.CERTFILE)
        self.socket = SSL.Connection(ctx, socket.socket(self.address_family,
                                                        self.socket_type))
        self.server_bind()
        self.server_activate()

    def verify_request(self,request, client_address):
    	#overrides method in socket class, to check if request comes 
		#from valid ip.
        if client_address[0] in const.ACCESSLIST:
            return 1
        else:
	    print "Connection from %s refused." % client_address[0]
	    logging.warning("Connection from %s refused." % client_address[0])
            return 0


class SecureXMLRpcRequestHandler(SimpleXMLRPCServer.SimpleXMLRPCRequestHandler):
    """Secure XML-RPC request handler class.

       It it very similar to SimpleXMLRPCRequestHandler but it 
       uses HTTPS for transporting XML data.
    """
    def setup(self):
        self.connection = self.request
        self.rfile = socket._fileobject(self.request, "rb", self.rbufsize)
        self.wfile = socket._fileobject(self.request, "wb", self.wbufsize)
        
    def do_POST(self):
        """Handles the HTTPS POST request.

           It was copied out from SimpleXMLRPCServer.py and modified 
		   to shutdown the socket cleanly. In the Cerebrum installation 
		   functionality to handle basic HTTP Autorization is added.
        """

        try:
            # get arguments
            data = self.rfile.read(int(self.headers["content-length"]))
            if const.LOGTRAFFIC:
                print "RECEIVE:\n%s" % data
                logging.debug("RECEIVE:\n%s" % data)
			#Checking Authorization header, for authentication data.
            [user,pw] = \
                base64.b64decode(self.headers['Authorization'][6:]).split(':')

            if authenticateAD(user,pw):            
                # In previous versions of SimpleXMLRPCServer, _dispatch
                # could be overridden in this class, instead of in
                # SimpleXMLRPCDispatcher. To maintain backwards compatibility,
                # check to see if a subclass implements _dispatch and dispatch
                # using that method if present.
                response = self.server._marshaled_dispatch(
                        data, getattr(self, '_dispatch', None)
                    )
                if const.LOGTRAFFIC:
                    print "SEND:\n%s" % response
                    logging.debug("SEND:\n%s" % response)

        except RuntimeError:
            logging.critical("Autorization Failed for user: %s" % user)
            self.send_response(401)
            self.end_headers()			
        except: # This should only happen if the module is buggy
            # internal error, report as HTTP server error
            traceback.print_exc()
            logging.critical(traceback.format_exc())
            self.send_response(500)
            self.end_headers()
        else:
            # got a valid XML RPC response
            self.send_response(200)
            self.send_header("Content-type", "text/xml")
            self.send_header("Content-length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

            # shut down the connection
            self.wfile.flush()
            self.connection.shutdown() # Modified here!




####################################################
#
# Service things.
#
####################################################
class Service(win32serviceutil.ServiceFramework):
	_svc_name_ = 'Cerebrum'
	_svc_display_name_ = 'Cerebrum adsync'

	def __init__(self,args):
		win32serviceutil.ServiceFramework.__init__(self, args)
		self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)


	def SvcDoRun(self):
		import servicemanager
		#------------------------------------------------------
		# Make entry in the event log that this service started
		#------------------------------------------------------
		servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
		servicemanager.PYS_SERVICE_STARTED,(self._svc_name_, ''))

	        # Redirect stdout and stderr to prevent "IOError: [Errno 9] 
        	# Bad file descriptor". Windows services don't have functional
        	# output streams. 
		import win32traceutil
        	

		runServer()
		return


	def SvcStop(self):
		# Before we do anything, tell SCM we are starting the 
		# stop process.
		self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)

		# And set my event
		win32event.SetEvent(self.hWaitStop)
		return


def authenticateAD(Uname, Pword):

	ADS_SECURE_AUTHENTICATION = 1

	if Uname == const.AUTH:
		try:
			adsi = win32com.client.Dispatch('ADsNameSpaces')
			ldap = adsi.GetObject("","LDAP:")
			ldap.OpenDSObject('LDAP://%s' % const.AD_LDAP_ROOT, 
						  const.AUTH, Pword, ADS_SECURE_AUTHENTICATION)
		except:
			pass
		else:
			return True

		raise RuntimeError, "Authorization failed"
		return False


def runServer():


	adsiserver = baseServer()

	server_address = (const.LISTEN_HOST, const.LISTEN_PORT) 
    
	if const.UNSECURE:
		server = SimpleXMLRPCServer.SimpleXMLRPCServer(server_address)
	else:
		server = SecureXMLRPCServer(server_address, SecureXMLRpcRequestHandler)

	sa = server.socket.getsockname()
	server.register_instance(adsiserver)    

	if const.UNSECURE:
		print "Unsecure XMLRPC Server on", sa[0], "port", sa[1]
		logging.info("Unsecure XMLRPC Server on %s port %s" % (sa[0],sa[1]))
	else:
		print "Serving HTTPS on", sa[0], "port", sa[1]
		logging.info("Serving HTTPS on %s port %s" % (sa[0], sa[1]))

    #Go into the main listener loop
	#TODO:Start new thread so that the service interface still has control.
	try:
		server.serve_forever()
	finally:
		server.server_close()
    
	logging.info("Server EXITED")



def usage():
	print """Usage: 
	[--debug | --service [options] [install|remove|start|stop]]
	"""


def main():

		try:
			opts, args = getopt.getopt(sys.argv[1:], '',['debug','service','startup'])
		except getopt.GetoptError:
			usage()
			sys.exit()

		for opt, val in opts:
			if opt == '--debug':
				runServer()
			elif opt == '--service':
				sys.argv.remove('--service')
				#Giving control to the Pythonservice
				win32serviceutil.HandleCommandLine(Service)
			elif opt == '--startup':
				pass
			else:
				usage()	

if __name__ == '__main__':
	main()
