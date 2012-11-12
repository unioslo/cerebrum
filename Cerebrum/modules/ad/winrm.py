#!/usr/bin/env python
# -*- encoding: utf8 -*-
# 
# Copyright 2012 University of Oslo, Norway
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

WinRM is a protocol for communicating with Windows machines (servers) to get and
set differents kinds of information. WinRM is Microsoft's version of WSMan,
which is based on SOAP and uses different WS-* standards.

Our focus is to use WinRM to execute commands on the server side, which we then
could use to administrate Active Directory (AD).

The WinRM server has to be set up properly before we could connect to it.

For more information about the WinRM standard, see:

    http://msdn.microsoft.com/en-us/library/aa384426.aspx
    http://msdn.microsoft.com/en-us/library/cc251526(v=prot.10).aspx

"""

import random
import base64
import socket
import urllib2
from lxml import etree

import cerebrum_path

# The namespaces that might be used in the SOAP envelopes, for the server to be
# happy. This is the namespaces that are used in Microsoft's documentation.
namespaces = {
    'rsp':   "http://schemas.microsoft.com/wbem/wsman/1/windows/shell",
    's':     "http://www.w3.org/2003/05/soap-envelope",
    'wsa':   "http://schemas.xmlsoap.org/ws/2004/08/addressing",
    'wsman': "http://schemas.dmtf.org/wbem/wsman/1/wsman.xsd",
    'wsen':  "http://schemas.xmlsoap.org/ws/2004/09/enumeration",
    'wsmid': "http://schemas.dmtf.org/wbem/wsman/identity/1/wsmanidentity.xsd",
    'xml':   "http://www.w3.org/XML/1998/namespace",
    }
#if hasattr(etree, 'register_namespace'):
#    for prefix, url in namespaces.iteritems():
#        etree.register_namespace(prefix, url)

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

class WinRMServerException(Exception):
    """Exception for HTTP 500 Server Errors. WinRM's standard way of saying that
    something failed, and it's either an unknown error or something the client
    have done.

    """
    def __init__(self, code, reason, details=None):
        super(WinRMServerException, self).__init__(code, reason, details)
        self.code = code
        self.reason = reason
        self.details = details

class WinRMProtocol(object):
    """The basic protocol for sending correctly formatted SOAP-data to the WinRM
    server. Methods for sending different call types, like Get, Execute and
    Send, are available, but more advanced functionality should not be put in
    this class.

    If we need to support more WinRM call types, you should add them as new
    methods in this class.

    """

    # The default ports for encrypted [0] and unencrypted [1] communication:
    default_ports = (5986, 5985)

    # Timeout in seconds for trying to connect to the server:
    connection_timeout = 100

    # The string that identifies this client in HTTP calls
    useragent = 'Cerebrum WinRM client'

    def __init__(self, host='localhost', port=None, encrypted=True,
                 logger=None):
        """Set up the basic configuration. Fill the HTTP headers and set the
        correct port if not given.

        """
        self.host = host
        self.encrypted = bool(encrypted)
        if port is None:
            self.port = self.default_ports[0]
            if not self.encrypted:
                self.port = self.default_ports[1]
        # TODO: How should we handle no logger?
        self.logger = logger
        self._opener = urllib2.build_opener()
        self._http_headers = {
                'Host': '%s:%s' % (self.host, self.port),
                'Accept': '*/*',
                'Content-Type': 'application/soap+xml; charset=utf-8',
                'User-Agent': self.useragent}

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

        @type xml: ElementTree or string
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

        """
        if not isinstance(xml, basestring):
            xml = etree.tostring(xml)
        # Add the XML header definition
        xml = '<?xml version="1.0" encoding="UTF-8" ?>\n%s' % xml
        req = urllib2.Request(self._http_url(address), xml, self._http_headers)
        original_timeout = urllib2.socket.getdefaulttimeout()
        urllib2.socket.setdefaulttimeout(self.connection_timeout)
        try:
            ret = self._opener.open(req)
        except urllib2.HTTPError, e:
            if e.code == 401: # Unauthorized
                self.logger.debug("Server says 401 Unauthorized")
                #if ("Negotiate" in e.hdrs.get('www-authenticate', '') and
                #        "Basic" in e.hdrs.get('www-authenticate', '')):
                #    print "Retry with Negotiate Basic?"

                # TODO: Should we support authenticating through Kerberos? Or
                #       should we only have a local user account for the AD
                #       sync?
                self.logger.warn("No known server auth method: %s" %
                                 e.hdrs.get('www-authenticate', None))
                raise
            elif e.code == 500:
                code, reason, detail = self._parse_fault(e)
                raise WinRMServerException(code, reason, detail)

                self.logger.warn("Fault [%s]: %s" % (','.join(code),
                                                  '| '.join(reason)))
                self.logger.warn("Fault detail: %s" % '\n'.join(detail))
                raise
            self.logger.warn("Server http error, code=%s: %s" % (e.code, e.msg))
            self.logger.warn("Server headers: %s" % str(e.hdrs).replace('\r\n', ' | '))
            raise
        except urllib2.URLError, e:
            self.logger.warn("Connection error: %s" % (e.reason,))
            raise
        except socket.timeout, e:
            self.logger.warn("Socket timeout when connecting to %s: %s" %
                          (self._http_url('wsman'), e))
            raise
        finally:
            urllib2.socket.setdefaulttimeout(original_timeout)
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

            - Code (int): Could be an internal Win32 error code or an application
              specific code. Search for MS-ERREF to get a list of standard
              codes.

            - Machine (string): The machine where the fault occured.

            - Message (mixed content) [optional]: Different data that gives more
              details about the fault.

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
        Header and Body should exist, but at least the Body could be empty (e.g.
        <s:Body/>).

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
        if ns_prefix:
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
        a lot of different WS-* standards, e.g. WS-Addressing and WS-Management,
        but most of the WSMan calls looks fortunately the same. The Header
        returned from this method could therefore contain most of those
        settings.

        Some of the elements that are used:

        - wsa:Action: The action type to request for. See L{action_types}.

        - wsa:MessageID: A random string with a unique Id of this message.

        - wsa:ReplyTo: wsa:Address: Who should get the reply. Only set to
          anonymous, as we get the reply through the HTTP reply.

        - wsa:To: Addressing to whom the request is for. This is since the
          requests for WinRM are not bound to TCP.

        - wsman:Locale: Specify language to use in replies and faults. Default:
          en-US.

        - wsman:MaxEnvelopeSize: The max size of the reply message. If the reply
          gets bigger than this, the message gets split up in different
          envelopes.
          
        - wsman:OperationTimeout: Set how long the request could run before it
          gets timed out. This is only for the connection to the server, it does
          not override the max lifetime for the user's shells.

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
          <wsman:MaxEnvelopeSize s:mustUnderstand="true">153600</wsman:MaxEnvelopeSize>
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
            L{Cerebrum.modules.ad.winrm.action_types} for defined actions.
            Examples are 'command', 'create', 'send' and 'delete'.

        @type resource: String
        @param resource: The resource URI as specified in wsman:ResourceURI.
            Used differently for the various action types, some types doesn't
            even use it. If the URI doesn't start with 'http' it will be set up
            with a prefix of:

                http://schemas.microsoft.com/wbem/wsman/1/

            Examples of resources could be 'windows/shell/cmd' when working with
            standard shells, 'config' at Get requests for getting the server
            configuration and
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

        uri = self._xml_element('ResourceURI', 'wsman',
                #text='http://schemas.microsoft.com/powershell/microsoft.powershell',
                #text='http://schemas.microsoft.com/wbem/wsman/1/%s' % resource,
                text=resource,
                attribs={'s:mustUnderstand': 'true'})
        header.append(uri)

        act = self._xml_element('Action', 'wsa', text=action_types[action],
                                attribs={'s:mustUnderstand': 'true'})
        header.append(act)

        size = self._xml_element('MaxEnvelopeSize', 'wsman', text='153600',
                                 attribs={'s:mustUnderstand': 'true'})
        header.append(size)

        msgid = self._xml_element('MessageID', 'wsa')
        # TODO: Do we need a better randomizer for this?
        msgid.text = ('uuid:ABABABAB-' + ''.join(str(random.randint(0,9))
                                                 for i in xrange(30)))
        header.append(msgid)

        locale = self._xml_element('Locale', 'wsman',
                                   attribs={'xml:lang': 'en-US',
                                            's:mustUnderstand': 'false'})
        header.append(locale)

        timeout = self._xml_element('OperationTimeout', 'wsman',
                                    text='PT20.000S')
        header.append(timeout)

        # Add Selector, if given:
        if selectors:
            selectorset = self._xml_element('SelectorSet', 'wsman')
            for s in selectors:
                selectorset.append(s)
            header.append(selectorset)

        # Add the Shell ID as a selector, if it exists.
        # TODO: This should be added from somewhere else...
        #
        #if getattr(self, 'shellid', None):
        #    selector = self._xml_element('Selector', 'wsman',
        #                                    text=self.shellid, attribs={'Name':
        #                                                            'ShellId'})
        #    selectors = self._xml_element('SelectorSet', 'wsman')
        #    selectors.append(selector)
        #    header.append(selectors)
        return header

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
            be a single command, a command with parameters or many commands that
            should all be executed. All the strings are simply sent to the
            server, so they need to be valid code.

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
        # WINRS_CONSOLEMODE_STDIN: TRUE makes input from wsman_send go directly
        # to the console. FALSE send input from wsman_send through pipes. Is for
        # different purposes, not sure of what we should use, but
        # get-credentials does not accept input through pipes, so it looks like
        # we have to set it to true:
        options.append(self._xml_element('Option', 'wsman', 
                                    attribs={'Name': 'WINRS_CONSOLEMODE_STDIN'},
                                    text='TRUE'))
        options.append(self._xml_element('Option', 'wsman', 
                                    attribs={'Name': 'WINRS_SKIP_CMD_SHELL'},
                                    text='TRUE'))
        header.append(options)

        body = self._xml_element('Body', 's')
        cmdline = self._xml_element('CommandLine', 'rsp')
        body.append(cmdline)

        # To support sending blank commands:
        if not args:
            args = [None]

        cmd = self._xml_element('Command', 'rsp', text=args[0])
        cmdline.append(cmd)
        for a in args[1:]:
            cmdline.append(self._xml_element('Arguments', 'rsp', text=a))

        ret = self._http_call(self._xml_envelope(header, body))
        tag = '{%s}CommandId' % namespaces['rsp']
        for event, elem in etree.iterparse(ret.fp, tag=tag):
            return elem.text
        raise Exception('Did not receive CommandID')

    def wsman_create(self):
        """Send a Create request to the server, asking it to create a new Shell.
        This shell could later be used to execute commands.

        Example on how a Create request looks like (inside s:Body):

        <s:Header>
          ...
          <wsman:OptionSet xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
            <wsman:Option Name="WINRS_NOPROFILE">TRUE</wsman:Option>
            <wsman:Option Name="WINRS_CODEPAGE">437</wsman:Option>
          </wsman:OptionSet>
          ...
        </s:Header>
        <s:Body>
          <rsp:Shell xmlns:rsp="http://schemas.microsoft.com/wbem/wsman/1/windows/shell">
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
        #env = self._xml_element('Environment', 'rsp')
        # TODO: Do we need  environment variables?
        #header.append(env)
        options = self._xml_element('OptionSet', 'wsman')
        options.append(self._xml_element('Option', 'wsman', text='TRUE',
                                         attribs={'Name': 'WINRS_NOPROFILE'}))
        header.append(options)

        body = self._xml_element('Body', 's')
        shell = self._xml_element('Shell', 'rsp', nsmap={'rsp':
                     'http://schemas.microsoft.com/wbem/wsman/1/windows/shell'})
        shell.append(self._xml_element('Lifetime', 'rsp', text='PT20.000S'))
        shell.append(self._xml_element('InputStreams', 'rsp', text='stdin'))
        shell.append(self._xml_element('OutputStreams', 'rsp',
                                       text='stdout stderr'))
        body.append(shell)
        ret = self._http_call(self._xml_envelope(header, body))
        # Find the ShellID:
        for event, elem in etree.iterparse(ret.fp,
                    tag='{http://schemas.dmtf.org/wbem/wsman/1/wsman.xsd}Selector'):
            return elem.text 
        raise Exception('Did not receive ShellId from server')

    def wsman_delete(self, shellid):
        """Send a Delete request to the server, to terminate the Shell by the
        given ShellId.

        It is recommended to delete the shell when a job has finished, to free
        up usage on the server. Only a limited number of shells are available
        per user, and old shells could stay idle for quite some time before they
        get deleted.

        """
        selector = self._xml_element('Selector', 'wsman', text=shellid,
                                     attribs={'Name': 'ShellId'})
        ret = self._http_call(self._xml_envelope(self._xml_header('delete',
                                                        selectors=[selector])))
        # TODO: Parse and check reply?

    def wsman_enumerate(self, type='config', selector=None):
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

        @type type: string
        @param type: The type of information to get. Could start with http, or
            it could be relative to:

                http://schemas.microsoft.com/wbem/wsman/1/

        @type selector: dict
        @param selector: The parameters of a selector for the get request.
            Should be a dict which contains the attributes of the selector.
            Some usable attribute names:
                - Name: The name of the selector, used to target what to select
                - text: The value of the selection.

        @rtype: string
        @return: The Id of the EnumerateResponse. This should be used to get the
            output from the enumerate request through L{wsman_pull}. You might
            want to do something else while waiting, as it might take a while to
            process, depending on what you requested.

        """
        sel = None
        if selector:
            s_txt = ''
            if selector.has_key('text'):
                s_txt = selector['text']
                del selector['text']
            sel = [self._xml_element('Selector', 'wsman', text=s_txt,
                                    attribs=selector)]
        header = self._xml_header('enumerate', resource=type, selectors=sel)
        body = self._xml_element('Body', 's')
        enum = self._xml_element('Enumerate', 'wsen')
        # wsen:Expires must either be a datetime, e.g.
        # '2002-10-10T12:00:00-05:00', or a ISO8601 duration on the format "PnYn
        # MnDTnH nMnS" - quoting:
        #
        #   [...] where nY represents the number of years, nM the number of
        #   months, nD the number of days, 'T' is the date/time separator, nH
        #   the number of hours, nM the number of minutes and nS the number of
        #   seconds. The number of seconds can include decimal digits to
        #   arbitrary precision
        #enum.append(self._xml_element('Expires', 'wsen', text='PT120.000S'))
        body.append(enum)
        ret = self._http_call(self._xml_envelope(header, body))
        tag = '{%s}EnumerationContext' % namespaces['wsen']
        for event, elem in etree.iterparse(ret.fp, tag=tag):
            return elem.text
        raise Exception("Unknown Enumeration response for type='%s'" % type)

    def wsman_get(self, type='config', selector=None):
        """Send a Get request to the server, to get specified information.

        @type type: string
        @param type: The type of information to get. Could start with http, or
            it could be relative to:

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
            if selector.has_key('text'):
                s_txt = selector['text']
                del selector['text']
            sel = [self._xml_element('Selector', 'wsman', text=s_txt,
                                    attribs=selector)]
        header = self._xml_header('get', resource=type, selectors=sel)
        ret = self._http_call(self._xml_envelope(header))
        xml = etree.parse(ret.fp)
        return xml

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
        ret = self._http_call(env) # , address='/wsman-anon/identify')
        del self._http_headers['WSMANIDENTIFY']
        xml = etree.parse(ret.fp)
        return xml

    def wsman_pull(self, type='config', context=None):
        """Send a Pull request to the server, to pull for data.

        How a Pull request's Body could look like:

            <wsen:Pull>
                <wsen:EnumerationContext>...</wsen:EnumerationContext>
                <wsen:MaxTime>PT120.000S</wsen:MaxTime>
                <wsen:MaxElements>xs:long</wsen:MaxElements>
                <wsen:MaxCharacters>xs:long</wsen:MaxCharacters>
            </wsen:Pull>

        @type type: string
        @param type: The type of information to get. Could start with http, or
            it could be relative to:

                http://schemas.microsoft.com/wbem/wsman/1/

        @type context: string
        @param contet: The EnumerationContext which should have been returned
            by a L{wsman_enumerate} request.

        @rtype: etree._Element
        @return: The XML PullResponse returned from the server.
            TODO: Does the Header contain something useful too?

        """
        header = self._xml_header('pull', resource=type)
        body = self._xml_element('Body', 's')
        pull = self._xml_element('Pull', 'wsen')
        pull.append(self._xml_element('EnumerationContext', 'wsen', text=context))
        body.append(pull)

        tag = '{%s}PullResponse' % namespaces['wsen']
        ret = self._http_call(self._xml_envelope(header, body))
        for event, elem in etree.iterparse(ret.fp, tag=tag):
            return elem

    def wsman_receive(self, shellid, commandid=None, sequence=0):
        """Send a Recieve request to the server, to get a command's output.

        WinRM's execution of commands works in the way that the command is first
        called by a Command request, which only returns a CommandId, which we
        should then use when sending a Receive request later.

        Note that this command only returns one page of output, you would need
        to loop over the method with a growing L{sequence} to get the rest of
        the pages, until State is "Done".

        Example on how the SOAP XML looks like:

        <s:Body>
          <rsp:Receive 
               xmlns:rsp="http://schemas.microsoft.com/wbem/wsman/1/windows/shell"
               SequenceId="0">
            <rsp:DesiredStream CommandId="77df7bb6-b5a0-4777-abd9-9823c0774074">
                  stdout stderr
            </rsp:DesiredStream>
          </rsp:Receive>
        </s:Body>

        @type shellid: string
        @param shellid: The ShellId that identifies what shell to get the output
            from.

        @type commandid: string
        @param commandid: The CommanId for the command that has already been
            given to the server. Only output from this command will be received.
            Not needed for Custom Remote Shells.

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
            contain elements 'stdout' and 'stderr', depending on what the server
            sends. The elements in the dict are unicode strings with output.

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

        ret = self._http_call(self._xml_envelope(header, body))

        out = dict()
        exitcode = None
        state = None

        root = etree.parse(ret.fp)
        tag = "{%s}Stream" % namespaces['rsp']
        amount = 0
        for elem in root.iter(tag=tag):
            if elem.text:
                amount += len(elem.text)
                out.setdefault(elem.get('Name'), []).append(elem.text)
        self.logger.debug("Received %d bytes of base64 data" % amount)

        tag = "{%s}CommandState" % namespaces['rsp']
        for xml_state in root.iter(tag=tag):
            state = xml_state.get('State').split('/')[-1]
        # TODO: Check if state is not set?

        tag = "{%s}ExitCode" % namespaces['rsp']
        for code in root.iter(tag=tag):
            exitcode = code.text
        # TODO: Check if exitcode is not set?

        # Clean up output
        for t in out:
            # TODO: Why is it returned as latin-1 and not utf-8? Is it because
            # we send in latin-1 characters? Can't find anything about this in
            # the specification.
            out[t] = u''.join(unicode(base64.decodestring(s), 'latin-1')
                              for s in out[t]).replace('\r\n', '\n')
        return state, exitcode, out

    def wsman_send(self, commandid, data):
        """Make a Send call with input to be given to the remote Shell. This
        works like piping input through stdin, e.g:

            echo "testing" | cat

        It could for instance be used when a command asks you for a password,
        e.g. 'get-credential "cerebrum_service"'.

        Note that this method does some reformatting of the given data, to make
        it readable by the windows server.

        @type commandid: string
        @param commandid: The CommandID for the command that should recieve the
            input data. The command must be active on the server, and probably
            waiting for input.

        @rtype: TODO
        @return: TODO

        """
        assert self.shellid, "Not logged on to server, try to connect first"
        if isinstance(data, (tuple, list)):
            data = '\n'.join(data)
        # TODO: Might not want to log what is sent when done debugging:
        self.logger.debug("In shell %s, for CmdID: %s: Sending stdin input: '%s'" %
                       (self.shellid, commandid, data))
        # Need to add carriage return, to simulate Enter in Windows. A simple
        # newline (\n) would not work, carriage return (\r) is required:
        data = data.replace('\n', '\r\n')
        if not data.endswith('\n'):
            data += '\r\n'
        selector = self._xml_element('Selector', 'wsman', text=self.shellid,
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
        ret = self._http_call(self._xml_envelope(header, body))
        return etree.parse(ret.fp)
        # TODO: What to return? Only True?

    def wsman_signal(self, commandid, signalcode='terminate'):
        """Send a Signal request to the server, to send a signal to a command.

        Signals could for instance be to "ack" that the command's output has
        been received on our side, or to abort the execution of the command.

        Between each Receive calls, the server should get a Signal, so that the
        server knows what has been successfully sent, and could remove it from
        cache and start sending the next round of output.

        @type commandid: string
        @param commandid: The CommandId for the command that should be
            signalled.

        @type signalcode: string
        @param signalcode: The type of signal that should be sent. Types:
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
        selector = self._xml_element('Selector', 'wsman', text=self.shellid,
                                     attribs={'Name': 'ShellId'})
        return self._http_call(self._xml_envelope(self._xml_header('signal',
                                                    selectors=[selector]), body))
        # TODO: What to return?

class WinRMClient(WinRMProtocol):
    """Client for handling a remote Shell at a WinRM service through the WinRM
    protocol.

    What the client is taking care of, is how all the wsman request should be
    sent and received. The standard workflow when communicating with a WinRM
    server is:

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

    """

    def connect(self):
        """Set up a connection to the WinRM server.

        TODO: should we handle reconnects? Shells could be running on the
        server, and we could get list of active shell through wsman_enumerate.

        """
        self.logger.debug("Connecting to WinRM: %s:%s" % (self.host, self.port))
        self.shellid = self.wsman_create()
        # Subclasses could now run some startup commands on the server, e.g.
        # starting powershell in the active shell and import the ActiveDirectory
        # module. Example:
        #   commandid = self.wsman_command(self.shellid, "powershell")
        return True 

    def execute(self, *args, **kwargs):
        """Send a command to the server and return a CommandId that could be
        used to retrieve the output. This is for larger operations which could
        take some time to process. For faster commands you could rather use the
        easier method L{run} which returns the command's output directly.

        @type *args: strings
        @param *args: Input should be the code that should be executed. Note
            that when using the default shell, cmd, you can only specify one
            single command, which must be in the first argument, and the rest of
            the arguments are considered parameters for that.

        @type stdin: string
        @param stdin: Data to send as input to the server.

        """
        commandid = self.wsman_command(self.shellid, *args)
        # Send input to stdin, if given:
        if 'stdin' in kwargs:
            self.wsman_send(commandid, kwargs['stdin'])
        self._last_commandid = commandid
        return commandid

    def run(self, *args, **kwargs):
        """Send a command to the server, return its response after execution.

        This method is meant to be used for quick commands, as it hangs while
        waiting for the response. If you want to execute commands that take some
        time, please use L{execute} instead, and then use L{get_output} later
        on.

        @type *args: strings
        @param *args: Input should be the code that should be executed. Note
            that when using the default shell, cmd, you can only specify one
            single command, which must be in the first argument, and the rest of
            the arguments are considered parameters for that.

        @type stdin: string
        @param stdin: Data to send as input to the server.

        @rtype: tuple
        @return: The first element is the exitcode for the command, while the
            second element is a dict with output, where the keys are output
            types, and the values are strings of output.

        """
        commandid = self.execute(*args, **kwargs)
        out = dict()
        # Get output from server
        for code, tmpout in self.get_output(commandid):
            for type in tmpout:
                out.setdefault(type, []).append(tmpout[type])
        # Transform output from lists to strings
        for t in out:
            out[t] = ''.join(out[t])
        return code, out

    def get_output(self, commandid=None, signal=True, timeout_retries=10):
        """Get the exitcode and output for a given command.

        The output is returned as an iterator, to be able to process the first
        parts of the output already before all is processed or returned from the
        server.

        @type commandid: string
        @param commandid: The CommandId for the command that the output should
            be retrieved from. If not given, the CommandId from the latest call
            to L{execute} is used instead.

        @type signal: bool
        @param signal: If we should send a end signal to the server when all the
            output was received. This must be done, according to the
            specifications, after a process has finished, so that the server
            could free up the cache space and use it for the next command.
            It could be set to false in case of a command that needs input later
            on, but you want its initial output first. You then have to signal
            it yourself later on.

        @type timeout_retries: int
        @param timeout_retries: How many retry attempts should be made if the
            server responds with a time out. Some methods take a long time to
            process, other cases there might be a deadlock, e.g. when waiting
            for input from the client or other bugs, which we shouldn't wait for
            forever.

        @rtype: iterator
        @return: Iterating over output from the server. WinRM splits output into
            different XML response messages if it's too much data. Small
            commands would normally only be sent in one response message, so
            this makes only sense for large output, to start processing the
            output faster.

        """
        if not commandid:
            commandid = self._last_commandid
        assert commandid, "No CommandId is given, and no previos Ids found"

        retried = 0
        sequence = 0
        state = 'Running'
        while state != 'Done':
            try:
                state, code, out = self.wsman_receive(self.shellid, commandid,
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
                self.logger.debug("wsman_receive: Timeout %d" % retried)
                continue
            yield code, out
            retried = 0
            sequence += 1
        # Tell the server that the reponse was read successfully:
        if signal:
            self.wsman_signal(commandid, 'terminate')

    def close(self):
        """Shut down the active Shell on the server. Useful so that you could
        make of the Shell for other processes, since each user has a limited
        number of shells available on the server.

        """
        if self.shellid:
            return self.wsman_delete(self.shellid)
        del self.shellid

class PowershellClient(WinRMClient):
    """Client for using powershell through WinRM.

    Note that it is not using the Powershell plugin or CustomRemoteShell set up
    with powershell, but is rather just executing powershell.exe through the
    normal WinRM interface. This is easier than to implement the more complex
    Powershell Remote Protocol (PSRP).

    """

    def execute(self, *args, **kwargs):
        """Send powershell commands to the server."""
        return super(PowershellClient, self).execute(
                # TODO: We are here expecting x64, and the path might change in
                # the future, so we should be able to configure this somewhere.
                u'%SystemRoot%\syswow64\WindowsPowerShell\\v1.0\powershell.exe',
                u'-NonInteractive', # As we can't handle stdin yet. This avoids
                                    # deadlocks, if a prompt is popping up.
                *args, **kwargs)

# TODO: The rest should be moved to a file with more AD related stuff:
#class ADClient(PowershellClient):
#
#    def execute(self, *args, **kwargs):
#        """Send commands to the server, but first setting up the environment
#        properly, to be able to work with AD with Cerebrum's domain account.
#
#        """
#        return self.execute(u"""$pass = ConvertTo-SecureString -Force -AsPlainText '%(ad_password)s';
#                       $cred = New-Object System.Management.Automation.PSCredential('"%(ad_user)s"', $pass);
#                       Import-Module ActiveDirectory;
#                       Get-ADUser -Credential $cred -filter "'*'";
#                       """ % {'ad_user': u'some_username',
#                              'ad_password': u'some_kinda_password'},
#                       *args, **kwargs)
