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

The WinRM server has to be set up properly before we could connect to it. See:

    http://msdn.microsoft.com/en-us/library/aa384426.aspx
    http://msdn.microsoft.com/en-us/library/cc251526(v=prot.10).aspx


for more information about WinRM.

"""
import random
import base64
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
    'wsmid': "http://schemas.dmtf.org/wbem/wsman/identity/1/wsmanidentity.xsd",
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
    # Get information, e.g. config
    'get': 'http://schemas.xmlsoap.org/ws/2004/09/transfer/Get',
    # Receive output from a shell
    'receive': 'http://schemas.microsoft.com/wbem/wsman/1/windows/shell/Receive',
    # Send input to stdin
    'send': 'http://schemas.microsoft.com/wbem/wsman/1/windows/shell/Send',
    # Send a signal to a shell, e.g. 'terminate' or 'ctrl_c'
    'signal':  'http://schemas.microsoft.com/wbem/wsman/1/windows/shell/Signal',
    }

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
                self.logger.warn("Server says 500 (Internal Server Error)")
                code, reason, detail = self._parse_errormessage(e)
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

    def _parse_errormessage(self, fp):
        """Parse input data for an error message retrieved from the WinRM
        server. Faults from WinRM contains:

        - Fault code (list of strings): A human semi-readable code pointing on
          what failed, formatted in string. Consists of a "primary" code and
          could also contain subcode(s). Returned in the order of appearance.

        - Reason (list of strings): An short explanation of the error.

        - Detail (list of XXX): More details about the error. This contains more data:

            - Code (int): Could be an internal Win32 error code or an application
              specific code. Search for MS-ERREF to get a list of standard
              codes.

            - Machine (string): The machine where the fault occured.

            - Message (mixed content) [optional]: Different data that gives more
              details about the fault.

        Example on the format of an Fault response:

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

        The envelope should look like:

            <s:Envelope xml:s="http..." 
                        xml:wsa="http..."
                        xml:wsman="http..."
                        ...>
                <s:Header>
                    ...
                </s:Header>
                <s:Body>
                    ...
                </s:Body>
            </s:Envelope>

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

    def _xml_header(self, action, resource='windows/shell/cmd'):
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
          create custom shells. The URL that is used is:

            http://schemas.microsoft.com/wbem/wsman/1/XXX

        - wsman:Selector: wsman:ShellId: The ShellId that the request should be
          executed in/for. Not always used.

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
        @param resource: The resource as specified in wsman:ResourceURI. For
            action types that works with shell and commands, 'windows/shell/cmd'
            or a custom shell could be specified. Other requests could for
            instance set 'config'. The URL that is used:
            http://schemas.microsoft.com/wbem/wsman/1/XXX

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

        uri = self._xml_element('ResourceURI', 'wsman',
                text='http://schemas.microsoft.com/wbem/wsman/1/%s' % resource,
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

        # TODO: how to add 'xml:lang' to elementtree?
        #locale = self._xml_element('Locale', 'wsman', attribs={
        #                                        'xml:lang': 'en-US',
        #                                        's:mustUnderstand': 'false'})
        #header.append(locale)

        timeout = self._xml_element('OperationTimeout', 'wsman',
                                    text='PT120.000S')
        header.append(timeout)

        # Add the Shell ID as a selector, if it exists.
        # TODO: Make this an input argument instead.
        if getattr(self, 'shellid', None):
            selector = self._xml_element('Selector', 'wsman',
                                            text=self.shellid, attribs={'Name':
                                                                    'ShellId'})
            selectors = self._xml_element('SelectorSet', 'wsman')
            selectors.append(selector)
            header.append(selectors)
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
        header = self._xml_header('command')
        options = self._xml_element('OptionSet', 'wsman')
        options.append(self._xml_element('Option', 'wsman', 
                                    attribs={'Name': 'WINRS_CONSOLEMODE_STDIN'},
                                    text='TRUE'))
        # Not necessary as long as we just set the default:
        #options.append(self._xml_element('Option', 'wsman', 
        #                            attribs={'Name': 'WINRS_SKIP_CMD_SHELL'},
        #                            text='FALSE'))
        header.append(options)

        body = self._xml_element('Body', 's')
        cmdline = self._xml_element('CommandLine', 'rsp')
        body.append(cmdline)
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
        body = self._xml_element('Body', 's')
        shell = self._xml_element('Shell', 'rsp', nsmap={'rsp':
                     'http://schemas.microsoft.com/wbem/wsman/1/windows/shell'})
        shell.append(self._xml_element('Lifetime', 'rsp', text='PT120.000S'))
        shell.append(self._xml_element('InputStreams', 'rsp', text='stdin'))
        shell.append(self._xml_element('OutputStreams', 'rsp',
                                       text='stdout stderr'))
        body.append(shell)
        ret = self._http_call(self._xml_envelope(self._xml_header('create'), body))
        # Find the ShellID:
        for event, elem in etree.iterparse(ret.fp,
                    tag='{http://schemas.dmtf.org/wbem/wsman/1/wsman.xsd}Selector'):
            return elem.text 
        raise Exception('Could not Create Shell')

    def wsman_delete(self, shellid):
        """Send a Delete request to the server, to terminate the Shell by the
        given ShellId.

        It is recommended to delete the shell when a job has finished, to free
        up usage on the server. Only a limited number of shells are available
        per user, and old shells could stay idle for quite some time before they
        get deleted.

        """
        # TODO: Make use of the given shellid
        ret = self._http_call(self._xml_envelope(self._xml_header('delete')))
        # TODO: Parse and check reply?

    def wsman_get(self, type='config'):
        """Send a Get request to the server, to get specified information.

        @type type: string
        @param type: The type of information to get.
            TODO: Should be able to specify full URL, or is the last part
            enough? It depends on what URLs that are available...

        @rtype: etree._Element
        @return: The XML returned from the server.
            TODO: Find the body content and return that instead? Or is some
            information in the Header interesting too?

        """
        header = self._xml_header('get', resource=type)
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
        information.

        @rtype: etree._Element
        @return: The Identify response from the server, in SOAP XML format.

        """
        env = self._xml_element('Envelope', 's')
        env.append(self._xml_element('Header', 's'))
        body = self._xml_element('Body', 's')
        body.append(self._xml_element('Identify', 'wsmid'))
        env.append(body)
        ret = self._http_call(env) # , address='/wsman-anon/identify')
        xml = etree.parse(ret.fp)
        return xml

    def wsman_receive(self, shellid, commandid, sequence=0):
        """Send a Recieve request to the server, to get a command's output.

        WinRM's execution of commands works in the way that the command is first
        called by a Command request, which only returns a CommandId, which we
        should then use when sending a Receive request later.

        TODO: Should this method return an iterator instead, so that you could
        see the first output while waiting for the next reply with more data?


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

        @type sequence: int
        @param sequence: Specifies what "page" of the output that should be
            retrieved. This is only needed when command output is so large that
            it can't fit in a single SOAP message, and has to split up in
            several. Starts on 0 and counts upwards.

        @rtype: tuple
        @return: A three element tuple on the form:

                (int:return_code, string:stdout, string:stderr)

            The return code might be None, if not given by the server.

            TODO: Return iterator or something else instead? An object maybe?

        """
        # TODO: Move the loop out of this method. This method should _only_ send
        # the command and return the server response!

        self.log.debug("In shell %s: Get output for command: %s" % (self.shellid,
                                                                   commandid))
        out = {'stdout': [], 'stderr': []}
        exitcode = None
        sequence = 0
        state = 'Running'

        while state != 'Done':
            header = self._xml_header('receive')
            body = self._xml_element('Body', 's')
            receiver = self._xml_element('Receive', 'rsp')
            receiver.set('SequenceId', str(sequence))
            body.append(receiver)
            stream = self._xml_element('DesiredStream', 'rsp')
            stream.set('CommandId', commandid)
            stream.text = 'stdout stderr'
            receiver.append(stream)

            try:
                ret = self._http_call(self._xml_envelope(header, body))
            except urllib2.HTTPError, e:
                print e
                # TODO: Handle it somehow? Return only what has been returned?
                raise

            root = etree.parse(ret.fp)
            tag = "{%s}Stream" % namespaces['rsp']
            amount = 0
            for elem in root.iter(tag=tag):
                if elem.text:
                    amount += len(elem.text)
                    out[elem.get('Name')].append(elem.text)
            self.log.debug("Received %d bytes of base64 data" % amount)

            tag = "{%s}CommandState" % namespaces['rsp']
            for xml_state in root.iter(tag=tag):
                state = xml_state.get('State').split('/')[-1]
                self.log.debug("New state = %s, sequence = %d" % (state, sequence))
                sequence += 1

            tag = "{%s}ExitCode" % namespaces['rsp']
            for code in root.iter(tag=tag):
                exitcode = code.text

            # Tell the server that the reponse was read successfully:
            if state != 'Done':
                self.send_signal(commandid, 'terminate')

            # TODO: the loop doesn't work for now. Need to find out why it only
            # hangs at first round.
            #break

        stdout = ''.join(base64.decodestring(s) for s in out['stdout'])
        stderr = ''.join(base64.decodestring(s) for s in out['stderr'])
        # TODO: Check if the return code has been set?
        return (exitcode, stdout, stderr)

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
        self.log.debug("In shell %s, for CmdID: %s: Sending stdin input: '%s'" %
                       (self.shellid, commandid, data))
        # Need to add carriage return, to simulate Enter in Windows. A simple
        # newline (\n) would not work, carriage return (\r) is required:
        data = data.replace('\n', '\r\n')
        if not data.endswith('\n'):
            data += '\r\n'
        header = self._xml_header('send')
        body = self._xml_element('Body', 's')
        send = self._xml_element('Send', 'rsp')
        send.append(self._xml_element('Stream', 'rsp',
                                      text=base64.encodestring(data),
                                      attribs={'Name': 'stdin',
                                               'CommandId': commandid}))
        body.append(send)
        return self._http_call(self._xml_envelope(header, body))
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
        code.text = 'http://schemas.microsoft.com/wbem/wsman/1/windows/shell/signal/%s' % signal_code
        xml.append(code)
        body.append(xml)
        return self._http_call(self._xml_envelope(self._xml_header('signal'), body))
        # TODO: What to return?

class WinRMClient(WinRMProtocol):
    """Client that talks with a service through the WinRM protocol.

    The standard workflow when communicating with a WinRM server is:

        1. Send Create request to create a Shell on the server. A ShellId is
           returned.
        2. Send Command request to start a new command in the given Shell. A
           CommandID is returned.
        3. If needed, you could send a Send request to send input to stdin.
           Could be used to e.g. fill in prompts.
        4. If you want to, you could now wait and do something else. The server
           is processing the command and caching the output.
        5. Send Receive request to receive the output from the command.
        6. Send Signal request to tell the server that the output was received.
        7. Repeat step 5-6 until CommandState is Done 
        8. Send and receive more commands if needed.
        9. Send Delete request to shut down the given Shell when done.

    """

    # TODO:
    #def __init__(self):
    #   self.shellid = None

    def connect(self):
        """Set up a connection to the WinRM server.

        TODO: should we handle reconnects? Shells could be running on the
        server, and we have request types to get them.

        """
        self.logger.debug("Connecting to WinRM: %s:%s" % (self.host, self.port))
        self.shellid = self.wsman_create()

        # Subclasses could now run some startup commands on the server, e.g.
        # starting powershell in the active shell and import the ActiveDirectory
        # module. Example:
        #   commandid = self.wsman_command(self.shellid, "powershell")
        return True 

    def run(self, *args):
        """Send commands to the server, and get their response. TODO"""
        pass
