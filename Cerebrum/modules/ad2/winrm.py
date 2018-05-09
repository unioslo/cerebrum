#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2012-2018 University of Oslo, Norway
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
"""Client functionality for making use of Windows Remote Management (WinRM).

WinRM is a protocol for communicating with Windows machines (servers) to get
and set differents kinds of information. WinRM is Microsoft's version of WSMan,
which is based on SOAP and uses different WS-* standards.

Our focus is to use WinRM to execute commands on the server side, which we then
could use to administrate Active Directory (AD).

The WinRM server has to be set up properly before we could connect to it.

For more information about the WinRM standard, see:

    http://msdn.microsoft.com/en-us/library/aa384426.aspx
    http://msdn.microsoft.com/en-us/library/cc251526(v=prot.10).aspx

"""

import base64
import io
import json
import logging
import random
import re
import socket
import urllib2

import six
from lxml import etree

from Cerebrum.Utils import unicode2str

logger = logging.getLogger(__name__)

# The namespaces that might be used in the SOAP envelopes, for the server to be
# happy. This is the namespaces that are used in Microsoft's documentation.
namespaces = {
    # WS-man configuration:
    'cfg':   "http://schemas.microsoft.com/wbem/wsman/1/config",
    'rsp':   "http://schemas.microsoft.com/wbem/wsman/1/windows/shell",
    # Standard SOAP definition:
    's':     "http://www.w3.org/2003/05/soap-envelope",
    # WS-Addressing:
    'wsa':   "http://schemas.xmlsoap.org/ws/2004/08/addressing",
    # WS-Management:
    'wsman': "http://schemas.dmtf.org/wbem/wsman/1/wsman.xsd",
    # WS-Enumeration:
    'wsen':  "http://schemas.xmlsoap.org/ws/2004/09/enumeration",
    'wsmid': "http://schemas.dmtf.org/wbem/wsman/identity/1/wsmanidentity.xsd",
    # Standard XML definition. Must be present to be able to use e.g. xml:lang:
    'xml':   "http://www.w3.org/XML/1998/namespace",
}

"""What WinRS action types that is available for the server."""
action_types = {
    # Executing a command:
    'command': 'http://schemas.microsoft.com/wbem/wsman/1/windows/shell/Command',
    # Creating a shell
    'create':  'http://schemas.xmlsoap.org/ws/2004/09/transfer/Create',
    # Deleting a shell
    'delete':  'http://schemas.xmlsoap.org/ws/2004/09/transfer/Delete',
    # Retrieve list of information, e.g. listeners or certificates
    'enumerate': 'http://schemas.xmlsoap.org/ws/2004/09/enumeration/Enumerate',
    # Get information, e.g. config
    'get': 'http://schemas.xmlsoap.org/ws/2004/09/transfer/Get',
    # Pull information from the server
    'pull': 'http://schemas.xmlsoap.org/ws/2004/09/enumeration/Pull',
    # Receive output from a shell
    'receive': 'http://schemas.microsoft.com/wbem/wsman/1/windows/shell/Receive',
    # Send input to stdin
    'send': 'http://schemas.microsoft.com/wbem/wsman/1/windows/shell/Send',
    # Send a signal to a shell, e.g. 'terminate' or 'ctrl_c'
    'signal':  'http://schemas.microsoft.com/wbem/wsman/1/windows/shell/Signal',
}


class WinRMException(Exception):
    """Generic exception for any WinRM errors.

    This should be the superclass for all the various exceptions when
    communicating with WinRM, whether it is Powershell or AD that syas no.

    """
    pass


class WinRMServerException(WinRMException):
    """Exception for HTTP 500 Server Errors. WinRM's standard way of saying that
    something failed, and it's either an unknown error or something the client
    have done.

    """
    def __init__(self, code, reason, details=None):
        super(WinRMServerException, self).__init__(code, reason, details)
        self.code = code
        self.reason = reason
        self.details = details


class WinRMAuthenticationException(WinRMException):
    """Exception for if the mutual authentication fails.

    We are creating our own exception type for this, to avoid the problem that
    python2.5 does not have the ssl module. By using this exception, we could
    use it for 2.5 and newer versions.

    There are many scenarios that could go wrong in the authentication process:

    - The server is not registered with a certificate at all.

    - The server's certificate is not signed by any CA certificate we have
      registered as authoritative for this use.

    - The hostname in the server's certificate is not the same as the URL that
      we connect to.

    - The client is not registered with a proper certificate.

    - The client's certificate is not accepted by the server.

    """
    pass


class ExitCodeException(WinRMException):
    """This is raised when a command returns an exitcode that is not 0.

    All commands sent through WinRM returns with an exitcode. Only 0 is
    considered as success, other values are considered as errors. The value
    could say something about what failed for the command, but the meaning of
    the exitcode value differs from command to command.

    """
    def __init__(self, exitcode, stderr, output=None, msg=None):
        """Initiate exception for command with exitcode other than 0.

        @type exitcode: int or string
        @param exitcode: The command's exitcode.

        @type stderr: string
        @param stderr: The stderr message for the command.

        @type output: dict
        @param output: All output from the command. It might include the stderr
            output too, even if that must be present in the L{stderr} argument.

        @type msg: string
        @param msg: If you want to specify the message that is printed for the
            exception. Defaults to a generic "command failed" message.

        """
        self.exitcode = exitcode
        self.stderr = stderr
        self.output = output
        if msg is None:
            msg = 'Command failed: exitcode: %s, stderr: %s' % (exitcode,
                                                                stderr)
        super(ExitCodeException, self).__init__(msg)


class PowershellException(ExitCodeException):
    """Exception that tells you that some powershell code failed.

    Works exactly like ExitCodeException, but is created to differentiate
    between cmd code and powershell code.

    Examples on what could trigger such exceptions:
     - Syntax error in the powershell code we send.
     - A command failed, for example if we tried to create a new user object
       which already existed.

    """
    def __init__(self, exitcode, stderr, output=None, msg=None):
        """Initiate exception for command with exitcode other than 0.

        :type exitcode: int or string
        :param exitcode: The command's exitcode.

        :type stderr: string
        :param stderr: The stderr message for the command.

        :type output: dict
        :param output: All output from the command. It might include the stderr
            output too, even if that must be present in the L{stderr} argument.

        :type msg: string
        :param msg: If you want to specify the message that is printed for the
            exception. Defaults to a generic "command failed" message.

        """
        self.exitcode = exitcode
        self.output = output
        self.stderr = stderr

        # Search for, and attempt to extract error-information from PowerShell
        # error-messages.
        if stderr:
            m = re.search(
                "(?P<first_error>[\w\s\-'.]+)[+\s]+CategoryInfo[\s:]+"
                "(?P<second_error>\w+):\s+\("
                "(?P<args>[\w\-:]+)\)\s+\["
                "(?P<command>[\w\s-]+)\].*",
                stderr,
                re.MULTILINE)
        else:
            m = None
        if msg is not None:
            r_msg = msg
        elif m:
            gd = m.groupdict()
            cmd = re.sub('\s', '', gd.get('command'))
            first_err = gd.get('first_error').strip()
            #  Fix empty argument sequence
            args = gd.get('args') if gd.get('args') != ':' else ''
            second_err = gd.get('second_error')

            # We'll differentiate between how we report errors. Exception
            # information seems to be pattern matchable, but the error message
            # is not always defined in the same place.
            r_msg = ("Command '%s' called with args '%s' "
                     "returned exit code %s: %s" % (
                         cmd, args, exitcode, first_err or second_err))
        # Default error representation
        else:
            r_msg = 'Command failed: exitcode: %s, stderr: %s' % (exitcode,
                                                                  stderr)

        super(PowershellException, self).__init__(exitcode,
                                                  stderr,
                                                  output=self.output,
                                                  msg=r_msg)


