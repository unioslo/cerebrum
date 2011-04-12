#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2010, 2011 University of Oslo, Norway
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

from lxml import etree
from soaplib.core.service import DefinitionBase

"""
This class provides the core functionality for SOAP services running
in the CIS framework. CIS is based on the twisted framework and
soaplib.

...
"""

class BasicSoapServer(DefinitionBase):
    """
    Base class for SOAP services.

    This class defines general setup useful for SOAP services.
    No SOAP actions are defined here. Define the actions in subclasses.
    """

    # Hooks, nice for logging etc.

    def on_method_call(self, method_name, py_params, soap_params):
        '''Called BEFORE the service implementing the functionality is called

        @param the method name
        @param the tuple of python params being passed to the method
        @param the soap elements for each argument
        '''
        print "Calling method %s(%s)" % (method_name, ', '.join(py_params))

    def on_method_return_object(self, py_results):
        '''Called AFTER the service implementing the functionality is called,
        with native return object as argument
        
        @param the python results from the method
        '''
        pass

    def on_method_return_xml(self, soap_results):
        '''Called AFTER the service implementing the functionality is called,
        with native return object serialized to Element objects as argument.
        
        @param the xml element containing the return value(s) from the method
        '''
        pass

    def on_method_exception_object(self, exc):
        '''Called BEFORE the exception is serialized, when an error occurs
        during execution.
    
        @param the exception object
        '''
        pass

    def on_method_exception_xml(self, fault_xml):
        '''Called AFTER the exception is serialized, when an error occurs
        during execution.
        
        @param the xml element containing the exception object serialized to a
        soap fault
        '''
        msg = "Exception occured: "
        for el in fault_xml.iter('faultstring'):
            msg += el.text
        print msg
        

    def call_wrapper(self, call, params):
        '''Called in place of the original method call.

        @param the original method call
        @param the arguments to the call
        '''
        return call(*params)


#
# Hack of WSGI/soaplib to support sessions.
#
# Since the WSGI doesn't define any specific support for sessions and cookies we
# need to hack it into soaplib's wsgi support. It is a bad hack, as it might
# crash the server by later soaplib upgrades. This is why it is all put last in
# this file, so it can be easier to locate and change it when problems occur.
#
# To use the hack, you would need to use these subclasses in the server setup.
# Example code:
#
#    import SoapListener
#
#    service = Application([IndividuationServer], 'tns')
#    # instead of wsgi.Application(service):
#    wsgi_app = SoapListener.WSGIApplication(service) 
#
#    # instead of WSGIResource(reactor, ..., wsgi_app):
#    resource = SoapListener.WSGIResourceSession(reactor,
#                               reactor.getThreadPool(), wsgi_application)
#
# If you do not put in these lines in your server setup, the soap server will be
# unaffected by this hack, but you wouldn't have session-support.
#
from soaplib.core.server import wsgi
from twisted.web.server import NOT_DONE_YET
from twisted.web.wsgi import WSGIResource, _WSGIResponse
from twisted.python import log

class WSGIApplication(wsgi.Application):
    def on_wsgi_call(self, req_env):
        """Using the hook to give the current session to every service in the
        application. This is a hack, as we tighten the coupling to CIS. CIS
        should be able to handle no defined sessions here.
        """
        for service in self.app.services:
            service.session = req_env.get('cis.session', None)

class WSGIResourceSession(WSGIResource):
    def render(self, request):
        """We are changing the default behaviour by calling our subclass of
        _WSGIResponse, so we can include the session to environ.
        
        We can't call the method's super() here, so we have to copy-paste in the
        super method's code."""
        response = _WSGIResponse(self._reactor, self._threadpool,
                                 self._application, request)
        if request.method == 'POST':
            response.environ['cis.session'] = request.getSession()
            log.msg("DEBUG: session id = %s" % request.getSession().uid)
        # The service can be reached at self._application.app.services[0] - are
        # there other ways of giving IndividuationServer the session?
        response.start()
        return NOT_DONE_YET
