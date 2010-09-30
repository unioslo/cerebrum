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

from soaplib.service import DefinitionBase

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

    #
    # Hooks, nice for logging etc.
    def on_method_call(self, environ, method_name, py_params, soap_params):
        """
        Called BEFORE the service implementing the functionality is called
        @param the wsgi environment
        @param the method name
        @param the body element of the soap request
        @param the tuple of python params being passed to the method
        @param the soap elements for each params
        """
        print "Call method %s with params %s" % (method_name, py_params)

    def on_method_return(self, environ, py_results, soap_results,
                         http_resp_headers):
        """
        Called AFTER the service implementing the functionality is called
        @param the wsgi environment
        @param the python results from the method
        @param the xml element containing the return value(s) from the method
        @param http response headers as a dict of strings
        """
        pass
        
        
    def on_method_exception_object(self, environ, exc):
        '''
        Called BEFORE the exception is serialized, when an error occurs durring
        execution
        @param the wsgi environment
        @param the exception object
        '''
        pass

    def on_method_exception_xml(self, environ, fault_xml):
        '''
        Called AFTER the exception is serialized, when an error occurs durring
        execution
        @param the wsgi environment
        @param the xml element containing the exception object serialized to a
        soap fault
        '''
        pass

    def call_wrapper(self, call, params):
        '''
        Called in place of the original method call.
        @param the original method call
        @param the arguments to the call
        '''
        return call(*params)
