#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2010 University of Oslo, Norway
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

#from soaplib.service import soapmethod
#from soaplib.serializers.primitive import String, Integer, Array, Boolean
from soaplib.wsgi_soap import SimpleWSGISoapApp

#from twisted.web.server import Site
#from twisted.web.resource import Resource
#from twisted.web.wsgi import WSGIResource
#from twisted.internet import reactor
from twisted.python.log import err

"""
This class provides the core functionality for SOAP services running
in the CIS framework. CIS is based on the twisted framework and
soaplib.

...
"""

class BasicSoapServer(SimpleWSGISoapApp):
    """
    Base class for SOAP services.

    This class defines general setup useful for SOAP services.
    No SOAP actions are defined here. Define the actions in subclasses.
    """

    #
    # Hooks, nice for logging etc.
    def onCall(self, environ):
        """This is the first method called when this WSGI app is invoked"""
        print "Calling SOAP server from address %s" % environ['REMOTE_ADDR']
    
    def onWsdl(self, environ, wsdl):
        """This is called when a wsdl is requested"""
        pass
    
    def onWsdlException(self, environ, exc, resp):
        """Called when an exception occurs durring wsdl generation"""
        err(exc, 'wsdl generation failed') 
    
    def onMethodExec(self, environ, body, py_params, soap_params):
        """Called BEFORE the service implementing the functionality is called"""
        pass
        
    
    def onResults(self, environ,py_results, soap_results):
        """Called AFTER the service implementing the functionality is called"""
        pass
        
    def onException(self, environ, exc, resp):
        """Called when an error occurs durring execution"""
        err(exc, 'An exception occured: %s' % resp)
    
    def onReturn(self, environ, returnString):
        """Called before the application returns"""
        pass

