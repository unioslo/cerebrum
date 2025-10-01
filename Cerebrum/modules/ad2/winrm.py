# -*- coding: utf-8 -*-
#
# Copyright 2012-2024 University of Oslo, Norway
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
"""
Windows Remote Management (WinRM) client.

WinRM is a protocol for communicating with Windows machines (servers) to get
and set differents kinds of information.  WinRM is Microsoft's version of
WS-Man, which is based on SOAP and uses a bunch of XML, SOAP, and WS
definitions.

Our focus is to use WinRM to execute commands on the server side, in order
to manage Active Directory.

The WinRM server has to be set up properly before we can connect to it.  For
more information about WinRM, see:

- <http://msdn.microsoft.com/en-us/library/aa384426.aspx>
- <http://msdn.microsoft.com/en-us/library/cc251526(v=prot.10).aspx>

"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import base64
import io
import json
import logging
import re
import socket
import warnings
import uuid

import six
from lxml import etree
from six.moves.urllib import request as urllib_request
from six.moves.urllib import error as urllib_error

from Cerebrum.utils import http as http_utils
from Cerebrum.utils import mime_type
from Cerebrum.utils import text_compat

logger = logging.getLogger(__name__)

# Extra loggger for debugging winrm traffic.  This logger is disabled by
# default, but can be enabled by logger config.
#
# - INFO:  Logs info on each request and response to/from winrm
# - DEBUG: Logs potentially secret or sensitive values to/from winrm
#
debug_log = logger.getChild("debug")
debug_log.propagate = False
debug_log.addHandler(logging.NullHandler())


#
# XML/SOAP/WS-Man helpers
#

# XML namespaces that are used by the the WinRM SOAP envelope
NAMESPACES = {
    'cfg': "http://schemas.microsoft.com/wbem/wsman/1/config",
    'rsp': "http://schemas.microsoft.com/wbem/wsman/1/windows/shell",
    's': "http://www.w3.org/2003/05/soap-envelope",
    'wsa': "http://schemas.xmlsoap.org/ws/2004/08/addressing",
    'wsman': "http://schemas.dmtf.org/wbem/wsman/1/wsman.xsd",
    'wsen': "http://schemas.xmlsoap.org/ws/2004/09/enumeration",
    'wsmid': "http://schemas.dmtf.org/wbem/wsman/identity/1/wsmanidentity.xsd",
    'xml': "http://www.w3.org/XML/1998/namespace",
}


# WS-Man action types that is available for the server
_ACTION_CREATE = (
    # create (shell)
    "http://schemas.xmlsoap.org/ws/2004/09/transfer/Create"
)
_ACTION_DELETE = (
    # delete (shell)
    "http://schemas.xmlsoap.org/ws/2004/09/transfer/Delete"
)
_ACTION_CMD = (
    # run windows (shell) command
    "http://schemas.microsoft.com/wbem/wsman/1/windows/shell/Command"
)
_ACTION_ENUM = (
    # Enumerate/list information
    "http://schemas.xmlsoap.org/ws/2004/09/enumeration/Enumerate"
)
_ACTION_GET = (
    # Get information, e.g. config
    "http://schemas.xmlsoap.org/ws/2004/09/transfer/Get"
)
_ACTION_PULL = (
    # Pull information from the server
    "http://schemas.xmlsoap.org/ws/2004/09/enumeration/Pull"
)
_ACTION_SEND = (
    # Send input to shell stdin
    "http://schemas.microsoft.com/wbem/wsman/1/windows/shell/Send"
)
_ACTION_RECV = (
    # Receive output from shell
    "http://schemas.microsoft.com/wbem/wsman/1/windows/shell/Receive"
)
_ACTION_SIGNAL = (
    # Send a signal to a shell, e.g. 'terminate' or 'ctrl_c'
    "http://schemas.microsoft.com/wbem/wsman/1/windows/shell/Signal"
)

_ACTION_TYPES = (
    _ACTION_CREATE, _ACTION_DELETE, _ACTION_CMD, _ACTION_ENUM, _ACTION_GET,
    _ACTION_PULL, _ACTION_SEND, _ACTION_RECV, _ACTION_SIGNAL,
)


def format_name(name, namespace=None):
    """
    Format a namespaced tag name or attribute name.

    >>> format_name("Foo")
    "Foo"
    >>> format_name("Foo", "xml")
    "{http://www.w3.org/XML/1998/namespace}Foo",
    >>> format_name("xml:Foo")
    "{http://www.w3.org/XML/1998/namespace}Foo",

    See :const:`.NAMESPACES` for a list of available namespaces.

    This is done because we don't provide a namespace mapping when creating
    individual elements.  Note that the final xml will turn these back into
    prefixed format if provided with a namespace mapping.
    """
    if namespace is None and not name.startswith("{"):
        parts = name.split(':', 1)
        if len(parts) == 2:
            namespace, name = parts
    if namespace is not None:
        name = '{%s}%s' % (NAMESPACES[namespace], name)
    return name


def format_bool(value):
    """ Format a boolean XML text value. """
    return "TRUE" if value else "FALSE"


def create_xml_element(tag, attrs=None, text=None, nsmap=None):
    """
    Create a single XML element.

    :param str tagname:
        Element name/tag.

    @param str ns:
        One of the namespaces in :const:`.NAMESPACES`.

    :param attrs:
        A dict-like mapping of element attributes.

    @param str text:
        Element text content.

    :param dict nsmap:
        XML namespace mapping to place in this element.

        This is typically only required for some parent elements, as namespaces
        are inherited.  This is typically (a subset of) :const:`.NAMESPACES`.

    :rtype: lxml.etree.ElementBase
    :returns: A new XML Element
    """
    tag = format_name(tag)
    attrs = {format_name(k): v for k, v in (attrs or {}).items()}

    element = etree.Element(tag, attrs, nsmap=nsmap)
    if text is not None:
        element.text = text
    return element


def create_wsman_selector(name, value):
    """ Format a wsman:Selector element. """
    return create_xml_element(
        "wsman:Selector",
        attrs={'Name': name},
        text=value,
    )


def create_wsman_option(name, value):
    """ Format a wsman:Option element. """
    return create_xml_element(
        "wsman:Option",
        attrs={'Name': name},
        text=value,
    )


def create_soap_header(to, action, resource_uri, timeout,
                       options=None, selectors=None):
    """
    Create an XML header for a given request action.

    WinRM makes use of a lot of different xml schemas and standards,  e.g.
    WS-Addressing and WS-Management.  The Header element tree returned from
    this method can contain most of those settings.

    :param str to:
        Recipient of this request.  Usually the same value as the endpoint URL
        for the request.

    :param str action:
        URI to the action type for this request.

    :param str resource_uri:
        URI to the resource for this request.

    :param int timeout:
        Connection timeout (in seconds).

    :param options:
        A sequence of wsman:Option elements.

    :param selectors:
        A sequence of wsman:Selector elements.

    :rtype: lxml.etree.ElementBase
    :returns:
        A SOAP Header element with the proper settings to be
        understood by the WinRM server.
    """
    message_id = "uuid:" + text_compat.to_text(uuid.uuid4())
    operation_timeout = iso8601_duration(seconds=int(timeout))
    options = list(options) if options else []
    selectors = list(selectors) if selectors else []

    if action not in _ACTION_TYPES:
        raise ValueError("unknown action: " + repr(action))

    header = create_xml_element("s:Header")

    # wsa:To - recipient address for this request
    header.append(create_xml_element("wsa:To", text=to))

    # wsa:ReplyTo > wsa:Address - we set this to anonymous, as we get an
    # immediate reply through the http response
    reply_to = create_xml_element("wsa:ReplyTo")
    reply_to.append(
        create_xml_element(
            "wsa:Address",
            attrs={"s:mustUnderstand": 'true'},
            text=(
                "http://schemas.xmlsoap.org/"
                "ws/2004/08/addressing/role/anonymous"
            ),
        )
    )
    header.append(reply_to)

    # wsman:ResourceURI - the wsman resource type that we're acting on
    header.append(
        create_xml_element(
            "wsman:ResourceURI",
            attrs={"s:mustUnderstand": "true"},
            text=resource_uri,
        )
    )

    # wsa:Action - The action type for this request - see _ACTION_TYPES
    header.append(
        create_xml_element(
            "wsa:Action",
            text=action,
            attrs={"s:mustUnderstand": "true"},
        )
    )

    # wsman:MaxEnvelopeSize - max size of response envelopes.
    #
    # If the response gets bigger than this, it gets split up into
    # multiple envelopes.  Must be a multiple of 1024.
    header.append(
        create_xml_element(
            "wsman:MaxEnvelopeSize",
            text="3073741824",
            attrs={"s:mustUnderstand": "true"},
        )
    )

    # wsa:MessageID - A random string with a unique Id of this message.
    header.append(
        create_xml_element(
            "wsa:MessageID",
            text=message_id,
        )
    )

    # wsman:Locale - language to use in responses, including faults and
    # error messages.
    header.append(
        create_xml_element(
            "wsman:Locale",
            attrs={
                "xml:lang": "en-US",
                "s:mustUnderstand": "false",
            },
        )
    )

    # wsman:OperationTimeout - a connection timeout for producing a
    # response.  This is affects the server connection, does not override
    # e.g. the lifetime for a shell resource.
    header.append(
        create_xml_element(
            "wsman:OperationTimeout",
            text=operation_timeout,
        )
    )

    # wsman:SelectorSet of wsman:Selector - scope the request action.
    #
    # Some actions require a selector, others don't allow them at all.
    # Selector effect depends on the type of action:
    #
    # - For command, this selects the wsman:ShellId to run the command in
    # - For Get, this selects the type of information to look up
    #
    if selectors:
        selector_set = create_xml_element("wsman:SelectorSet")
        for s in selectors:
            selector_set.append(s)
        header.append(selector_set)

    # wsman:OptionSet of wsman:Option - additional settings for the request
    #
    # Typically used to set server behaviour for a given request and action
    if options:
        option_set = create_xml_element("wsman:OptionSet")
        for opt in options:
            option_set.append(opt)
        header.append(option_set)

    return header


def create_soap_envelope(header, body=None):
    """
    Create the XML element tree for SOAP requests.

    This simply wraps a SOAP header and an optional SOAP body in a SOAP
    envelope with the relevant namespace prefixes.
    ::

        <s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
                    xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing"
                    xmlns:wsman="http://schemas.dmtf.org/wbem/wsman/1/wsman.xsd"
                    ...>
            <s:Header> ... </s:Header>
            <s:Body> ... </s:Body>
        </s:Envelope>

    :type header: lxml.etree.ElementBase
    :param header: The SOAP request header element

    :type body: lxml.etree.ElementBase
    :param body: An optional element for the request body.

    :rtype: lxml.etree.ElementBase
    :returns:
        The request header and body wrapped in a SOAP Envelope element with
        namespace mappings.
    """
    envelope = create_xml_element("s:Envelope", nsmap=NAMESPACES)
    envelope.append(header)
    if body is None:
        body = create_xml_element("s:Body")
    envelope.append(body)
    return envelope


def xml_to_bytes(root_element, encoding):
    """ Turn an xml element into a bytestring xml document. """
    root = etree.ElementTree(root_element)
    xml_buffer = io.BytesIO()
    root.write(xml_buffer, encoding=encoding, xml_declaration=True)
    return xml_buffer.getvalue()


def format_basic_auth(username, password, charset="UTF-8"):
    """
    Format a basic auth Authorization header value

    Legacy Basic Auth (RFC-2617), doesn't specify any charset, as usernames and
    passwords are byte-values.  Modern Basic Auth (RFC-7617) specifies that
    UTF-8 is the only "correct" charset (at least for challenges).  If this is
    correct for Active Directory remains to be seen.  These values are probably
    just ascii chars anyway.
    """
    plaintext = ":".join((username, password))
    cred = base64.b64encode(text_compat.to_bytes(plaintext, encoding=charset))
    return "Basic " + text_compat.to_text(cred, encoding="ascii")


def escape_to_string(data):
    """
    Prepare data to be used in powershell commands.

    The data should be escaped to avoid parsing errors in powershell, and
    to avoid injections.

    Documentation about escaping in powershell:

        http://www.rlmueller.net/PowerShellEscape.htm

    The main escaping rules in powershell are that single quoted strings
    (those put inside ') does only treat the single quote as a special
    character.  Other characters like $ and { are treated as normal
    characters.  The single quote should be escaped by another single quote.

    Examples:

        testing testing         -> 'testing testing'
        Mc'Donalds'             -> 'Mc''Donalds'''

    Lists are transformed into:

        "val1","val2","val3","val4",...

    A dict will be transformed into the string:

        @{'key1'='value1';'key2'='value2a','value2b';...}

        Empty strings must be converted to $false.

    :param data:
        The data that should be escaped to be usable in powershell.

    :returns str:
        A string that could be used in powershell commands directly.
    """
    # TODO/TBD:
    #   - Is this correct?
    #   - How about other special characters, like \n?
    #   - Does powershell escape '? Would it for instance be possible to end
    #     a string with \\, and then escape the '?
    #   - How about two single quotes, is the result '''' usable?
    if data is None:
        return '$false'
    if isinstance(data, bool):
        if data:
            return '$true'
        else:
            return '$false'
    if isinstance(data, six.integer_types):
        return six.text_type(data)
    if isinstance(data, float):
        return "'%f'" % data
    if isinstance(data, bytes):
        # Further processing as text
        data = data.decode("utf-8")
    if isinstance(data, six.text_type):
        # TODO: more that should be removed from strings?
        data = data.replace('\0', '')
        if data == '':
            return '$false'
        else:
            return "'%s'" % data.replace("'", "''")
    if isinstance(data, (tuple, list, set)):
        return ','.join(escape_to_string(s) for s in data)
    if isinstance(data, dict):
        # Dicts are returned as "Hash Tables" for powershell
        ret = []
        for k, v in sorted(six.iteritems(data)):
            k, v = escape_to_string(k), escape_to_string(v)
            if not k or not v:
                logger.warning("escape_to_string(): Omitting empty value "
                               "in hash table: k=%s, v=%s", repr(k), repr(v))
                continue
            ret.append('%s=%s' % (k, v))
        return '@{%s}' % ';'.join(ret)
    raise TypeError("No support for values of type: %s (%s)" %
                    (type(data), repr(data)))


def parse_winrm_fault(fp):
    """
    Parse a SOAP Fault response from winrm.

    Faults from WinRM contains:

    Fault code (list of strings):
        A human semi-readable code pointing to where something has failed,
        formatted in string. Consists of a "primary" code and could also
        contain subcode(s). Returned in the order of appearance, supposedly.

    Reason (list of strings):
        An short explanation of the error.

    Detail (list of mixed content):
        More details about the error. This contains more data, and could give
        you more help about fixing the fault:

        Code (int):
            Could be an internal Win32 error code or an application specific
            code. Search for MS-ERREF to get a list of standard codes.

        Machine (string):
            The machine where the fault occured.

        Message (mixed content) [optional]:
            Different data that gives more details about the fault.

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
          <f:WSManFault
                xmlns:f="http://schemas.microsoft.com/wbem/wsman/1/wsmanfault"
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
    tag = format_name("Fault", "s")
    for event, elem in etree.iterparse(fp, tag=tag):
        for elecode in elem.iter(tag=format_name("Code", "s")):
            codes.extend(
                ele.text
                for ele in elecode.iter(tag=format_name("Value", "s"))
            )
        for elereas in elem.iter(tag=format_name("Reason", "s")):
            reason.extend(r.text for r in elereas.iterchildren())
        details.extend(elem.iter(tag=format_name("Detail", "s")))
    return (
        codes,
        reason,
        tuple(etree.tostring(e, pretty_print=True) for e in details),
    )


def dechunk_wsman_response(chunks, charset):
    """ Join and decode a chunked base64 response. """
    # PY2/3 - each chunk is always a base64 text, as a native str
    plain_chunks = [
        base64.b64decode(text_compat.to_bytes(chunk, "ascii"))
        for chunk in chunks
    ]
    bytestring = b"".join(plain_chunks)
    plaintext = bytestring.decode(charset)
    return plaintext.replace("\r", "")


def prepare_wsman_input(data, charset):
    """ Prepare stdin-like input for wsman command. """
    if isinstance(data, (tuple, list)):
        text = "\n".join(text_compat.to_text(d) for d in data)
    else:
        text = text_compat.to_text(data)

    # Need to add carriage return, to simulate Enter in Windows. A simple
    # newline (\n) would not work, carriage return (\r) is required:
    text = text.replace("\n", "\r\n")
    if not text.endswith("\n"):
        text += "\r\n"

    return text_compat.to_text(base64.b64encode(text.encode(charset)), "ascii")


def iso8601_duration(seconds=None, minutes=None, hours=None):
    """ Simple ISO-8601 duration formatter. """
    # Note - No validation - caller should ensure that no single value exceeds
    # the maximum (e.g. no more than 59 minutes)
    ret = ['PT']
    if hours:
        ret.append('%dH' % int(hours))
    if minutes:
        ret.append('%dM' % int(minutes))
    if seconds:
        ret.append('%.3fS' % int(seconds))
    return ''.join(ret)


class WinRMException(Exception):
    """
    Generic exception for all WinRM errors.

    This should be the superclass for all the various exceptions when
    communicating with WinRM, whether it is Powershell or AD that syas no.
    """
    pass


class WinRMServerException(WinRMException):
    """
    Exception for HTTP 500 Server Errors.

    The WinRM standard way of saying that something failed, and it's either an
    unknown error or something the client have done wrong.
    """
    def __init__(self, code, reason, details=None):
        super(WinRMServerException, self).__init__(code, reason, details)
        self.code = code
        self.reason = reason
        self.details = details


class WinRMAuthenticationException(WinRMException):
    """
    Exception for if the mutual authentication fails.

    We are creating our own exception type for this, to avoid the problem that
    python2.5 does not have the ssl module. By using this exception, we could
    use it for 2.5 and newer versions.

    There are many scenarios that could go wrong in the authentication process:

    - The server is not registered with a certificate at all.

    - The server certificate is not signed by any CA certificate we have
      registered as authoritative for this use.

    - The hostname in the server's certificate is not the same as the URL that
      we connect to.

    - The client is not registered with a proper certificate.

    - The client's certificate is not accepted by the server.
    """
    pass


class ExitCodeException(WinRMException):
    """
    This is raised when a command returns an exitcode that is not 0.

    All commands sent through WinRM returns with an exitcode. Only 0 is
    considered as success, other values are considered as errors. The value
    could say something about what failed for the command, but the meaning of
    the exitcode value differs from command to command.
    """
    def __init__(self, exitcode, stderr, output=None, msg=None):
        """Initiate exception for command with exitcode other than 0.

        :type exitcode: int or str
        :param exitcode: The command's exitcode.

        :param str stderr: The stderr message for the command.

        :param dict output:
            All output from the command. It might include the stderr output
            too, even if that must be present in the L{stderr} argument.

        :param str msg:
            If you want to specify the message that is printed for the
            exception.  Defaults to a generic "command failed" message.

        """
        self.exitcode = exitcode
        self.stderr = stderr
        self.output = output
        if msg is None:
            msg = 'Command failed: exitcode: %s, stderr: %s' % (exitcode,
                                                                stderr)
        super(ExitCodeException, self).__init__(msg)


class PowershellException(ExitCodeException):
    """
    Exception that tells you that some powershell code failed.

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
                r"(?P<first_error>[\w\s\-'.]+)[+\s]+CategoryInfo[\s:]+"
                r"(?P<second_error>\w+):\s+\("
                r"(?P<args>[\w\-:]+)\)\s+\["
                r"(?P<command>[\w\s-]+)\].*",
                stderr,
                re.MULTILINE)
        else:
            m = None
        if msg is not None:
            r_msg = msg
        elif m:
            gd = m.groupdict()
            cmd = re.sub(r'\s', '', gd.get('command'))
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
    """
    The protocol for sending SOAP requests to the WinRM server.

    Methods for sending different call types, like Get, Execute and Send, are
    available, but more advanced functionality should not be put in this class.
    The ShellId is for example only returned from the server, but how to use it
    should be done by subclasses.

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
    _winrm_encoding = 'UTF-8'
    _winrm_codepage = '65001'

    def __init__(self, host='localhost', port=None, encrypted=True,
                 logger=None, ca=None, client_key=None, client_cert=None,
                 check_name=True):
        """
        Set up the basic configuration.

        Fill the HTTP headers and set the correct port if not given.

        :param str host:
            The hostname

        :type port: string or int
        :param port:
            The port to use. Defaults to integers in L{self._default_ports},
            5986 for encrypted and 5985 for unencrypted communication.

        :param bool encrypted:
            If the communication should go encrypted. It should!

        :type logger: CerebrumLogger
        :param logger: Cerebrum's logger to log to.

        :param str ca:
            Absolute path to a CA certificate file.

        :param str client_key:
            Absolute path to a file with the client's private key for use with
            client authentication.  The client key and cert could be in the
            same file.

        :param str client_cert:
            Absolute path to a file with the client certificate
            (for client authentication).

        :param bool check_name:
            Enable hostname validation (if encrypted).
        """
        # TODO: How should we handle no logger?
        self.logger = logger
        self.host = host
        self.encrypted = bool(encrypted)
        if not self.encrypted:
            self.logger.warning("Unencrypted communication with WinRM")
        if port:
            self.port = port
        else:
            self.port = self._default_ports[0]
            if not self.encrypted:
                self.port = self._default_ports[1]
        if encrypted:
            from Cerebrum import https

            ssl_config = https.SSLConfig()
            ssl_config.set_ssl_version(https.SSLConfig.TLSv1_2)

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
            self._opener = urllib_request.build_opener(
                https.HTTPSHandler(ssl_connection=conn))
        else:
            socket.setdefaulttimeout(self.connection_timeout)
            self._opener = urllib_request.build_opener()

        self._http_headers = {
            'Host': '%s:%s' % (self.host, self.port),
            'Accept': '*/*',
            'Content-Type': mime_type.format_mime_type(
                "application", "soap+xml",
                {'charset': self._winrm_encoding},
            ),
            'User-Agent': self._useragent,
        }
        self.logger.debug("WinRMProtocol: init done")

    @property
    def xmlparser(self):
        # Set up the XML parser to expect input in utf-8
        # TODO: Do we need this? The xml documents *should* contain encoding.
        return etree.XMLParser(encoding=self._winrm_encoding)

    def _http_url(self, sub=''):
        """Return a string with the HTTP URL of the service."""
        proto = "https" if self.encrypted else "http"
        if not sub.startswith('/'):
            sub = '/%s' % (sub,)
        url = '%s://%s:%s%s' % (proto, self.host, self.port, sub)
        return url

    def add_credentials(self, username, password):
        """Set the credentials to give to the server for authentication."""
        self._username = username
        self._http_headers = http_utils.merge_headers(
            self._http_headers,
            {'Authorization': format_basic_auth(username, password)},
        )

    def _http_call(self, xml, address='/wsman', headers=None):
        """
        Send an HTTP call with the given XML-data to the WinRM server.

        Send a call to the server. The given message should be a string or
        instance with XML data to be sent. The returned object is an urllib
        response instance. Interesting variables are ret.headers and ret.fp.

        :type xml: lxml.etree.ElementTree
        :param xml:
            The XML that should be sent to the server. Should be valid SOAP
            data that the server could understand.

        :param str address:
            The HTTP address to where the data should go on the server.

            The WinRM specification gives '/wsman' as the default, but other
            addresses could be used for separate behaviour, e.g.
            '/wsman-anon/identify' for identifying servers (from the WSMan
            spec).

        :returns:
            An urrlib response object.

            Interesting attributes are ret.headers, ret.fp and ret.code.

        :raises WinRMServerException: For HTTP 500 Server Errors
        :raises HTTPError: When other, unhandled errors arrive.
        :raises URLError: When the server connection fails.
        :raises socket.timeout: When the socket connection times out.
        """
        xml = xml_to_bytes(xml, self._winrm_encoding)
        url = self._http_url(address)
        headers = http_utils.merge_headers(self._http_headers, headers)
        req = urllib_request.Request(url, xml, headers)
        try:
            ret = self._opener.open(req)
        except urllib_error.HTTPError as e:
            if e.code == 401:  # Unauthorized
                self.logger.debug("Server says 401 Unauthorized")
                self.logger.warning("No known server auth method: %s" %
                                    e.hdrs.get('www-authenticate', None))
                raise
            elif e.code == 500:
                code, reason, detail = parse_winrm_fault(e)
                raise WinRMServerException(code, reason, detail)
            self.logger.warning("Server http error, code=%r: %s",
                                e.code, e.msg)
            self.logger.warning("Server headers: %s",
                                str(e.hdrs).replace('\r\n', ' | '))
            raise
        except socket.timeout as e:
            self.logger.warning("Socket timeout when connecting to %s: %s",
                                repr(url), e)
            raise
        except urllib_error.URLError as e:
            self.logger.warning("Connection error: %s", e.reason)
            raise
        return ret

    # XML generating

    def _xml_header(self, action, resource='windows/shell/cmd',
                    selectors=None, options=None):
        """ Create an XML request header for a given request type. """
        if not resource.startswith('http'):
            # e.g.: http://schemas.microsoft.com/wbem/wsman/1/windows/shell/cmd
            resource_uri = (
                "http://schemas.microsoft.com/wbem/wsman/1/" + resource
            )
        else:
            resource_uri = resource

        return create_soap_header(
            to=self._http_url('wsman'),
            action=action,
            resource_uri=resource_uri,
            timeout=self.request_timeout,
            selectors=selectors,
            options=options,
        )

    #
    # WS-Man Windows Shell Command (and settings)
    #
    # WINRS_CONSOLEMODE_STDIN:
    #     If input from wsman_send should go directly to the console (True) or
    #     through pipes (False).  The purpose is to support input through stdin
    #     to a command.  Note that we have trouble sending stdin to Powershell
    #     2.0, so we have to set this to True to avoid that a command hangs,
    #     waiting for input that we can't send.  This might be fixed in later
    #     Powershell versions.
    _winrs_consolemode_stdin = True

    # WINRS_SKIP_CMD_SHELL:
    #     If a command that is sent to WinRS should be executed inside of
    #     `cmd.exe` shell (False), or not (True).
    #     If True, i.e. skip cmd.exe shell, the first argument must be an
    #     absolute path to an executable file to run,  like `powershell.exe`.
    #     Note that there is a limit on the full input length of the command,
    #     which is 8191 (http://support.microsoft.com/kb/830473), and you will
    #     in need to escape strings both for the regular shell and for
    #     Powershell, if that is to be used.
    _winrs_skip_cmd_shell = True

    def format_wsman_request_command(self, shell_id, argv):
        r"""
        Format request for :meth:`.wsman_command`.

        Example:
        ::

          <s:Body>
            <rsp:CommandLine
                xmlns:rsp="http://schemas.microsoft.com/wbem/wsman/1/windows/shell">
              <rsp:Command>del</rsp:Command>
              <rsp:Arguments>/p</rsp:Arguments>
              <rsp:Arguments>d:\temp\out.txt</rsp:Arguments>
            </rsp:CommandLine>
          </s:Body>
        """
        # Support sending blank/noop commands
        argv = tuple(argv) if argv else (None,)
        header = self._xml_header(
            _ACTION_CMD,
            selectors=[
                create_wsman_selector("ShellId", shell_id),
            ],
            options=[
                create_wsman_option(
                    "WINRS_CONSOLEMODE_STDIN",
                    format_bool(self._winrs_consolemode_stdin),
                ),
                create_wsman_option(
                    "WINRS_SKIP_CMD_SHELL",
                    format_bool(self._winrs_skip_cmd_shell),
                ),
            ],
        )
        body = create_xml_element("s:Body")
        cmdline = create_xml_element("rsp:CommandLine")
        cmdline.append(create_xml_element("rsp:Command", text=argv[0]))
        for arg in argv[1:]:
            cmdline.append(create_xml_element("rsp:Arguments", text=arg))
        body.append(cmdline)
        return create_soap_envelope(header, body)

    def wsman_command(self, shell_id, *argv):
        r"""
        Send a Command request to the server, to execute the given command(s).

        Commands are run in the shell identified by *shellid*, so you have to
        set this up first.  The specification allows you to send an empty
        command, e.g. to clean up any temporary locks.

        :param str shell_id:
            ShellId of an existing shell to run command(s) in.

        :param *argv:
            Argument vector to run (i.e. command and arguments).

            The argument vector is sent as-is, and all items must be unicode
            strings.

        :returns str:
            CommandId of the running command.

            This is typically used in a Receive request to get the output from
            the command, but you are allowed to do something else before
            getting the output.
        """
        request = self.format_wsman_request_command(shell_id, argv)

        debug_log.info("WS-Man Command start (shell-id=%s)", repr(shell_id))
        debug_log.debug("Running command in shell=%s: %s",
                        repr(shell_id), repr(argv))
        ret = self._http_call(request)
        debug_log.info("WS-Man Command done (shell-id=%s)", repr(shell_id))

        tag = format_name("CommandId", "rsp")
        for event, elem in etree.iterparse(ret.fp, tag=tag):
            logger.info("created command-id: %s", repr(elem.text))
            return elem.text
        raise Exception('Did not receive CommandID')

    #
    # WS-Man Create (shell)
    #

    def format_wsman_request_create(self):
        r"""
        Format request for :meth:`.wsman_create`.

        Example:
        ::

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
            <rsp:WorkingDirectory>d:\\windows</rsp:WorkingDirectory>
            <rsp:Lifetime>PT1000.000S</rsp:Lifetime>
            <rsp:InputStreams>stdin</rsp:InputStreams>
            <rsp:OutputStreams>stdout stderr</rsp:OutputStreams>
          </rsp:Shell>
        </s:Body>
        """
        header = self._xml_header(
            _ACTION_CREATE,
            options=[
                # We don't need a profile for now, will only take longer
                # execution time
                create_wsman_option(
                    "WINRS_NOPROFILE",
                    format_bool(True),
                ),
                # The codepage sets what encoding to use for output. For more
                # info, see <http://msdn.microsoft.com/en-us/library/windows/
                # desktop/dd317756%28v=vs.85%29.aspx>
                create_wsman_option(
                    "WINRS_CODEPAGE",
                    self._winrm_codepage,
                ),
            ],
        )
        body = create_xml_element("s:Body")
        shell = create_xml_element(
            "rsp:Shell",
            nsmap={'rsp': NAMESPACES['rsp']},
        )
        shell.append(
            create_xml_element(
                "rsp:Lifetime",
                text=iso8601_duration(seconds=self.shell_lifetime),
            )
        )
        shell.append(
            create_xml_element(
                "rsp:InputStreams",
                text="stdin",
            )
        )
        shell.append(
            create_xml_element(
                "rsp:OutputStreams",
                text="stdout stderr",
            )
        )
        body.append(shell)
        return create_soap_envelope(header, body)

    def wsman_create(self):
        """
        Send a Create request to the server, asking it to create a new Shell.

        The shell could later be used to execute commands.

        :returns str:
            The ShellId that identifies the newly created Shell. This should be
            used further to execute commands inside the Shell.
        """
        request = self.format_wsman_request_create()

        debug_log.info("WS-Man Create start")
        ret = self._http_call(request)
        debug_log.info("WS-Man Create done")

        # Find the ShellID:
        for event, elem in etree.iterparse(ret.fp,
                                           tag=format_name("Selector",
                                                           "wsman")):
            logger.info("created shell-id: %s", repr(elem.text))
            return elem.text
        raise Exception('Did not receive ShellId from server')

    #
    # WS-Man Delete (shell)
    #

    def format_wsman_request_delete(self, shell_id):
        """ Format request for :meth:`.wsman_delete`. """
        header = self._xml_header(
            _ACTION_DELETE,
            selectors=[
                create_wsman_selector("ShellId", shell_id),
            ],
        )
        return create_soap_envelope(header, None)

    def wsman_delete(self, shell_id):
        """
        Send a Delete request to terminate a Shell with the given given id.

        It is recommended to delete the shell when a job has finished, to free
        up usage on the server. Only a limited number of shells are available
        per user, and old shells could stay idle for quite some time before
        they get deleted, depending on the settings.
        """
        request = self.format_wsman_request_delete(shell_id)
        debug_log.info("WS-Man Delete start (shell-id=%s)", repr(shell_id))
        self._http_call(request)
        debug_log.info("WS-Man Delete done (shell-id=%s)", repr(shell_id))
        # No need to parse the reply, exceptions are thrown by HTTP error codes
        # and raised by _http_call
        return True

    #
    # WS-Man Enumerate
    #

    def format_wsman_request_enumerate(self, resource, selector):
        r"""
        Format request for :meth:`.wsman_enumerate`.

        Example (content of <s:Body/>:
        ::

          <wsen:Enumerate>
            <!-- Where to send EnumerationEnd messages if unexpectedly
                 terminated. Is optional. -->
            <wsen:EndTo>endpoint-reference</wsen:EndTo> ?
            <!-- For how long until timeout. If not specified, set to
                 infinite, which might not be accepted by the endpoint -->
            <wsen:Expires>[xs:dateTime | xs:duration]</wsen:Expires>
            <wsen:Filter Dialect="xs:anyURI"> xs:any </wsen:Filter>
          </wsen:Enumerate>
        """
        selectors = []
        if selector:
            selector = dict(selector)
            text = selector.pop('text', "")
            selectors.append(
                create_xml_element(
                    "wsman:Selector",
                    attrs=selector,
                    text=text,
                )
            )

        header = self._xml_header(
            _ACTION_ENUM,
            resource=resource,
            selectors=selectors,
        )
        body = create_xml_element("s:Body")
        body.append(create_xml_element("wsen:Enumerate"))
        return create_soap_envelope(header, body)

    def wsman_enumerate(self, resource='config', selector=None):
        """
        Send an Enumerate request to get a list of specified information.

        :param str resource:
            The resource identifier (URI) of what information to enumerate. It
            should either start with http or be relative to:

                http://schemas.microsoft.com/wbem/wsman/1/

            Examples on valid resources:

                'config'
                'windows/shell'

        :param dict selector:
            The parameters of a selector for the enumerate request. Should be a
            dict which contains the attributes of the selector. Some usable
            attribute names:

             - Name: The name of the selector, used to target what to select
             - text: The value of the selection.

        :returns str:
            Id of the EnumerateResponse.

            This should be used to get the output from the enumerate request
            through L{wsman_pull}. You might want to do something else while
            waiting, as it might take a while to process, depending on what you
            requested.
        """
        request = self.format_wsman_request_enumerate(resource, selector)

        debug_log.info("WS-Man Enumerate start (resource=%s)", repr(resource))
        ret = self._http_call(request)
        debug_log.info("WS-Man Enumerate done (resource=%s)", repr(resource))

        tag = format_name("wsen:EnumerationContext")
        for event, elem in etree.iterparse(ret.fp, tag=tag):
            return elem.text
        raise Exception("Unknown Enumeration response for resource="
                        + repr(resource))

    #
    # WS-Man Get
    #

    def format_wsman_request_get(self, resource, selector):
        """ Format request for :meth:`.wsman_get`. """
        selectors = []
        if selector:
            selector = dict(selector)
            text = selector.pop('text', "")
            selectors.append(
                create_xml_element(
                    "wsman:Selector",
                    attrs=selector,
                    text=text,
                )
            )
        header = self._xml_header(
            _ACTION_GET,
            resource=resource,
            selectors=selectors,
        )
        return create_soap_envelope(header, None)

    def wsman_get(self, resource='config', selector=None):
        """
        Send a Get request to get specified information.

        :param str resource:
            The type of information to get. Could start with http, or it could
            be relative to:

                http://schemas.microsoft.com/wbem/wsman/1/

        :param dict selector:
            The parameters of a selector for the enumerate request. Should be a
            dict which contains the attributes of the selector. Some usable
            attribute names:

             - Name: The name of the selector, used to target what to select
             - text: The value of the selection.

        :rtype: lxms.etree.ElementBase
        :returns:
            The XML returned from the server.

            TODO: Find the body content and return that instead? Or is some
            information in the Header interesting too?
        """
        request = self.format_wsman_request_get(resource, selector)
        debug_log.info("WS-Man Get start (resource=%s)", repr(resource))
        ret = self._http_call(request)
        debug_log.info("WS-Man Get done (resource=%s)", repr(resource))
        return etree.parse(ret.fp, parser=self.xmlparser)

    #
    # WS-Man Identify
    #

    def format_wsman_request_identify(self):
        """ Format request for :meth:`.wsman_identify`. """
        # Note: Not our regular WS-Man header - this one is empty!
        header = create_xml_element("s:Header")
        body = create_xml_element("s:Body")
        body.append(create_xml_element("wsmid:Identify"))
        return create_soap_envelope(header, body)

    def wsman_identify(self):
        """
        Send an Identify request to the server, to get the service type.

        The Idenfity request is a simple request that should work for all
        services that should support any WSMan standard, as it should be equal
        for all of them. It is used to check what WSMan accent the service is,
        e.g. WinRM, and the brand, e.g. Microsoft.

        Note that WinRM still requires you to authenticate to see this
        information, unless the following header is specified:

            WSMANIDENTIFY: unauthenticated

        :rtype: lxml.etree.ElementBase
        :returns:
            The Identify response from the server, in SOAP XML format.

            TODO: return only the important part of the response, e.g. as a
            dict?
        """
        request = self.format_wsman_request_identify()
        debug_log.info("WS-Man Identify start")
        ret = self._http_call(
            request,
            headers={
                'WSMANIDENTIFY': 'unauthenticated',
            },
        )
        debug_log.info("WS-Man Identify done")
        xml = etree.parse(ret.fp, parser=self.xmlparser)
        return xml

    #
    # WS-Man Pull
    #

    def format_wsman_request_pull(self, resource, context):
        r"""
        Format request for :meth:`.wsman_pull`.

        Example SOAP body:
        ::

          <wsen:Pull>
            <wsen:EnumerationContext>...</wsen:EnumerationContext>
            <wsen:MaxTime>PT120.000S</wsen:MaxTime>
            <wsen:MaxElements>xs:long</wsen:MaxElements>
            <wsen:MaxCharacters>xs:long</wsen:MaxCharacters>
          </wsen:Pull>
        """
        header = self._xml_header(
            _ACTION_PULL,
            resource=resource,
        )
        body = create_xml_element("s:Body")
        pull = create_xml_element("wsen:Pull")
        pull.append(
            create_xml_element("wsen:EnumerationContext", text=context)
        )
        body.append(pull)
        return create_soap_envelope(header, body)

    def wsman_pull(self, resource, context):
        """Send a request to pull data.

        :param str resource:
            The type of information to get. Could start with http, or it could
            be relative to:

                http://schemas.microsoft.com/wbem/wsman/1/

        :param str context:
            The identifier of the request to pull.  It is an EnumerationContext
            which should have been returned by a L{wsman_enumerate} request.

        :rtype: lxml.etree.ElementBase
        :returns:
            The XML PullResponse returned from the server.

            TODO: Does the Header contain something useful too?
        """
        request = self.format_wsman_request_pull(resource, context)

        debug_log.info("WS-Man Pull start (resource=%s)", repr(resource))
        ret = self._http_call(request)
        debug_log.info("WS-Man Pull done (resource=%s)", repr(resource))

        for event, elem in etree.iterparse(
                ret.fp,
                tag=format_name("PullResponse", "wsen"),
                encoding=self._winrm_encoding):
            return elem

    #
    # WS-Man Receive
    #

    def format_wsman_request_receive(self, shell_id, command_id, sequence):
        r"""
        Format request for :meth:`.wsman_receive`.

        Example SOAP request body:
        ::

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
        """
        header = self._xml_header(
            _ACTION_RECV,
            selectors=[
                create_wsman_selector("ShellId", shell_id),
            ],
        )
        body = create_xml_element("s:Body")
        receiver = create_xml_element(
            "rsp:Receive",
            attrs={'SequenceId': str(sequence)},
        )
        body.append(receiver)
        stream = create_xml_element(
            "rsp:DesiredStream",
            text="stdout stderr",
        )
        if command_id:
            stream.set('CommandId', str(command_id))
        receiver.append(stream)
        return create_soap_envelope(header, body)

    def wsman_receive(self, shell_id, command_id=None, sequence=0):
        """
        Send a Recieve request get command output.

        WinRM's execution of commands works in the way that the command is
        first called by a Command request, which only returns a CommandId,
        which we should then use when sending a Receive request later.

        Note that this command only returns one page of output, you would need
        to loop over the method with a growing L{sequence} to get the rest of
        the pages, until State is "Done".

        :param str shell_id:
            The ShellId that identifies what shell to get the output from.

        :param str command_id:
            The CommanId for the command that has already been given to the
            server.  Only output from this command will be received.  Not
            needed for Custom Remote Shells.

        :param int sequence:
            Specifies what "page" of the output that should be retrieved. This
            is only needed when command output is so large that it can't fit in
            a single SOAP message, and has to split up in several. Starts on 0
            and counts upwards.

        :returns tuple:
            A three element tuple on the form:

                (str:status, int:return_code, dict:out)

            The *status* could be Done, Running or Pending.
            The return code might be None, if not given by the server.
            The out dict could contain elements 'stdout' and 'stderr',
            depending on what the server sends.  The elements in the dict are
            all unicode objects.
        """
        request = self.format_wsman_request_receive(shell_id, command_id,
                                                    sequence)
        debug_log.info("WS-Man Recieve start (shell-id=%s, command-id=%s)",
                       repr(shell_id), repr(command_id))
        ret = self._http_call(request)
        debug_log.info("WS-Man Recieve done (shell-id=%s, command-id=%s)",
                       repr(shell_id), repr(command_id))

        root = etree.parse(ret.fp, parser=self.xmlparser)
        exitcode = None
        state = None
        out = dict()

        # Find the CommandState (Done, Running or Pending)
        for xml_state in root.iter(tag=format_name("CommandState", "rsp")):
            state = xml_state.get('State').split('/')[-1]
        # TODO: Check if state is not set?

        # Find the ExitCode, if given in this round
        for code in root.iter(tag=format_name("ExitCode", "rsp")):
            # Casting the exitcode into an integer. It could that WinRM tries
            # to use this differently in the future, which would then trigger
            # exceptions here. Would then have to cast it later.
            exitcode = int(code.text)

        # Get the output
        amount = 0
        for elem in root.iter(tag=format_name("Stream", "rsp")):
            if elem.text:
                amount += len(elem.text)
                out.setdefault(elem.get('Name'), []).append(elem.text)
            # free up memory:
            elem.clear()
        debug_log.info("Received %d bytes of base64 data", int(amount))

        # Clean up output:
        # - Change newlines from Microsoft's format '\r\n' to linux's '\n'.
        # - Remove the Byte Order Mark (BOM) - not needed for UTF-8, except to
        #   identity that it is encoded in UTF-8. More info:
        #   http://www.unicode.org/faq/utf_bom.html#BOM
        for t in out:
            out[t] = dechunk_wsman_response(out[t],
                                            charset=self._winrm_encoding)
        return state, exitcode, out

    #
    # WS-Man Send
    #

    def format_wsman_request_send(self, shell_id, command_id, data):
        """ Format request for :meth:`.wsman_send`. """
        header = self._xml_header(
            _ACTION_SEND,
            selectors=[
                create_wsman_selector("ShellId", shell_id),
            ],
        )
        body = create_xml_element("s:Body")
        send = create_xml_element("rsp:Send")
        body.append(send)
        send.append(
            create_xml_element(
                "rsp:Stream",
                attrs={
                    'Name': 'stdin',
                    'CommandId': command_id,
                    # Not sure if End is used
                    'End': format_bool(True),
                },
                text=prepare_wsman_input(data, self._winrm_encoding),
            )
        )
        return create_soap_envelope(header, body)

    def wsman_send(self, shell_id, command_id, data):
        """
        Make a Send call with input to be given to the remote Shell.

        This works like piping input through stdin, e.g:

            echo "testing" | cat

        It could be used when a command prompts you for input, e.g. password
        prompts.  Note that newlines (\n) are translated to windows' version of
        newlines (\r\n), and it should end with a newline.

        :param str shell_id:
            The ShellId for the Shell to use. The shell must have been created
            on the server side.

        :param str command_id:
            The CommandID for the command that should recieve the input data.
            The command must be active on the server, and should probably wait
            for input.

        :type data: str, or sqeuence of str
        :param data: The data to sent to the server as input.

        :returns:
            TODO
        """
        debug_log.debug("Sending input (shell-id=%s, command-id=%s): %s",
                        repr(shell_id), repr(command_id), repr(data))
        request = self.format_wsman_request_send(shell_id, command_id, data)
        debug_log.info("WS-Man Send start (shell-id=%s, command-id=%s)",
                       repr(shell_id), repr(command_id))
        ret = self._http_call(request)
        debug_log.info("WS-Man Send done (shell-id=%s, command-id=%s)",
                       repr(shell_id), repr(command_id))
        return etree.parse(ret.fp, parser=self.xmlparser)

    #
    # WS-Man Signal
    #

    def format_wsman_request_signal(self, shell_id, command_id, signal_name):
        """ Format request for :meth:`.wsman_signal`. """
        header = self._xml_header(
            _ACTION_SIGNAL,
            selectors=[
                create_wsman_selector("ShellId", shell_id),
            ],
        )
        body = create_xml_element("s:Body")
        signal = create_xml_element(
            "rsp:Signal",
            attrs={'CommandId': command_id},
        )
        body.append(signal)
        signal.append(
            create_xml_element(
                "rsp:Code",
                text="/".join((_ACTION_SIGNAL, signal_name)),
            )
        )
        return create_soap_envelope(header, body)

    def wsman_signal(self, shell_id, command_id, signal_name="Terminate"):
        """
        Send a Signal request to the server, to send a signal to a command.

        Signals are used e.g. to abort the execution of a running command.

        The most used signal is Terminate.  This should be sent for commands
        after the client has received the command output and exit code.  The
        server then knows that it doesn't need the output from the command
        anymore, and can remove it from its cache.

        :param str shell_id:
            The ShellId for the shell that the command is running in.

        :param str command_id:
            The CommandId for the command that should be signalled.

        :param str signal_name:
            The type of signal that should be sent.  Valid types:
              - 'ctrl_c': Aborts the command execution.
              - 'Terminate': Tells that the server could remove the given
                output from its cache, as the client has received it.
        """
        request = self.format_wsman_request_signal(shell_id, command_id,
                                                   signal_name)
        debug_log.info("WS-Man Signal start (shell-id=%s, command-id=%s)",
                       repr(shell_id), repr(command_id))
        ret = self._http_call(request)
        debug_log.info("WS-Man Signal done (shell-id=%s, command-id=%s)",
                       repr(shell_id), repr(command_id))
        # TODO: What to check?
        # TODO: What to return?
        return ret


class WinRMClient(WinRMProtocol):
    """
    Client for handling a remote Shell at a WinRM service through the WinRM
    protocol.

    What the client is taking care of, is how all the wsman request should be
    sent and received for WinRM shells.  The standard workflow when
    communicating with a WinRM server is:

        1. Send a Create request to create a Shell on the server. A ShellId is
           returned.
        2. Send a Command request to start a new command in the given Shell. A
           CommandId is returned. Note that it's not the result from the
           execution that is returned now, the command might not even be
           started on yet.
        3. If needed, you could send a Send request to send input to stdin or
           pipe. This could e.g. be used to e.g. fill in data in prompts.
           TODO: This does not work as expected, so more work needs to be done
           for this to work.
        4. If you want to, you could now go and do something else. The server
           is processing the command and caching the output.
        5. Send a Receive request to receive the output from the command. If
           the returned State is not "Done", you could keep on sending Send
           requests to get all of the data.
        6. Send a Signal request to tell the server that the output was
           received. The server could now remove the output from its cache and
           use for other commands.
        8. Send and receive more commands if needed in the shell. Note that
           each command is independent of the others, as we need to start
           powershell at each Command request. We might need to improve on this
           in the future, depending on our needs.
        9. Send a Delete request to shut down the given Shell when done. Each
           user only have a limited number of shells available, so you should
           do this to avoid getting temporarily blocked from the server if too
           many AD jobs are running simultaneously.

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
        logger.debug("Connecting to WinRM: %s", url)
        shellid = self.wsman_create()
        self.shellid = shellid
        # Subclasses could now run some startup commands on the server, e.g.
        # starting powershell in the active shell and import the
        # ActiveDirectory module. Example:
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
        except WinRMServerException as e:
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
            except Exception as e:
                self.logger.debug2("Closing shell failed: %r", e)
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

        This is a shortcut for calling L{execute} and run it through
        L{get_data} for getting the output data. This method is meant to be
        used for quick commands, as it hangs while waiting for the response. If
        you want to execute commands that take some time, please use L{execute}
        instead, and then use L{get_output} later on.

        @type *args: strings
        @param *args:
            Input should be the code that should be executed. Note that when
            using the default shell, cmd, you can only specify one single
            command, which must be in the first argument, and the rest of the
            arguments are considered parameters for that.

        @type stdin: string
        @param stdin: Data to send as input to the server.

        @rtype: dict
        @return:
            A dict with the command's output, separated by output type, e.g.
            'stderr', 'stdout' and 'pr'. All values should be strings.

        """
        return self.get_data(self.execute(*args, **kwargs))

    def get_output(self, commandid=None, signal=True, timeout_retries=50):
        """Get an iteration of exitcode and output for a given command.

        The output is returned as an iterator, to be able to process the first
        parts of the output already before all is processed or returned from
        the server. When done, the server is told that the output was received
        and could be removed from its cache.

        @type commandid: tuple
        @param commandid:
            The (ShellId, CommandId) for the command that the output should be
            retrieved from.

        @type signal: bool
        @param signal:
            If we should send a end signal to the server when all the output
            was received. This must be done, according to the specifications,
            after a process has finished, so that the server could free up the
            cache space and use it for the next command. It could be set to
            false in case of a command that needs input later on, but you want
            its initial output first. You then have to signal it yourself later
            on.

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
                except WinRMServerException as e:
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

        You have to wait for the whole response before getting the returned
        data from this command, as it gathers it all up. If you want to start
        processing the output before all of it is sent you should use
        L{get_output} directly.

        @type commandid: tuple
        @param commandid:
            The (ShellId, CommandId) for the command that the output should be
            retrieved from.

        @type signal: bool
        @param signal:
            If we should send a end signal to the server when all the output
            was received. This must be done, according to the specifications,
            after a process has finished, so that the server could free up the
            cache space and use it for the next command. It could be set to
            false in case of a command that needs input later on, but you want
            its initial output first. You then have to signal it yourself later
            on.

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

    # The location of the powershell.exe program we should run. Note that we
    # are expecting x64, and the path might change in the future.
    exec_path = (
        '%SystemRoot%\\syswow64\\WindowsPowerShell\\v1.0\\powershell.exe'
    )

    def execute(self, *args, **kwargs):
        """Send powershell commands to the server.

        Fires up the proper powershell.exe with proper parameters.

        Unfortunately, a new Shell must be create for each execution, due to
        not getting blocked from the server.

        """

        def _convert(v):
            if isinstance(v, bytes):
                v = v.decode('utf-8')
                warnings.warn('PowershellClient got bytestring args',
                              UnicodeWarning)
                return v
            else:
                return six.text_type(v)

        args = tuple((_convert(v) for v in args))
        # Later versions of powershell just hangs at newlines, so need to
        # remove them. TODO: This could create problems, we need to look at how
        # we generate powershell commands!
        command = ' '.join(args).replace('\n', ' ')
        # Options for powershell:
        # -NonInteractive   To avoid waiting for stdin and deadlocks if a
        #                   prompt is popping up.
        # -NoLogo           We don't want/need to see the copyright banner.
        #                   Don't know if it has any effect though, as we are
        #                   not starting a session.
        # -NoProfile        Loading profile is not needed, at least for now. It
        #                   will probably only increase the startup time if not
        #                   set.

        # Due to the command prompt string limitation, commands can not be
        # longer than 8191 characters. We limit ourselves to 8000 for some
        # extra breathing room.
        # See <https://support.microsoft.com/en-gb/help/830473
        #       /command-prompt-cmd-exe-command-line-string-limitation>
        # for more information for more information
        #
        if len(command) > 8000:
            raise CommandTooLongException('Too long command')

        return super(PowershellClient, self).execute(
            self.exec_path,
            '-NonInteractive -NoLogo -NoProfile -Command "%s"' % command,
            **kwargs)

    def escape_to_string(self, data):
        """Prepare (escape) data to be used in powershell commands.

        This is a compatibility method, see the module function
        :func:`.escape_to_string` for usage details.
        """
        try:
            return escape_to_string(data)
        except TypeError as exc_info:
            logger.warning("escape_to_string(): %s", repr(exc_info))
            raise Exception('Unknown data type %s for: %s'
                            % (type(data), data))

    def get_data(self, commandid, signal=True, timeout_retries=50):
        """Get the output for a given command.

        The method is overridden only to raise PowershellException when an
        error has occured. This is to be able to separate cmd errors from
        powershell errors.

        @raise PowershellException:
            If the exitcode from the output was other than 0.

        """
        try:
            return super(PowershellClient, self).get_data(commandid, signal,
                                                          timeout_retries)
        except ExitCodeException as e:
            raise PowershellException(e.exitcode, e.stderr, e.output)

    def get_output_json(self, commandid, other):
        """Get a Command's output and return the JSON as native data.

        This method could be used when data to output is piped through the
        powershell command:

            ... | ConvertTo-Json

        Note that to make the code a lot easier to read, the method reads in
        the complete output from WinRM before parsing it. The result is that it
        then consumes a lot of memory, especially for large output, but it's
        easier to debug later on.

        @type commandid: list or dict
        @param commandid:
            The CommandId for the command that the output should be retrieved
            from. If it is a dict, it is considered to be the output from the
            command already retrieved - the output must then be under the
            'stdout' key of the dict.

        @type other: dict
        @param other:
            This is where all server output that is not CSV gets put, sorted by
            output type. The values are lists of all its output.

        @rtype: mixed
        @return:
            All the JSON output is returned as native python data elements. The
            output could return a list, a dict (array) or a single element.

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
            for otype, data in six.iteritems(o):
                if data and otype != 'stdout':
                    other[otype] = data
            del o, otype, data
        self.logger.debug3("Got output of length: %d", len(out))
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


class CommandTooLongException(Exception):
    """If the given command is too long to be run through WinRM.

    The commands could be limited either by Powershell's command line, cmd's
    command line, or even WinRM. The maximum length for cmd.exe is 8191 for
    modern Windows versions (http://support.microsoft.com/kb/830473).

    This is not always enforced in our code, as we are not always sure when it
    happens, and what situations in the Windows environment that could cause
    it. It is, for now, only enforced in the more common situations where we
    could handle it. In the future, we might want to move this into `winrm.py`
    as one of the regular ExitCodeExceptions.

    """
    pass
