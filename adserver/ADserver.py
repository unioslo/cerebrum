import win32com.client
import pythoncom
import logging
import SimpleXMLRPCServer
import SocketServer
import BaseHTTPServer
import SimpleHTTPServer
import socket, os, sys, getopt
from OpenSSL import SSL

import win32serviceutil
import win32service
import win32event

import Constants
from ADObject import Account
from ADObject import Group
from ADObject import Search

const = Constants.Constants()

#Starting logger.
loglevel = getattr(logging, const.loglevel)
logging.basicConfig(level = loglevel,	
		format = const.logformat,
		filename = const.logfilename,
		filemode = const.logfilemode)


class Server(Search):
	
	def __init__(self):
		pass

	def getvalue(self, klasse, attr):
		#Overrides the values in the Objects presented by XMLRPC.
		return getattr(getattr(self,klasse) , value)


	def setvalue(self, klasse, attr, value):
		#Overrides the values in the Objects presented by XMLRPC.
		setattr(getattr(self, klasse) , attr , value)
		return 1


	def runmethod(self, klass, deff, param1=None, param2=None):
		newobj = getattr(getattr(self, klass), deff)
		if param1 == None:
			return newobj()
		elif param2 == None:
			return newobj(param1)	
		else:
			return newobj(param1, param2)


	def response(self,string):
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

    It it very similar to SimpleXMLRPCRequestHandler but it uses HTTPS for transporting XML data.
    """
    def setup(self):
        self.connection = self.request
        self.rfile = socket._fileobject(self.request, "rb", self.rbufsize)
        self.wfile = socket._fileobject(self.request, "wb", self.wbufsize)
        
    def do_POST(self):
        """Handles the HTTPS POST request.

        It was copied out from SimpleXMLRPCServer.py and modified to shutdown the socket cleanly.
        """

        try:
            # get arguments
            data = self.rfile.read(int(self.headers["content-length"]))
            # In previous versions of SimpleXMLRPCServer, _dispatch
            # could be overridden in this class, instead of in
            # SimpleXMLRPCDispatcher. To maintain backwards compatibility,
            # check to see if a subclass implements _dispatch and dispatch
            # using that method if present.
            response = self.server._marshaled_dispatch(
                    data, getattr(self, '_dispatch', None)
                )
        except: # This should only happen if the module is buggy
            # internal error, report as HTTP server error
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

		runServer()
		return


	def SvcStop(self):
		# Before we do anything, tell SCM we are starting the 
		# stop process.
		self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)

		# And set my event
		win32event.SetEvent(self.hWaitStop)
		return


def runServer():

	adsiserver = Server()
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

    #Initializing values for server, initializing in __init__ do not work
    #across xmlrpc.  	
	adsiserver._setFilter()
	adsiserver._init_values()	
	
    #Go into the main listener loop
	try:
		server.serve_forever()
	finally:
		server.server_close()
    
	logging.info("Server EXITED")



def usage():
	print """Usage: [options]
	--debug|--service
	"""


def main():

	if sys.argv[1] == '--debug':
		#Running in debug mode.
		try:
			opts, args = getopt.getopt(sys.argv[1:], '',['debug'])
		except getopt.GetoptError:
			usage()
			sys.exit()

		for opt, val in opts:
			if opt == '--debug':
				runServer()

	else:
		#Giving control to the Pythonservice
		win32serviceutil.HandleCommandLine(Service)			


if __name__ == '__main__':
	main()