class WinRMProtocol(object):
    """The basic protocol for sending correctly formatted SOAP-data to the WinRM
    server. Methods for sending different call types, like Get, Execute and
    Send, are available, but more advanced functionality should not be put in
    this class. This is only for basic functionality to be used in different
    ways. The ShellId is for example only returned from the server, but how to
    use it should be done by subclasses.

    If we need to support more WinRM call types, you should add them as new
    methods in this class.

    """

    # The default ports for encrypted [0] and unencrypted [1] communication:
    _default_ports = (5986, 5985)

    # Timeout in seconds for trying to connect to the server. Controls the
    # socket timeout:
    connection_timeout = 1800

    # Timeout in seconds for waiting for replies from the server. This is
    # handled by the WinRM server, returning a Fault when this many seconds
    # have passed.
    request_timeout = 60 * 5  # 5 minutes

    # How many seconds a Shell is set to last before the server automatically
    # deletes it. If set to low, a long fullsync might not succeed. Set too
    # high, and you would not be able to reconnect before the timeout has
    # passed if many of previous syncs have failed.
    #
    #   Lifetime: An optional quota setting that configures the maximum time,
    #   in seconds, that the Remote Shell will stay open. The time interval is
    #   measured beginning from the time that the service receives a wst:Create
    #   request for a Remote Shell.
    #                   - http://msdn.microsoft.com/en-us/library/cc251546.aspx
    #
    shell_lifetime = 10  # 60*10 = 10 minutes

    # The string that identifies this client in HTTP calls
    _useragent = 'Cerebrum WinRM client'

    # Encoding
    #
    # The _winrm_encoding and _winrm_codepage must be configured to the same
    # charset. See
    # <http://msdn.microsoft.com/en-us/library/windows/desktop/dd317756%28v=vs.85%29.aspx>
    # for mappings between codepage and encoding.
    _winrm_encoding = 'utf-8'
    _winrm_codepage = '65001'

    def __init__(self, host='localhost', port=None, encrypted=True,
                 logger=None, ca=None, client_key=None, client_cert=None,
                 check_name=True):
        """Set up the basic configuration. Fill the HTTP headers and set the
        correct port if not given.

        @type host: string
        @param host: The hostname

        @type port: string or int
        @param port:
            The port to use. Defaults to integers in L{self._default_ports},
            5986 for encrypted and 5985 for unencrypted communication.

        @type encrypted: bool
        @param encrypted: If the communication should go encrypted. It should!

        @type logger: CerebrumLogger
        @param logger: Cerebrum's logger to log to.

        @type ca: string
        @param ca:
            The absolute location of a file with the CA certificate that should
            be signing the server certificate. TODO: should we accept the
            server certificate itself as well?

        @type client_key: string
        @param client_key:
            The absolute location of a file with the client's private key for
            use with client authentication. The client key and cert could be in
            the same file.

        @type client_cert: string
        @param client_cert:
            The absolute location of a file with the client's (signed)
            certificate to be used with client authentication.

        @type check_name: boolean
        @param check_name: Enable hostname validation (if encrypted).

        """
        # TODO: How should we handle no logger?
        self.logger = logger
        self.host = host
        self.encrypted = bool(encrypted)
        if not self.encrypted:
            self.logger.warn("Unencrypted communication with WinRM")
        if port:
            self.port = port
        else:
            self.port = self._default_ports[0]
            if not self.encrypted:
                self.port = self._default_ports[1]
        if encrypted:
            from Cerebrum import https

            ssl_config = https.SSLConfig()
            ssl_config.set_ssl_version(https.SSLConfig.TLSv1)

            if ca is None:
                # No certificate validation!
                ssl_config.set_ca_validate(https.SSLConfig.NONE)
            else:
                ssl_config.set_ca_chain(ca)
                ssl_config.set_ca_validate(https.SSLConfig.REQUIRED)
                ssl_config.set_verify_hostname(check_name)

            if client_cert or client_key:
                ssl_config.set_cert(client_cert, client_key)

            self.logger.debug("Connection settings: timeout=%r, ssl=%s",
                              self.connection_timeout, ssl_config)

            conn = https.HTTPSConnection.configure(
                ssl_config, timeout=self.connection_timeout)
            self._opener = urllib2.build_opener(
                https.HTTPSHandler(ssl_connection=conn))
        else:
            socket.setdefaulttimeout(self.connection_timeout)
            self._opener = urllib2.build_opener()
        self._http_headers = {
            'Host': '%s:%s' % (self.host, self.port),
            'Accept': '*/*',
            'Content-Type': 'application/soap+xml; charset={}'.format(
                self._winrm_encoding),
            'User-Agent': self._useragent}
        # Set up the XML parser to expect input in utf-8
        # TODO: Do we need this? The xml documents *should* contain encoding.
        self.xmlparser = etree.XMLParser(encoding=self._winrm_encoding)
        self.logger.debug("WinRMProtocol: init done")

    def _http_url(self, sub=''):
        """Return a string with the HTTP URL of the service."""
        proto = 'http'
        if self.encrypted:
            proto = 'https'
        if not sub.startswith('/'):
            sub = '/%s' % sub
        return '%s://%s:%s%s' % (proto, self.host, self.port, sub)

    def add_credentials(self, username, password):
        """Set the credentials to give to the server for authentication."""
        self._username = username
        self._password = password
        cred = base64.encodestring('%s:%s' % (username, password)).strip()
        self._http_headers['Authorization'] = "Basic %s" % cred

    def _http_call(self, xml, address='/wsman'):
        """Send an HTTP call with the given XML-data to the WinRM server.

        Send a call to the server. The given message should be a string or
        instance with XML data to be sent. The returned object is an urllib2
        response instance. Interesting variables are ret.headers and ret.fp.

        @type xml: lxml.etree.ElementTree
        @param xml: The XML that should be sent to the server. Should be valid
            SOAP data that the server could understand.

        @type address: string
        @param address: The HTTP address to where the data should go on the
            server. The WinRM specification gives '/wsman' as the default, but
            other addresses could be used for separate behaviour, e.g.
            '/wsman-anon/identify' for identifying servers (from the WSMan
            spec).

        @rtype: urllib2 responce instance
        @return: An instance with returned data. Interesting attributes are
            ret.headers, ret.fp and ret.code.

        @raise WinRMServerException: For HTTP 500 Server Errors. Used by WinRM
            together with a Fault message.

        @raise urllib2.HTTPError: When other, unhandled errors arrive.

        @raise urllib2.URLError: When the server connection fails.

        @raise socket.timeout: When the socket connection times out.

        """
        xml = self._xml_render(xml)
        req = urllib2.Request(
            self._http_url(address).encode(self._winrm_encoding),
            xml,
            self._http_headers)
        try:
            ret = self._opener.open(req)
        except urllib2.HTTPError, e:
            if e.code == 401:  # Unauthorized
                self.logger.debug("Server says 401 Unauthorized")
                self.logger.warn("No known server auth method: %s" %
                                 e.hdrs.get('www-authenticate', None))
                raise
            elif e.code == 500:
                code, reason, detail = self._parse_fault(e)
                raise WinRMServerException(code, reason, detail)
            self.logger.warn("Server http error, code=%r: %s", e.code, e.msg)
            self.logger.warn("Server headers: %s",
                             str(e.hdrs).replace('\r\n', ' | '))
            raise
        except socket.timeout as e:
            self.logger.warn("Socket timeout when connecting to %s: %s",
                             self._http_url('wsman'), e)
            raise
        except urllib2.URLError as e:
            self.logger.warn("Connection error: %s", e.reason)
            raise
        return ret

    def _parse_fault(self, fp):
        """Parse a response from the server for a fault message.

        Faults from WinRM contains:

        - Fault code (list of strings): A human semi-readable code pointing to
          where something has failed, formatted in string. Consists of a
          "primary" code and could also contain subcode(s). Returned in the
          order of appearance, supposedly.

        - Reason (list of strings): An short explanation of the error.

        - Detail (list of mixed content): More details about the error. This
          contains more data, and could give you more help about fixing the
          fault:

            - Code (int): Could be an internal Win32 error code or an
              application specific code. Search for MS-ERREF to get a list of
              standard codes.

            - Machine (string): The machine where the fault occured.

            - Message (mixed content) [optional]: Different data that gives
              more details about the fault.

        Example on the format of a Fault response:

        <s:Envelope xml:lang="en-US"
                    xmlns:s="http://www.w3.org/2003/05/soap-envelope"
                    xmlns:a="http://schemas.xmlsoap.org/ws/2004/08/addressing"
                    xmlns:x="http://schemas.xmlsoap.org/ws/2004/09/transfer"
                    xmlns:e="http://schemas.xmlsoap.org/ws/2004/08/eventing"
                    xmlns:n="http://schemas.xmlsoap.org/ws/2004/09/enumeration"
                    xmlns:w="http://schemas.dmtf.org/wbem/wsman/1/wsman.xsd"
                    xmlns:p="http://schemas.microsoft.com/wbem/wsman/1/wsman.xsd">
        <s:Header>
          <a:Action>
            http://schemas.dmtf.org/wbem/wsman/1/wsman/fault
          </a:Action>
          <a:MessageID>uuid:C7B5ECDB-BA3D-42D5-956A-09F386821B2C</a:MessageID>
          <a:To>http://schemas.xmlsoap.org/ws/2004/08/addressing/role/anonymous</a:To>
          <a:RelatesTo>uuid:ABABABAB-58905844435185278054</a:RelatesTo>
        </s:Header>
        <s:Body>
          <s:Fault>
            <s:Code>
              <s:Value>s:Sender</s:Value>
              <s:Subcode>
                <s:Value>w:QuotaLimit</s:Value>
              </s:Subcode>
            </s:Code>
            <s:Reason>
              <s:Text xml:lang="">
                The WS-Management service cannot process the request. The
                maximum number of concurrent shells for this user has been
                exceeded. Close existing shells or raise the quota for this
                user.
              </s:Text>
            </s:Reason>
            <s:Detail>
              <f:WSManFault xmlns:f="http://schemas.microsoft.com/wbem/wsman/1/wsmanfault"
                            Code="2150859173"
                            Machine="localhost">
                <f:Message>
                    The WS-Management service cannot process the request. This
                    user is allowed a maximum number of 5 concurrent shells,
                    which has been exceeded. Close existing shells or raise the
                    quota for this user.
                </f:Message>
              </f:WSManFault>
            </s:Detail>
          </s:Fault>
        </s:Body>
        </s:Envelope>

        """
        codes = []
        reason = []
        details = []
        tag = '{%s}Fault' % namespaces['s']
        for event, elem in etree.iterparse(fp, tag=tag):
            for elecode in elem.iter(tag='{%s}Code' % namespaces['s']):
                valuetag = '{%s}Value' % namespaces['s']
                codes.extend(ele.text for ele in elecode.iter(tag=valuetag))
            for elereas in elem.iter(tag='{%s}Reason' % namespaces['s']):
                reason.extend(r.text for r in elereas.iterchildren())
            details.extend(elem.iter(tag='{%s}Detail' % namespaces['s']))
        return codes, reason, tuple(etree.tostring(e, pretty_print=True)
                                    for e in details)

    def _xml_duration(self, seconds=None, minutes=None, hours=None):
        """Return a duration in the defined XML Duration time format.

        I've skipped days, months and years, but could be added if we need it
        in the future.

        In the documentation at http://www.w3.org/TR/xmlschema-2/#duration, it
        says:

            PnYn MnDTnH nMnS, where nY represents the number of years, nM the
            number of months, nD the number of days, 'T' is the date/time
            separator, nH the number of hours, nM the number of minutes and nS
            the number of seconds. The number of seconds can include decimal
            digits to arbitrary precision.

        Examples:

            120 seconds -> PT120S or PT120.000S
            2 minutes -> PT2M
            3 days and 2 hours -> P3DT2H

        """
        ret = ['PT']
        if hours:
            ret.append('%dH' % hours)
        if minutes:
            ret.append('%dM' % minutes)
        if seconds:
            ret.append('%.3fS' % seconds)
        return ''.join(ret)

    # XML generating

    def _xml_envelope(self, header, body=None):
        """Create the base SOAP element, an s:Envelope with given header and
        body. If body is not given, an empty <s:Body/> will be created instead.

        The envelope would look like:

            <s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
                        xmlns:a="http://schemas.xmlsoap.org/ws/2004/08/addressing"
                        xmlns:wsman="http://schemas.dmtf.org/wbem/wsman/1/wsman.xsd"
                        ...>
                <s:Header>
                    ...
                </s:Header>
                <s:Body>
                    ...
                </s:Body>
            </s:Envelope>

        As you can see, the XML specifications are put in the envelope. The
        Header and Body should exist, but at least the Body could be empty
        (e.g.  <s:Body/>).

        @type header: etree._Element
        @param header: An XML Element that should be tagged s:Header.

        @type body: etree._Element
        @param body: An XML Element that should be tagged s:Body. If no body is
            given, an empty element, <s:Body/>, is created. Some requests don't
            need data in the body.

        @rtype: etree._Element
        @return: An XML Element tagged as s:Envelope, which contains the Header
            and Body elements.

        """
        env = self._xml_element('Envelope', 's', nsmap=namespaces)
        env.append(header)
        if body is None:
            body = self._xml_element('Body', 's')
        env.append(body)
        return env

    def _xml_element(self, name, ns_prefix=None, attribs={}, text=None,
                     nsmap=None):
        """Create a single XML element, tagged by the given name and namespace.

        @type name: string
        @param name: The name/tag of the new element: <Name/>

        @type ns_prefix: string
        @param ns_prefix: The namespace shortcut that the element should be
            created in. The shortcut has to be defined in L{winrs.namespaces}.
            Example: <ns_prefix:Name/>

        @type attribs: dict
        @param attribs: A dict of all attributes that should be set for the
            element. Example: <Element attrib1="value1"/>

        @type text: string
        @param text: If the element should contain text, this could be added
           here. It could later be added by:: ele.text = 'text'. If the element
           should contain sub elements, they could instead be added by::
           ele.append(subele).

        @type nsmap: dict
        @param nsmap: The namespace mapping that should be used by the new
           element. It is given directly to etree._Element for further
           processing. Only needed when some special namespaces should be used,
           otherwise the parent's namespaces are used.

        @rtype: etree._Element
        @return: A new etree XML Element.

        """
        tag = name
        if len(ns_prefix) > 0:
            tag = '{%s}%s' % (namespaces[ns_prefix], name)

        # Rewrite the attribs if they use shortcut prefixes, as ElementTree
        # demands the full definition URLs, e.g.
        #   s:mustUnderstand -> {https://w3.org...}mustUnderstand:
        for name, attrib in attribs.copy().iteritems():
            names = name.split(':', 1)
            if len(names) > 1:
                attribs['{%s}%s' % (namespaces[names[0]], names[1])] = attrib
                del attribs[name]
        ele = etree.Element(tag, attribs, nsmap=nsmap)
        if text is not None:
            ele.text = text
        return ele

    def _xml_header(self, action, resource='windows/shell/cmd', selectors=None):
        """Create an XML header for different request types. WinRM makes use of
        a lot of different WS-* standards, e.g. WS-Addressing and
        WS-Management, but most of the WSMan calls looks fortunately the same.
        The Header returned from this method could therefore contain most of
        those settings.

        Some of the elements that are used:

        - wsa:Action: The action type to request for. See L{action_types}.

        - wsa:MessageID: A random string with a unique Id of this message.

        - wsa:ReplyTo: wsa:Address: Who should get the reply. Only set to
          anonymous, as we get the reply through the HTTP reply.

        - wsa:To: Addressing to whom the request is for. This is since the
          requests for WinRM are not bound to TCP.

        - wsman:Locale: Specify language to use in replies and faults. Default:
          en-US.

        - wsman:MaxEnvelopeSize: The max size of the reply message. If the
          reply gets bigger than this, the message gets split up in different
          envelopes. Must be a multiple of 1024.

        - wsman:OperationTimeout: Set how long the request could run before it
          gets timed out. This is only for the connection to the server, it
          does not override the max lifetime for the user's shells.

        - wsman:OptionSet: Options for the environment on the server, e.g. if
          the user profile should be used or not, and how piping input should
          work.

        - wsman:ResourceURI: An URL to a defined resource that should be used
          for the requests. The default is a 'cmd' shell, but it is possible to
          create custom shells. If the resource doesn't start with 'http' it
          will be set up with a prefix of:

            http://schemas.microsoft.com/wbem/wsman/1/

        - wsman:Selector: Selectors, which depens on the given type of action.
          Could for instance be wsman:ShellId for Command and Send, or the name
          of the information to retrieve through Get. Not required for all
          commands.

        Example on how a header could look like:

        <s:Header>
          <wsa:To>http://localhost:5985/wsman</wsa:To>
          <wsman:ResourceURI s:mustUnderstand="true">
            http://schemas.microsoft.com/wbem/wsman/1/windows/shell/cmd
          </wsman:ResourceURI>
          <wsa:ReplyTo>
            <wsa:Address s:mustUnderstand="true">
              http://schemas.xmlsoap.org/ws/2004/08/addressing/role/anonymous
            </wsa:Address>
          </wsa:ReplyTo>
          <wsa:Action s:mustUnderstand="true">
            http://schemas.xmlsoap.org/ws/2004/09/transfer/Create
          </wsa:Action>
          <wsman:MaxEnvelopeSize s:mustUnderstand="true">
            153600</wsman:MaxEnvelopeSize>
          <wsa:MessageID>uuid:AF6A2E07-BA33-496E-8AFA-E77D241A2F2F</wsa:MessageID>
          <wsman:Locale xml:lang="en-US" s:mustUnderstand="false" />
          <!-- The OptionSet is not always used
          <wsman:OptionSet xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
            <wsman:Option Name="WINRS_NOPROFILE">TRUE</wsman:Option>
            <wsman:Option Name="WINRS_CODEPAGE">437</wsman:Option>
          </wsman:OptionSet>
          <wsman:OperationTimeout>PT60.000S</wsman:OperationTimeout>
        </s:Header>

        @type action: String
        @param action: The type of wsa:Action to send in the request. See
            L{Cerebrum.modules.ad2.winrm.action_types} for defined actions.
            Examples are 'command', 'create', 'send' and 'delete'.

        @type resource: String
        @param resource: The ResourceURI as specified in wsman:ResourceURI.
            Used differently for the various action types, some types doesn't
            even use it. If the URI doesn't start with 'http' it will be set up
            with a prefix of:

                http://schemas.microsoft.com/wbem/wsman/1/

            Examples of resources could be 'windows/shell/cmd' when working
            with standard shells, 'config' at Get requests for getting the
            server configuration and
            'http://schemas.microsoft.com/wbem/wsman/1/config/plugin' for
            getting list of plugins.

        @rtype: etree._Element
        @return: An s:Header element with the proper settings to be
            understood by the WinRM server.

        """
        header = self._xml_element('Header', 's')
        header.append(self._xml_element('To', 'wsa',
                                        text=self._http_url('wsman')))
        reply = self._xml_element('ReplyTo', 'wsa')
        addr = self._xml_element('Address', 'wsa',
                                 attribs={'s:mustUnderstand': 'true'})
        addr.text = 'http://schemas.xmlsoap.org/ws/2004/08/addressing/role/anonymous'
        reply.append(addr)
        header.append(reply)

        if not resource.startswith('http'):
            resource = 'http://schemas.microsoft.com/wbem/wsman/1/%s' % resource
            # http://schemas.microsoft.com/wbem/wsman/1/windows/shell/cmd

        uri = self._xml_element(
            'ResourceURI', 'wsman',
            # text='http://schemas.microsoft.com/powershell/microsoft.powershell',
            # text='http://schemas.microsoft.com/wbem/wsman/1/%s' % resource,
            text=resource,
            attribs={'s:mustUnderstand': 'true'})
        header.append(uri)

        act = self._xml_element('Action', 'wsa', text=action_types[action],
                                attribs={'s:mustUnderstand': 'true'})
        header.append(act)

        size = self._xml_element('MaxEnvelopeSize', 'wsman', text='3073741824',
                                 attribs={'s:mustUnderstand': 'true'})
        header.append(size)

        msgid = self._xml_element('MessageID', 'wsa')
        # TODO: Do we need a better randomizer for this?
        msgid.text = ('uuid:ABABABAB-' + ''.join(str(random.randint(0, 9))
                                                 for i in xrange(30)))
        header.append(msgid)
        header.append(self._xml_element('Locale', 'wsman',
                                        attribs={'xml:lang': 'en-US',
                                                 's:mustUnderstand': 'false'}))
        header.append(self._xml_element('OperationTimeout', 'wsman',
                                        text=self._xml_duration(
                                            self.request_timeout)))

        # Add Selector, if given. E.g. used for specifying ShellId.
        if selectors:
            selectorset = self._xml_element('SelectorSet', 'wsman')
            for s in selectors:
                selectorset.append(s)
            header.append(selectorset)
        return header

    def _xml_render(self, root_element):
        root = etree.ElementTree(root_element)
        xml_buffer = io.BytesIO()
        root.write(xml_buffer,
                   encoding=self._winrm_encoding,
                   xml_declaration=True)
        return xml_buffer.getvalue()

    # Settings for the WinRM behaviour:

    # WINRS_CONSOLEMODE_STDIN: If input from wsman_send should go directly
    # to the console (True) or through pipes (False). The purpose is to support
    # input through stdin to a command. Note that we have trouble sending stdin
    # to Powershell 2.0, so we have to set this to True to avoid that a command
    # hangs, waiting for input that we can't send. This might be fixed in later
    # Powershell versions.
    _winrs_consolemode_stdin = True

    # WINRS_SKIP_CMD_SHELL: If a command that is sent to WinRS should be
    # executed inside of cmd.exe (False), or not (True). If not, the first
    # argument must be an absolute path to an executable file to run, e.g.
    # powershell.exe. Note that CMD has a limit on the input length of the
    # command, which is 8191 (http://support.microsoft.com/kb/830473), and you
    # will in addition need to escape strings both for CMD and for Powershell,
    # if that is used.
    _winrs_skip_cmd_shell = True

    # Commands that are defined by the WSMan and WinRM standards:

    def wsman_command(self, shellid, *args):
        """Send a Command request to the server, to execute the given
        command(s).

        Commands are run in the given Shell, so you have to have set this up
        first. The specification allows you to send an empty command, to clean
        up temporary locks.

        Example on SOAP XML for sending a command:

        <s:Body>
          <rsp:CommandLine
            xmlns:rsp="http://schemas.microsoft.com/wbem/wsman/1/windows/shell">
            <rsp:Command>del</rsp:Command>
            <rsp:Arguments>/p</rsp:Arguments>
            <rsp:Arguments>d:\temp\out.txt</rsp:Arguments>
          </rsp:CommandLine>
        </s:Body>

        @type shellid: string
        @param shellid: The ShellId that the given command(s) should run in.

        @type args: string or list of strings
        @param args: The code that should be sent to the WinRM server. It could
            be a single command, a command with parameters or many commands
            that should all be executed. All the strings are simply sent to the
            server, so they need to be valid code.

            The input must be in Unicode.

        @rtype: string
        @return: The CommandId that is returned from the server. This could be
            used in a Receive request to get the output from the command, but
            you are allowed to do something else before getting the output.

        @raise: TODO:
            If something failed and no CommandId was returned from the server.
            TODO

        """
        selector = self._xml_element('Selector', 'wsman', text=shellid,
                                     attribs={'Name': 'ShellId'})
        header = self._xml_header('command', selectors=[selector])
        options = self._xml_element('OptionSet', 'wsman')
        consolemode_stdin = 'FALSE'
        if self._winrs_consolemode_stdin:
            consolemode_stdin = 'TRUE'
        skip_cmd_shell = 'FALSE'
        if self._winrs_skip_cmd_shell:
            skip_cmd_shell = 'TRUE'
        options.append(
            self._xml_element('Option', 'wsman',
                              attribs={'Name': 'WINRS_CONSOLEMODE_STDIN'},
                              text=consolemode_stdin))
        options.append(
            self._xml_element('Option', 'wsman',
                              attribs={'Name': 'WINRS_SKIP_CMD_SHELL'},
                               text=skip_cmd_shell))
        header.append(options)

        body = self._xml_element('Body', 's')
        cmdline = self._xml_element('CommandLine', 'rsp')
        body.append(cmdline)

        # To support sending blank commands:
        if not args:
            args = [None]

        # TODO: Decode input if not unicode?
        #args = tuple(unicode2str(a) for a in args)

        cmd = self._xml_element('Command', 'rsp', text=args[0])
        cmdline.append(cmd)
        for a in args[1:]:
            cmdline.append(self._xml_element('Arguments', 'rsp', text=a))

        self.logger.debug5('Calling WSMAN Command for ShellId "%s" with args '
                           '"%s"' % (str(shellid), str(args)))
        ret = self._http_call(self._xml_envelope(header, body))
        self.logger.debug5('WSMAN Command done for ShellId "%s"' %
                           str(shellid))
        tag = '{%s}CommandId' % namespaces['rsp']
        for event, elem in etree.iterparse(ret.fp, tag=tag):
            return elem.text
        raise Exception('Did not receive CommandID')

    def wsman_create(self):
        """Send a Create request to the server, asking it to create a new Shell.

        The shell could later be used to execute commands.

        Example on how a Create request looks like (inside s:Body):

        <s:Header>
          ...
          <wsman:OptionSet
              xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
            <wsman:Option Name="WINRS_NOPROFILE">TRUE</wsman:Option>
            <wsman:Option Name="WINRS_CODEPAGE">437</wsman:Option>
          </wsman:OptionSet>
          ...
        </s:Header>
        <s:Body>
          <rsp:Shell
              xmlns:rsp="http://schemas.microsoft.com/wbem/wsman/1/windows/shell">
            <rsp:Environment>
                <rsp:Variable Name="test">1</rsp:Variable>
            </rsp:Environment>
            <rsp:WorkingDirectory>d:\windows</rsp:WorkingDirectory>
            <rsp:Lifetime>PT1000.000S</rsp:Lifetime>
            <rsp:InputStreams>stdin</rsp:InputStreams>
            <rsp:OutputStreams>stdout stderr</rsp:OutputStreams>
          </rsp:Shell>
        </s:Body>

        TODO: Make some input configurable.

        @rtype: string
        @return: The ShellId that identifies the newly created Shell. This
            should be used further to execute commands inside the Shell.

        @raise: TODO
            If a ShellId is not returned.
            TODO

        """
        header = self._xml_header('create')
        # TODO: add support for environment variables as input
        # env = self._xml_element('Environment', 'rsp')
        # env.append(self._xml_element('Variable', 'rsp',
        #                              attribs={'Name': 'Mode'},
        #                              text="1000, 1000"))
        # header.append(env)
        options = self._xml_element('OptionSet', 'wsman')
        # We don't need a profile for now, will only take longer execution time
        options.append(self._xml_element('Option', 'wsman', text='TRUE',
                                         attribs={'Name': 'WINRS_NOPROFILE'}))
        # The codepage sets what encoding to use for output. For more info, see
        # http://msdn.microsoft.com/en-us/library/windows/desktop/dd317756%28v=vs.85%29.aspx
        options.append(self._xml_element('Option', 'wsman',
                                         text=self._winrm_codepage,
                                         attribs={'Name': 'WINRS_CODEPAGE'}))
        header.append(options)

        body = self._xml_element('Body', 's')
        shell = self._xml_element('Shell', 'rsp', nsmap={
            'rsp': 'http://schemas.microsoft.com/wbem/wsman/1/windows/shell'})
        shell.append(self._xml_element('Lifetime', 'rsp',
                                       text=self._xml_duration(
                                           self.shell_lifetime)))
        shell.append(self._xml_element('InputStreams', 'rsp', text='stdin'))
        shell.append(self._xml_element('OutputStreams', 'rsp',
                                       text='stdout stderr'))
        body.append(shell)

        self.logger.debug3('Calling WSMAN Create')
        ret = self._http_call(self._xml_envelope(header, body))

        # Find the ShellID:
        for event, elem in etree.iterparse(
                ret.fp,
                tag='{http://schemas.dmtf.org/wbem/wsman/1/wsman.xsd}Selector'):
            self.logger.debug3('WSMAN Create done, returned ShellId %s',
                               elem.text)
            return elem.text
        raise Exception('Did not receive ShellId from server')

    def wsman_delete(self, shellid):
        """Send a Delete request to the server, to terminate the Shell by the
        given ShellId.

        It is recommended to delete the shell when a job has finished, to free
        up usage on the server. Only a limited number of shells are available
        per user, and old shells could stay idle for quite some time before
        they get deleted, depending on the settings.

        """
        selector = self._xml_element('Selector', 'wsman', text=shellid,
                                     attribs={'Name': 'ShellId'})
        self.logger.debug3('Calling WSMAN Delete for ShellId "%s"' %
                           str(shellid))
        self._http_call(
            self._xml_envelope(
                self._xml_header('delete', selectors=[selector])))
        self.logger.debug3('WSMAN Delete done for ShellId "%s"' % str(shellid))
        # No need to parse the reply, exceptions are thrown by HTTP error codes
        # and raised by _http_call
        return True

    def wsman_enumerate(self, resource='config', selector=None):
        """Send an Enumerate request to the server, to get a list of specified
        information.

        Example on how how an enumeration message looks like in the Body:

            <wsen:Enumerate>
                <!-- Where to send EnumerationEnd messages if unexpectedly
                     terminated. Is optional. -->
                <wsen:EndTo>endpoint-reference</wsen:EndTo> ?
                <!-- For how long until timeout. If not specified, set to
                     infinite, which might not be accepted by the endpoint -->
                <wsen:Expires>[xs:dateTime | xs:duration]</wsen:Expires>
                <wsen:Filter Dialect="xs:anyURI"> xs:any </wsen:Filter>
            </wsen:Enumerate>

        @type resource: string
        @param resource: The resource identifier (URI) of what information to
            enumerate. It should either start with http or be relative to:

                http://schemas.microsoft.com/wbem/wsman/1/

            Examples on valid resources:

                'config'
                'windows/shell'

        @type selector: dict
        @param selector: The parameters of a selector for the enumerate
            request. Should be a dict which contains the attributes of the
            selector. Some usable attribute names:
                - Name: The name of the selector, used to target what to select
                - text: The value of the selection.

        @rtype: string
        @return:
            The Id of the EnumerateResponse. This should be used to get the
            output from the enumerate request through L{wsman_pull}. You might
            want to do something else while waiting, as it might take a while
            to process, depending on what you requested.

        """
        sel = None
        if selector:
            s_txt = ''
            if 'text' in selector:
                s_txt = selector['text']
                del selector['text']
            sel = [self._xml_element('Selector', 'wsman', text=s_txt,
                                     attribs=selector)]
        header = self._xml_header('enumerate',
                                  resource=resource,
                                  selectors=sel)
        body = self._xml_element('Body', 's')
        enum = self._xml_element('Enumerate', 'wsen')
        # enum.append(self._xml_element(
        #     'Expires', 'wsen', text='%s' % self._xml_duration(seconds=120)))
        body.append(enum)

        # print etree.tostring(self._xml_envelope(header, body), pretty_print=True)
        self.logger.debug3('Calling WSMAN Enumerate for resource "%s"',
                           resource)
        ret = self._http_call(self._xml_envelope(header, body))
        tag = '{%s}EnumerationContext' % namespaces['wsen']
        for event, elem in etree.iterparse(ret.fp, tag=tag):
            self.logger.debug3('WSMAN Enumerate done for resource "%s"',
                               resource)
            return elem.text
        raise Exception("Unknown Enumeration response for resource='%s'" %
                        resource)

    def wsman_get(self, resource='config', selector=None):
        """Send a Get request to the server, to get specified information.

        @type resource: string
        @param resource: The type of information to get. Could start with http,
            or it could be relative to:

                http://schemas.microsoft.com/wbem/wsman/1/

        @type selector: dict
        @param selector: The parameters of a selector for the get request.
            Should be a dict which contains the attributes of the selector.
            Some usable attribute names:
                - Name: The name of the selector, used to target what to select
                - text: The value of the selection.

        @rtype: etree._Element
        @return: The XML returned from the server.
            TODO: Find the body content and return that instead? Or is some
            information in the Header interesting too?

        """
        sel = None
        if selector:
            s_txt = ''
            if 'text' in selector:
                s_txt = selector['text']
                del selector['text']
            sel = [self._xml_element('Selector', 'wsman', text=s_txt,
                                     attribs=selector)]
        header = self._xml_header('get', resource=resource, selectors=sel)
        self.logger.debug3('Calling WSMAN Get for resource "%s"' %
                           str(resource))
        ret = self._http_call(self._xml_envelope(header))
        self.logger.debug3('WSMAN Enumerate done for resource "%s"' %
                           str(resource))
        return etree.parse(ret.fp, parser=self.xmlparser)

    def wsman_identify(self):
        """Send an Identify request to the server, to get the service type.

        The Idenfity request is a simple request that should work for all
        services that should support any WSMan standard, as it should be equal
        for all of them. It is used to check what WSMan accent the service is,
        e.g. WinRM, and the brand, e.g. Microsoft.

        Note that WinRM still requires you to authenticate to see this
        information, unless the header:

            WSMANIDENTIFY: unauthenticated

        is specified.

        @rtype: etree._Element
        @return: The Identify response from the server, in SOAP XML format.

        TODO: return only the important part of the response, e.g. as a dict?

        """
        env = self._xml_element('Envelope', 's')
        env.append(self._xml_element('Header', 's'))
        body = self._xml_element('Body', 's')
        body.append(self._xml_element('Identify', 'wsmid'))
        env.append(body)
        self._http_headers['WSMANIDENTIFY'] = 'unauthenticated'
        self.logger.debug3('Calling WSMAN Identify')
        ret = self._http_call(env)  # , address='/wsman-anon/identify')
        self.logger.debug3('WSMAN Identify done')
        del self._http_headers['WSMANIDENTIFY']
        xml = etree.parse(ret.fp, parser=self.xmlparser)
        return xml

    def wsman_pull(self, resource, context):
        """Send a Pull request to the server, to pull for data.

        How a Pull request's Body could look like:

            <wsen:Pull>
                <wsen:EnumerationContext>...</wsen:EnumerationContext>
                <wsen:MaxTime>PT120.000S</wsen:MaxTime>
                <wsen:MaxElements>xs:long</wsen:MaxElements>
                <wsen:MaxCharacters>xs:long</wsen:MaxCharacters>
            </wsen:Pull>

        @type resource: string
        @param resource:
            The type of information to get. Could start with http, or it could
            be relative to:

                http://schemas.microsoft.com/wbem/wsman/1/

        @type context: string
        @param context:
            The identifier of the request to pull. It is an EnumerationContext
            which should have been returned by a L{wsman_enumerate} request.

        @rtype: etree._Element
        @return: The XML PullResponse returned from the server.
            TODO: Does the Header contain something useful too?

        """
        header = self._xml_header('pull', resource=resource)
        body = self._xml_element('Body', 's')
        pull = self._xml_element('Pull', 'wsen')
        pull.append(self._xml_element('EnumerationContext', 'wsen',
                                      text=context))
        body.append(pull)

        tag = '{%s}PullResponse' % namespaces['wsen']
        self.logger.debug3('Calling WSMAN Pull for resource "%s"' %
                           str(resource))
        ret = self._http_call(self._xml_envelope(header, body))
        self.logger.debug3('WSMAN Pull done for resource "%s"' % str(resource))
        for event, elem in etree.iterparse(ret.fp, tag=tag,
                                           encoding=self._winrm_encoding):
            return elem

    def wsman_receive(self, shellid, commandid=None, sequence=0):
        """Send a Recieve request to the server, to get a command's output.

        WinRM's execution of commands works in the way that the command is
        first called by a Command request, which only returns a CommandId,
        which we should then use when sending a Receive request later.

        Note that this command only returns one page of output, you would need
        to loop over the method with a growing L{sequence} to get the rest of
        the pages, until State is "Done".

        Example on how the SOAP XML looks like:

        <s:Body>
          <rsp:Receive
               xmlns:rsp="http://schemas.microsoft.com/wbem/wsman/1/windows/shell"
               SequenceId="0">
            <rsp:DesiredStream
                 CommandId="77df7bb6-b5a0-4777-abd9-9823c0774074">
              stdout stderr
            </rsp:DesiredStream>
          </rsp:Receive>
        </s:Body>

        @type shellid: string
        @param shellid:
            The ShellId that identifies what shell to get the output from.

        @type commandid: string
        @param commandid: The CommanId for the command that has already been
            given to the server. Only output from this command will be
            received.  Not needed for Custom Remote Shells.

        @type sequence: int
        @param sequence: Specifies what "page" of the output that should be
            retrieved. This is only needed when command output is so large that
            it can't fit in a single SOAP message, and has to split up in
            several. Starts on 0 and counts upwards.

        @rtype: tuple
        @return: A three element tuple on the form:

                (string:status, int:return_code, dict:out)

            The L{status} could be Done, Running or Pending. The return code
            might be None, if not given by the server. The out dict could
            contain elements 'stdout' and 'stderr', depending on what the
            server sends.

            The elements in the dict are all unicode objects.

        """
        selector = self._xml_element('Selector', 'wsman', text=shellid,
                                     attribs={'Name': 'ShellId'})
        header = self._xml_header('receive', selectors=[selector])
        body = self._xml_element('Body', 's')
        receiver = self._xml_element('Receive', 'rsp')
        receiver.set('SequenceId', str(sequence))
        body.append(receiver)
        stream = self._xml_element('DesiredStream', 'rsp')
        if commandid:
            stream.set('CommandId', str(commandid))
        stream.text = 'stdout stderr'
        receiver.append(stream)

        self.logger.debug3('Calling WSMAN Recieve for ShellId "%s", '
                           'CommandId "%s"' % (str(shellid), str(commandid)))
        ret = self._http_call(self._xml_envelope(header, body))
        self.logger.debug3('WSMAN Recieve done for ShellId "%s", '
                           'CommandId "%s"' % (str(shellid), str(commandid)))
        root = etree.parse(ret.fp, parser=self.xmlparser)
        exitcode = None
        state = None
        out = dict()

        # Find the CommandState (Done, Running or Pending)
        tag = "{%s}CommandState" % namespaces['rsp']
        for xml_state in root.iter(tag=tag):
            state = xml_state.get('State').split('/')[-1]
        # TODO: Check if state is not set?

        # Find the ExitCode, if given in this round
        tag = "{%s}ExitCode" % namespaces['rsp']
        for code in root.iter(tag=tag):
            # Casting the exitcode into an integer. It could that WinRM tries
            # to use this differently in the future, which would then trigger
            # exceptions here. Would then have to cast it later.
            exitcode = int(code.text)

        # Get the output
        tag = "{%s}Stream" % namespaces['rsp']
        amount = 0
        for elem in root.iter(tag=tag):
            if elem.text:
                amount += len(elem.text)
                out.setdefault(elem.get('Name'), []).append(elem.text)
            # free up memory:
            elem.clear()
        self.logger.debug3("Received %d bytes of base64 data" % int(amount))

        # Clean up output:
        # - Change newlines from Microsoft's format '\r\n' to linux's '\n'.
        # - Remove the Byte Order Mark (BOM) - not needed for UTF-8, except to
        #   identity that it is encoded in UTF-8. More info:
        #   http://www.unicode.org/faq/utf_bom.html#BOM
        for t in out:
            out[t] = ''.join(base64.decodestring(s)
                             for s in out[t]).replace('\r', '')
            out[t] = out[t].decode(self._winrm_encoding)
        return state, exitcode, out

    def wsman_send(self, shellid, commandid, data):
        """Make a Send call with input to be given to the remote Shell. This
        works like piping input through stdin, e.g:

            echo "testing" | cat

        It could be used when a command prompts you for input, e.g. password
        prompts. Note that newlines (\n) are translated to windows' version of
        newlines (\r\n), and it should end with a newline.

        @type shellid: string
        @param shellid: The ShellId for the Shell to use. The shell must have
            been created on the server side.

        @type commandid: string
        @param commandid: The CommandID for the command that should recieve the
            input data. The command must be active on the server, and should
            probably wait for input.

        @type data: string, unicode or list/tuple of strings/unicode objects
        @param data: The data to sent to the server as input.

        @rtype: TODO
        @return: TODO

        """
        if isinstance(data, (tuple, list)):
            data = '\n'.join(unicode2str(d) for d in data)
        else:
            data = unicode2str(data)

        # TODO: Might not want to log what is sent when done debugging:
        self.logger.debug(
            "In shell %s, for CmdID: %s: Sending stdin input: '%s'",
            shellid, commandid, data)
        # Need to add carriage return, to simulate Enter in Windows. A simple
        # newline (\n) would not work, carriage return (\r) is required:
        data = data.replace('\n', '\r\n')
        if not data.endswith('\n'):
            data += '\r\n'
        selector = self._xml_element('Selector', 'wsman', text=shellid,
                                     attribs={'Name': 'ShellId'})
        header = self._xml_header('send', selectors=[selector])
        body = self._xml_element('Body', 's')
        send = self._xml_element('Send', 'rsp')
        send.append(self._xml_element('Stream', 'rsp',
                                      text=base64.encodestring(data),
                                      attribs={'Name': 'stdin',
                                               'CommandId': commandid,
                                               # Not sure if End is used
                                               'End': 'TRUE'}))
        body.append(send)
        self.logger.debug3('Calling WSMAN Send for ShellId "%s", '
                           'CommandId "%s"' % (str(shellid), str(commandid)))
        ret = self._http_call(self._xml_envelope(header, body))
        self.logger.debug3('WSMAN Send done for ShellId "%s", '
                           'CommandId "%s"' % (str(shellid), str(commandid)))
        return etree.parse(ret.fp, parser=self.xmlparser)
        # TODO: What to return? Only True?

    def wsman_signal(self, shellid, commandid, signalcode='Terminate'):
        """Send a Signal request to the server, to send a signal to a command.

        Signals could for instance be used to abort the execution of a running
        command.

        The most used signal is Terminate. This should be sent for a command
        when the client has received all its output and exitcode. The server
        then knows that it doesn't need the output from the command anymore,
        and could remove it from its cache.

        @type shellid: string
        @param shellid: The ShellId for the shell that the command is running
            in.

        @type commandid: string
        @param commandid: The CommandId for the command that should be
            signalled.

        @type signalcode: string
        @param signalcode: The type of signal that should be sent. Valid types:
                            - 'ctrl_c': Aborts the command execution.
                            - 'Terminate': Tells that the server could remove
                                           the given output from its cache, as
                                           the client has received it.

        """
        body = self._xml_element('Body', 's')
        xml = self._xml_element('Signal', 'rsp',
                                attribs={'CommandId': commandid})
        code = self._xml_element('Code', 'rsp')
        code.text = 'http://schemas.microsoft.com/wbem/wsman/1/windows/shell/signal/%s' % signalcode
        xml.append(code)
        body.append(xml)
        selector = self._xml_element('Selector', 'wsman', text=shellid,
                                     attribs={'Name': 'ShellId'})
        self.logger.debug3('Calling WSMAN Signal for ShellId "%s", '
                           'CommandId "%s"' % (str(shellid), str(commandid)))
        ret = self._http_call(self._xml_envelope(self._xml_header('signal',
                                                 selectors=[selector]), body))
        self.logger.debug3(
            'WSMAN Signal done for ShellId "%s", CommandId "%s"',
            shellid, commandid)
        # TODO: What to check?
        # TODO: What to return?
        return ret


class WinRMClient(WinRMProtocol):
    """Client for handling a remote Shell at a WinRM service through the WinRM
    protocol.

    What the client is taking care of, is how all the wsman request should be
    sent and received for WinRM shells. The standard workflow when communicating
    with a WinRM server is:

        1. Send a Create request to create a Shell on the server. A ShellId is
           returned.
        2. Send a Command request to start a new command in the given Shell. A
           CommandId is returned. Note that it's not the result from the
           execution that is returned now, the command might not even be started
           on yet.
        3. If needed, you could send a Send request to send input to stdin or
           pipe. This could e.g. be used to e.g. fill in data in prompts.
           TODO: This does not work as expected, so more work needs to be done
           for this to work.
        4. If you want to, you could now go and do something else. The server is
           processing the command and caching the output.
        5. Send a Receive request to receive the output from the command. If the
           returned State is not "Done", you could keep on sending Send requests
           to get all of the data.
        6. Send a Signal request to tell the server that the output was
           received. The server could now remove the output from its cache and
           use for other commands.
        8. Send and receive more commands if needed in the shell. Note that each
           command is independent of the others, as we need to start powershell
           at each Command request. We might need to improve on this in the
           future, depending on our needs.
        9. Send a Delete request to shut down the given Shell when done. Each
           user only have a limited number of shells available, so you should do
           this to avoid getting temporarily blocked from the server if too many
           AD jobs are running simultaneously.

    The ShellId returned from the Create request (the L{connect} method) is set
    in the instance itself to be used when sending commands.

    """

    def connect(self):
        """Set up a connection to the WinRM server.

        TODO: should we handle reconnects? Shells could be running on the
        server, and we could get list of active shell through wsman_enumerate.

        @rtype: string
        @return: The ShellId of the shell that got created on the server. This
            is also put in L{self.shellid}.

        """
        url = '%s:%s' % (self.host, self.port)
        if getattr(self, '_username', None):
            url = '%s@%s' % (self._username, url)
        self.logger.debug("Connecting to WinRM: %s" % url)
        shellid = self.wsman_create()
        self.shellid = shellid
        # Subclasses could now run some startup commands on the server, e.g.
        # starting powershell in the active shell and import the ActiveDirectory
        # module. Example:
        #   commandid = self.wsman_command(self.shellid, "powershell")
        return shellid

    def execute(self, *args, **kwargs):
        """Send a command to the server and return a ShellId and a CommandId.

        These IDs can be used to retrieve the output. This is for larger
        operations which could take some time to process. For faster commands
        you could rather use the easier method L{run} which returns the
        command's output directly, with the downside of having to wait while
        the command is executed.

        Note that you have to send a signal to the server yourself, when the
        output was received okay. This is automatically done if you get output
        through L{get_output}.

        Due to some weird behaviour in WinRM, we could reach
        MaxConcurrentOperationsPerUser when sending over 1500 commands (default
        value), even though we Signal each command with Terminate. WinRM does
        not decrement the number of operations. We solve this error by starting
        a new shell directly in this method. For more info on the WinRM
        behaviour, see:

            http://msdn.microsoft.com/en-us/library/cc251679.aspx
            http://msdn.microsoft.com/en-us/library/f8ba005a-8271-45ec-92cd-43524d39c80f#id119

        @type shellid: string
        @param shellid: If set, used as the ShellId to execute the command in.
            Otherwise L{self.shellid} would be used.

        @type *args: strings
        @param *args: Input should be the code that should be executed. Note
            that when using the default shell, cmd, you can only specify one
            single command, which must be in the first argument, and the rest
            of the arguments are considered parameters for that.

        @type stdin: string
        @param stdin: Data to send as input to the server.

        @rtype: tuple
        @return: A two element tuple: (ShellId, CommandId). Could later be used
            to get the result of the command.

        """
        shellid = kwargs.get('shellid')
        if not shellid:
            shellid = self.shellid
        assert shellid, "ShellId not given or set"
        try:
            commandid = self.wsman_command(shellid, *args)
        except WinRMServerException, e:
            # Check if error matches MaxConcurrentOperationsPerUser and
            # reconnect. We also check to see if the shells have timed out
            # (the InvalidSelectors error) code, and reconnect in that case
            # too.
            if e.code not in (['s:Receiver', 'w:InternalError'],
                              ['s:Sender', 'w:InvalidSelectors'],):
                raise

            to_raise = True
            if ('The maximum number of concurrent operations for this user '
                    'has been exceeded' in e.reason[0]):
                to_raise = False
                self.logger.debug2('MaxConcurrentOperationsPerUser reached')

            if ('request contained invalid selectors for the resource' in
                    e.reason[0]):
                to_raise = False
                self.logger.debug2('ShellId is inncorrect, or does not ' +
                                   'exist anymore')
            if to_raise:
                raise

            try:
                # Note this could affect already executed commands that is not
                # received by the client yet, as we have not tested if already
                # running or finished commands gets discarded when the shell is
                # closed. Works when used as it is now, but should be tested if
                # we should send more commands before returning their output.
                self.close(shellid)
            except Exception, e:
                self.logger.debug2("Closing shell failed: %s" % e)
            self.connect()
            shellid = self.shellid
            # Retry:
            commandid = self.wsman_command(shellid, *args)

        # Send input to stdin, if given:
        if 'stdin' in kwargs:
            self.wsman_send(shellid, commandid, kwargs['stdin'])
        return shellid, commandid

    def run(self, *args, **kwargs):
        """Send a command to the server, return its response after execution.

        This is a shortcut for calling L{execute} and run it through L{get_data}
        for getting the output data. This method is meant to be used for quick
        commands, as it hangs while waiting for the response. If you want to
        execute commands that take some time, please use L{execute} instead, and
        then use L{get_output} later on.

        @type *args: strings
        @param *args: Input should be the code that should be executed. Note
            that when using the default shell, cmd, you can only specify one
            single command, which must be in the first argument, and the rest of
            the arguments are considered parameters for that.

        @type stdin: string
        @param stdin: Data to send as input to the server.

        @rtype: dict
        @return: A dict with the command's output, separated by output type,
            e.g. 'stderr', 'stdout' and 'pr'. All values should be strings.

        """
        return self.get_data(self.execute(*args, **kwargs))

    def get_output(self, commandid=None, signal=True, timeout_retries=50):
        """Get an iteration of exitcode and output for a given command.

        The output is returned as an iterator, to be able to process the first
        parts of the output already before all is processed or returned from the
        server. When done, the server is told that the output was received and
        could be removed from its cache.

        @type commandid: tuple
        @param commandid: The (ShellId, CommandId) for the command that the
            output should be retrieved from.

        @type signal: bool
        @param signal:
            If we should send a end signal to the server when all the
            output was received. This must be done, according to the
            specifications, after a process has finished, so that the server
            could free up the cache space and use it for the next command.
            It could be set to false in case of a command that needs input later
            on, but you want its initial output first. You then have to signal
            it yourself later on.

        @type timeout_retries: int
        @param timeout_retries:
            How many retry attempts should be made if the
            server responds with a time out. Some methods take a long time to
            process, other cases there might be a deadlock, e.g. when waiting
            for input from the client or other bugs, which we shouldn't wait
            for forever.

        @rtype: iterator
        @return:
            Iterating over output from the server. WinRM splits output into
            different XML response messages if it's too much data. Small
            commands would normally only be sent in one response message, so
            this makes only sense for large output, to start processing the
            output faster.

            Each iteration returns a tuple:

                (exitcode, {'stdout': ..., 'stderr': ...})


        """
        retried = 0
        sequence = 0
        state = 'Running'
        try:
            while state != 'Done':
                try:
                    state, code, out = self.wsman_receive(commandid[0],
                                                          commandid[1],
                                                          sequence)
                except WinRMServerException, e:
                    # Only timeouts are okay to retry:
                    if e.code != ['s:Receiver', 'w:TimedOut']:
                        raise
                    # Timeouts shouldn't be retried for forever:
                    if retried >= timeout_retries:
                        raise
                    retried += 1
                    state = "TimedOut"
                    self.logger.debug2("wsman_receive: Timeout %d", retried)
                    continue
                yield code, out
                retried = 0
                sequence += 1
        finally:
            # Always tell the server that the reponse was read successfully,
            # even if an unhandled exception has occured. Note that we are now
            # not able to retry getting the data from the server without
            # executing the command again.
            if signal:
                self.wsman_signal(commandid[0], commandid[1], 'Terminate')

    def get_data(self, commandid, signal=True, timeout_retries=50):
        """Get the output for a given command.

        This method makes use of L{get_output} but cleans up the output before
        it is returned as a double tuple and not an iterator. The exitcode is
        checked and codes other than 0 are raised as errors.

        You have to wait for the whole response before getting the returned data
        from this command, as it gathers it all up. If you want to start
        processing the output before all of it is sent you should use
        L{get_output} directly.

        @type commandid: tuple
        @param commandid: The (ShellId, CommandId) for the command that the
            output should be retrieved from.

        @type signal: bool
        @param signal: If we should send a end signal to the server when all the
            output was received. This must be done, according to the
            specifications, after a process has finished, so that the server
            could free up the cache space and use it for the next command.
            It could be set to false in case of a command that needs input later
            on, but you want its initial output first. You then have to signal
            it yourself later on.

        @type timeout_retries: int
        @param timeout_retries:
            How many retry attempts should be made if the
            server responds with a time out. Some methods take a long time to
            process, other cases there might be a deadlock, e.g. when waiting
            for input from the client or other bugs, which we shouldn't wait
            for
            forever.

        @rtype: dict
        @return:
            A dict with the command's output separated by output type, e.g.
            'stdout', 'stderr' and 'pr'. The dict's values are single strings
            with all its output.

        @raise ExitCodeException:
            If the exitcode from the output was other than 0.

        """
        out = dict()
        for code, tmpout in self.get_output(commandid, signal=signal,
                                            timeout_retries=timeout_retries):
            for tmp in tmpout:
                if tmpout:
                    out.setdefault(tmp, []).append(tmpout[tmp])
        # Transform output from lists to strings
        for t in out:
            out[t] = ''.join(out[t])
        if int(code) != 0:
            raise ExitCodeException(code, stderr=out.get('stderr'), output=out)
        return out

    def close(self, shellid=None):
        """Shut down a given Shell on the server, to free up resources for other
        processes. Each user has a limited number of shells available on the
        server.

        @type shellid: string
        @param shellid: The given ShellId of the Shell that should be deleted.

        """
        if not shellid and not hasattr(self, 'shellid'):
            return
        if not shellid:
            shellid = self.shellid
        assert shellid, "ShellId neither given nor set"
        return self.wsman_delete(shellid)

    def config2dict(self, config):
        """Parse given config XML and return a dict with the configuration.

        @type config: etree.Element
        @param config: XML from the server that is expected to be its
            configuration. Should be the cfg:Config element.

        @rtype: dict
        @return: A dict with the various configuration, in a format that is
            easier to read in python. Example:

                'Auth': {
                    'Basic': true,
                    'Kerberos': false,
                    ...
                'Winrs': {
                    'AllowRemoteShellAccess': true,
                    'IdleTimeout': 180000000,

            Note that the source (GPO) is not returned, to make the output
            easier. The WinRM server's sysadmins could get the output from
            powershell anyway.

        """
        def filtertag(tag):
            """Filter out the xml def as prefix in tag names."""
            _, name = tag.split('}', 1)
            return name

        def ele2native(ele):
            """Return an element's value or a dict with its children elements.
            Works recursively.

            """
            if ele.text:
                return ele.text
            return dict((filtertag(e.tag), ele2native(e)) for e in ele)

        configtag = '{%s}Config' % namespaces['cfg']
        if isinstance(config, etree._ElementTree) or config.tag != configtag:
            for ele in config.iter(configtag):
                config = ele
                break

        return ele2native(config)


class PowershellClient(WinRMClient):
    """Client for using powershell through WinRM.

    Note that it is not using the Powershell plugin or CustomRemoteShell set up
    with powershell, but is rather just executing powershell.exe through the
    normal WinRM interface. This is easier than to implement the more complex
    Powershell Remote Protocol (PSRP):

        http://msdn.microsoft.com/en-us/library/dd357801%28v=prot.20%29.aspx

    The use of CustomRemoteShell is deprecated, and is disabled from Windows
    Server 2012. You should rather make use of plugins if you later want to use
    powershell directly, without having to go through cmd.

    To be able to use powershell we need to change a bit of the behaviour for
    WinRM. For now, you are only able to run one or more powershell commands
    through L{execute} or L{run} and get the output from this.

    Unfortunately, a new Shell is created for each command that is run. This is
    since we can only run 15 processes per shell without getting blocked from
    the server. This takes unfortunately some longer time for the sync to work,
    and should be fixed when possible. TODO: You could test later versions of
    WinRM and powershell. A downside of this, is that L{self.shellid} is not
    used as it was originally designed in the L{WinRMClient} class.

    """

    # The location of the powershell.exe program we should run. Note that we are
    # expecting x64, and the path might change in the future - should we be able
    # to configure this somewhere?
    exec_path = u'%SystemRoot%\syswow64\WindowsPowerShell\\v1.0\powershell.exe'

    def execute(self, *args, **kwargs):
        """Send powershell commands to the server.

        Fires up the proper powershell.exe with proper parameters.

        Unfortunately, a new Shell must be create for each execution, due to not
        getting blocked from the server.

        """
        #shellid = self.connect()
        # Later versions of powershell just hangs at newlines, so need to remove
        # them. TODO: This could create problems, we need to look at how we
        # generate powershell commands!
        command = u' '.join(args).replace('\n', ' ')
        # Options for powershell:
        # -NonInteractive   To avoid waiting for stdin and deadlocks if a
        #                   prompt is popping up.
        # -NoLogo           We don't want/need to see the copyright banner.
        #                   Don't know if it has any effect though, as we are
        #                   not starting a session.
        # -NoProfile        Loading profile is not needed, at least for now. It
        #                   will probably only increase the startup time if not
        #                   set.
        return super(PowershellClient, self).execute(
            self.exec_path,
            u'-NonInteractive -NoLogo -NoProfile -Command "%s"' % command,
            **kwargs)

    def escape_to_string(self, data):
        """Prepare (escape) data to be used in powershell commands.

        The data should be escaped to avoid parsing errors in powershell, and to
        avoid injections.

        Documentation about escaping in powershell:

            http://www.rlmueller.net/PowerShellEscape.htm

        The main escaping rules in powershell are that single quoted strings
        (those put inside ') does only treat the single quote as a special
        character. Other characters like $ and { are treated as normal
        characters. The single quote should be escaped by another single quote.

        Examples:

            testing testing         -> 'testing testing'
            Mc'Donalds'             -> 'Mc''Donalds'''

        TODO: This is all the escape rules I found. Are there more?

        TODO: How about other special characters, like \n - could those be used
        to hack its way in, or do we need to allow those?

        TODO: Does powershell escape '? Would it for instance be possible to end
        a string with \, and then escape the '?

        TODO: How about two single quotes, is the result '''' usable?

        Lists are transformed into:

            "val1","val2","val3","val4",...

        A dict will be transformed into the string:

            @{'key1'='value1';'key2'='value2','value2b';...}

            Empty strings must be converted to $false.

        While a list or tuple would become:

            'value1','value2'...

        @type data: mixed (dict, list, tuple, string or int)
        @param data: The data that should be escaped to be usable in powershell.

        @rtype: string
        @return: A string that could be used in powershell commands directly.

        """
        if data is None:
            return u'$false'
        if isinstance(data, bool):
            if data:
                return u'$true'
            else:
                return u'$false'
        if isinstance(data, (int, long)):
            return data
        if isinstance(data, float):
            return u"'%f'" % data
        if isinstance(data, basestring):
            # TODO: more that should be removed from strings?
            data = data.replace(u'\0', u'')
            if data == u'':
                return u'$false'
            else:
                return u"'%s'" % data.replace(u"'", u"''")
        if isinstance(data, (tuple, list, set)):
            return u','.join(unicode(self.escape_to_string(s)) for s in data)
        if isinstance(data, dict):
            # Dicts are returned as "Hash Tables" for powershell
            ret = []
            for k, v in data.iteritems():
                k, v = self.escape_to_string(k), self.escape_to_string(v)
                if not k or not v:
                    self.logger.debug4("PowershellClient.escape_to_string: "
                                       "Omitting empty value in hash table, "
                                       "k=%r, v=%r", k, v)
                    continue
                ret.append(u'%s=%s' % (k, v))
            return u'@{%s}' % u';'.join(ret)
        raise Exception('Unknown data type %s for: %s' % (type(data), data))

    def get_data(self, commandid, signal=True, timeout_retries=50):
        """Get the output for a given command.

        The method is overridden only to raise PowershellException when an error
        has occured. This is to be able to separate cmd errors from powershell
        errors.

        @raise PowershellException: If the exitcode from the output was other
            than 0.

        """
        try:
            return super(PowershellClient, self).get_data(commandid, signal,
                                                          timeout_retries)
        except ExitCodeException, e:
            raise PowershellException(e.exitcode, e.stderr, e.output)

    def get_xml_iterator(self, commandid, other):
        """Get a Command's output and return the XML as an iterator of strings.

        This method could be used when data should be sent through the
        powershell command:

            ... | ConvertTo-Xml -as string

        The data is returned as an iterator for saving memory and CPU while
        parsing it. This is useful e.g. when listing out huge amounts of objects
        from AD.

        @type commandid: string
        @param commandid: The CommandId for the command that the output should
            be retrieved from.

        @type other: dict
        @param other: This is where all server output that is not XML gets put,
            sorted by output type. The values are lists of all its output.

        @rtype: iterator
        @return: Each iteration returns a string with the XML data.

        """
        first_round = True
        for exitcode, o in self.get_output(commandid):
            for otype in o:
                if otype != 'stdout':
                    other.setdefault(otype, []).append(o[otype])
                    continue
            out = ''.join(o.get('stdout', ''))
            if not out:
                continue
            if first_round:
                startpos = out.find('<?xml')
                if startpos == -1:  # starttag not found:
                    other.setdefault('stdout', []).append(out)
                    continue
                first_round = False
                other.setdefault('stdout', []).append(out[:startpos])
                out = out[startpos:]
            # TODO: remove this when we could stop winrm from breaking lines
            out = out.replace('\n', '')
            # TODO: find the XML endtag, output could be left after too.
            yield out

    def get_xml_stream(self, commandid, other):
        """Get a Command's output and return the XML as a stream.

        It is only a helper method for iterating output from L{get_xml_iterator}
        through a stream object of the type L{iter2stream}.

        This could be used e.g. by etree.iterparse, to save memory and CPU. The
        powershell command that is used should end with:

            ... | ConvertTo-Xml -as string

        The data is returned as an iterator for saving memory and CPU while
        parsing it. This is useful e.g. when listing out huge amounts of objects
        from AD.

        @type commandid: string
        @param commandid: The CommandId for the command that the output should
            be retrieved from.

        @type other: dict
        @param other: This is where all server output that is not XML gets put,
            sorted by output type. The values are lists of all its output.

        @rtype: instance of iter2stream
        @return: The XML output wrapped in a stream object, to be used by e.g.
            etree.iterparse.

        """
        return iter2stream(self.get_xml_iterator(commandid, other))

    def get_output_csv(self, commandid, other, delimiter=',',
                       line_delimiter=';'):
        """Get a Command's output and return the CSV as an iterator.

        Note that to make the code a lot easier to read, the method reads in the
        complete output from WinRM before parsing it. The result is that it then
        consumes a lot of memory, especially for large output, but it's easier
        to debug later on.

        This method could be used when data to output is piped through the
        powershell command:

            ... | ConvertTo-Csv # TODO: arguments?

        @type commandid: list or dict
        @param commandid: The CommandId for the command that the output should
            be retrieved from. If it is a dict, it is considered to be the
            output from the command already retrieved - the output must then be
            under the 'stdout' key of the dict.

        @type other: dict
        @param other: This is where all server output that is not CSV gets put,
            sorted by output type. The values are lists of all its output.

        @type elements: int
        @param elements: The number of elements to expect from the output. This
            is needed as

        @type delimiter: string
        @param delimiter: The delimiter between the elements on a line.
            Powershell uses comma if nothing else is given.

        @type line_delimiter: string
        @param line_delimiter: The delimiter to separate the lines. This is
            needed as we have no control of the lines, as cmd is splitting the
            lines at 80 characters. This has to be done with a 'replace' command
            in powershell.

        @rtype: iterator
        @return: Iterating each CSV line. Each element is a dict, where the keys
            are the names given by the first element.

            Note that the values in the dict are all unicode objects.

        """
        out = []
        # If the CommandId is not an Id but output data from the server
        if isinstance(commandid, dict):
            out = commandid['stdout']
        else:
            o = self.get_data(commandid)
            out = o.get('stdout')
            for otype, data in o.iteritems():
                if data and otype != 'stdout':
                    other[otype] = data
            del o, otype, data
        out = out.replace('\n', '')
        self.logger.debug3("Got output of length: %d" % len(out))

        # Powershell starts CSV output with a type definition, e.g: #TYPE ADUser
        try:
            startpos = out.index('#TYPE')
        except ValueError, e:
            if out in ('', ';'):
                # empty list of elements
                return
            # TODO: create a new exception type for this, and store output in
            # it?
            self.logger.warn('No CSV start found in output: "%s"', out)
            self.logger.debug("Other output: %s", other)
            raise Exception("Unexpected output, no CSV start found: %s" % e)

        # Check if there are any other output before the CSV:
        if startpos > 0:
            other.setdefault('stdout', []).append(out[:startpos])
            out = out[startpos:]
        # Start on the next line, after the type definition:
        out = out[out.find(line_delimiter):]

        def _decode(value):
            if isinstance(value, bytes):
                value.decode(self._winrm_encoding)
            else:
                return six.text_type(value)

        # Go through each line:
        # TODO: We need to be able to escape delimiters too - in case it exists
        # inside the elements!
        header_names = None
        out = self.split_csv_lines(out, line_delimiter)
        for line in out:
            if not line.strip():
                continue
            element = self.split_csv_line(line)

            # First line contains the header names:
            if not header_names:
                header_names = element
                continue

            if len(header_names) != len(element):
                self.logger.warn("Bad output? Line: %r", line)
                self.logger.warn("Bad output? Element: %r", element)
                self.logger.debug("Headers: %r", header_names)

            yield dict((header_names[i], _decode(element[i]))
                       for i in range(len(header_names)))

    @staticmethod
    def split_csv_lines(input, delimiter=';', value_wrapper='"'):
        """Split the lines in our own modified CSV format from powershell.

        The lines are normally separated with semicolons, which could also exist
        inside of elements, which must then be ignored.

        @type input: string
        @param input: The CSV input that should be separated.

        @type delimiter: string
        @param delimiter: The character that should separate the CSV lines.

        @type value_wrapper: string
        @param value_wrapper: The character that marks the start and end of a
            value. Used to be able to ignore delimiters that exists inside
            values.

        @rtype: iterator
        @return: The input, split up line by line.

        """
        # TODO: there is probably a much better way of doing this!
        in_wrapper = False
        line = []
        for i in input:
            if not in_wrapper and i == delimiter:
                yield ''.join(line)
                line = []
                continue
            if i == value_wrapper:
                # TODO: Need to be able to escape it!
                in_wrapper = not in_wrapper
            line.append(i)
        if line:
            yield line

    @staticmethod
    def split_csv_line(input, delimiter=',', value_wrapper='"'):
        """Split a line in powershell's CSV format.

        Example on a line:

            "Firstname, Lastname","username","SID"

        which, you could see, could contain commas inside the elements.

        @type delimiter: string
        @param delimiter: The character that separates each CSV element on the
            line.

        @type value_wrapper: string
        @param value_wrapper: The character that tells us that all inside of
            this is for the same value. If a delimiter character occurs inside
            of the value wrapper, it should be considered a part of the value
            and not as a separator.

        @rtype: list
        @return: The elements of the line, split into a list.

        """
        # TODO: is this too slow? Do we have a faster way of splitting and still
        # respecting the value wr
        ret = []
        tmp = []
        inside_value = False
        previous_char = None
        for i in input:
            if not inside_value:
                if i == delimiter:
                    ret.append(''.join(tmp))
                    tmp = []
                elif i == value_wrapper:
                    inside_value = True
                elif i in ('\n', '\r', ' '):
                    # ignore whitespace
                    pass
                else:
                    raise Exception("Unknown CSV input %s for line: %s" % (i, input,))
            else:
                if i == value_wrapper:
                    # TODO: need to check for escaped value_wrapper! How is that
                    # handled by powershell?
                    inside_value = False
                else:
                    tmp.append(i)
            previous_char = i
        # Add the last element. It might be empty, which makes the line just end
        # with a delimiter, but you still have to append it:
        if tmp or input.endswith(delimiter):
            ret.append(''.join(tmp))
        return ret

    def get_output_json(self, commandid, other):
        """Get a Command's output and return the JSON as native data.

        This method could be used when data to output is piped through the
        powershell command:

            ... | ConvertTo-Json

        Note that to make the code a lot easier to read, the method reads in the
        complete output from WinRM before parsing it. The result is that it then
        consumes a lot of memory, especially for large output, but it's easier
        to debug later on.

        @type commandid: list or dict
        @param commandid: The CommandId for the command that the output should
            be retrieved from. If it is a dict, it is considered to be the
            output from the command already retrieved - the output must then be
            under the 'stdout' key of the dict.

        @type other: dict
        @param other: This is where all server output that is not CSV gets put,
            sorted by output type. The values are lists of all its output.

        @rtype: mixed
        @return: All the JSON output is returned as native python data elements.
            The output could return a list, a dict (array) or a single element.

            Note that all returned strings, including dict keys, are unicode
            objects.

        """
        out = []
        # If the CommandId is not an Id but output data from the server
        if isinstance(commandid, dict):
            out = commandid['stdout']
        else:
            o = self.get_data(commandid)
            out = o.get('stdout')
            for otype, data in o.iteritems():
                if data and otype != 'stdout':
                    other[otype] = data
            del o, otype, data
        self.logger.debug3("Got output of length: %d" % len(out))
        # TODO: how to avoid creating a full copy of the data, e.g. by strip?
        out = out.strip()
        if not out:
            return ()
        # Powershell ends JSON output with semicolon, which needs to be
        # removed for json to parse it without errors:
        if out.endswith(';'):
            out = out[:-1]
        try:
            r = json.loads(out)
        except ValueError:
            # TODO: Add better debugging later
            raise
        return r
        # TODO: should we yield it iteratively, to save memory?

    @staticmethod
    def xml_obj2dict(obj):
        """Helper method for converting an Object from powershell represented in
        XML into a python dict.

        For example, the XML:

          <Object Type="Microsoft.ActiveDirectory.Management.ADUser">
            <Property Name="DistinguishedName" Type="System.String">
                CN=username,OU=users,OU=cerebrum,DC=uio,DC=no
            </Property>
            <Property Name="Enabled" Type="System.Boolean">True</Property>
            <Property Name="SamAccountName" Type="System.String">
                username
            </Property>
            ...
            <!-- Also recursive properties: -->
            <Property Name="PropertyNames"
                      Type="System.Collections.Generic.SortedDictionary`2+KeyCollection[System.String,Microsoft.ActiveDirectory.Management.ADPropertyValueCollection]">
                <Property Type="System.String">DistinguishedName</Property>
                <Property Type="System.String">Enabled</Property>
                ...
            </Property>
          </Object>

        Which could get transformed into:

            {'DistinguishedName': 'CN=username,OU=users,OU=cerebrum,DC=uio,DC=no',
             'Enabled': True,
             'GivenName': 'FirstName',
             'PropertyNames: ['DistinguishedName', 'Enabled', ...],
             ...
             }

        @type obj: etree._Element
        @param obj: An XML Element that represents an Object returned from
            powershell.

        @rtype: dict
        @return: A dict with all the properties of the given object that we care
            about.

        """
        # Mapping of how to convert simple types:
        conv_map = {'System.String': unicode,
                    'System.Boolean': bool,
                    'System.Int32': int,
                    # TODO: add more
                    }
        ret = dict()
        for ch in obj.iterchildren():
            if ch.tag != 'Property':
                logger.warn('Unknown element %r for object', ch.tag)
                # TODO/TBD: Is this method used? no 'elem'!
                logger.debug(etree.tostring(elem))
                continue
            conv = conv_map.get(ch.get('Type'), None)
            if conv:
                if ch.text is None:
                    ovalue = None
                else:
                    ovalue = conv(ch.text)
            else:
                ovalue = ch.text
                # TODO: if element has children, the values should be a dict
            if ch.get('Name') in ret:
                logger.warn("XML: already set: %s = %s",
                            ch.get('Name'), ret[ch.get('Name')])
            ret[ch.get('Name')] = ovalue
        return ret


class iter2stream(object):
    """Helper class for converting an iterator into a stream.

    This is for methods that requires a file-like stream input, for instance
    L{lxml.etree.iterparse}, which we could then use iterators for, and thus
    save memory and some cpu usage.

    It is expecting data in str and not unicode, since this is what
    etree.iterparse wants.

    """
    def __init__(self, iterable):
        self.buffered = ''
        self.iter = iter(iterable)

    def read(self, size=5000):
        """Return a given number of bytes from the iterator."""
        data = self.buffered or self.iter.next()
        self.buffered = ''
        if data is None:
            return ''
        if len(data) > size:
            self.buffered = data[size:]
            return data[:size]
        elif len(data) == size:
            return data
        try:
            return data + self.read(size - len(data))
        except StopIteration:
            return data
