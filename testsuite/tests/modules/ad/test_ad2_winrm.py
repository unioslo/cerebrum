# encoding: utf-8
""" Tests for mod:`Cerebrum.modules.ad2.winrm` """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import io
import logging
import textwrap
from xml.dom import minidom

import pytest
import six

from Cerebrum.modules.ad2 import winrm
# from Cerebrum.utils import text_compat
from Cerebrum.testutils.log_utils import StrictNullHandler


UUID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"


def _setup_logger(logger):
    # ensure log formatting is tested for the given logger
    logger.addHandler(StrictNullHandler())
    logger.setLevel(-100)


@pytest.fixture(scope='module', autouse=True)
def _patch_logging():
    """ catch badly formatted log records in dbal.logger. """
    _setup_logger(winrm.logger)
    # _setup_logger(winrm.debug_log)


@pytest.fixture
def logger(scope='module', autouse=True):
    logger = logging.getLogger("test")
    _setup_logger(logger)
    return logger


def test_winrm_protocol_default_ports(logger):
    http = winrm.WinRMProtocol(
        host="localhost",
        encrypted=False,
        logger=logger,
    )
    assert http.host == "localhost"
    assert http.port == 5985
    assert not http.encrypted
    https = winrm.WinRMProtocol(
        host="localhost",
        encrypted=True,
        logger=logger,
    )
    assert https.host == "localhost"
    assert https.port == 5986
    assert https.encrypted


@pytest.fixture
def proto(logger):
    proto = winrm.WinRMProtocol(
        host="localhost",
        port=5985,
        encrypted=False,
        logger=logger,
        check_name=False,
    )
    # TODO: We should probably mock this properly
    proto._opener = None
    return proto


def test_winrm_protocol_url(proto):
    expected = "http://localhost:5985/foo/bar"
    assert proto._http_url("foo/bar") == expected
    assert proto._http_url("/foo/bar") == expected


def test_winrm_protocol_add_creds(proto):
    username = "AzureDiamond"
    password = "hunter2"
    expected = "Basic QXp1cmVEaWFtb25kOmh1bnRlcjI="

    proto.add_credentials(username, password)
    assert proto._username == username
    assert proto._http_headers["Authorization"] == expected


def test_winrm_parse_fault(proto):
    fault_text = textwrap.dedent(
        """
        <s:Envelope
            xml:lang="en-US"
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
          <a:MessageID>
            uuid:AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE
          </a:MessageID>
          <a:To>
            http://schemas.xmlsoap.org/ws/2004/08/addressing/role/anonymous
          </a:To>
          <a:RelatesTo>
            uuid:AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE
          </a:RelatesTo>
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
    ).strip()
    fault_buffer = io.BytesIO(fault_text.encode(proto._winrm_encoding))

    fault_codes, reasons, details = winrm.parse_winrm_fault(fault_buffer)

    assert fault_codes == ["s:Sender", "w:QuotaLimit"]

    assert len(reasons) == 1
    assert reasons[0].strip().startswith("The WS-Management service ")
    assert reasons[0].strip().endswith(" user.")

    assert len(details) == 1
    assert details[0].strip().startswith(b"<s:Detail")
    assert details[0].strip().endswith(b"</s:Detail>")


@pytest.mark.parametrize(
    "args, expected",
    [
        pytest.param(args, expected, id="-".join(a for a in args))
        for args, expected in [
            (("Tag",), "Tag"),
            (("s:Body",), "{http://www.w3.org/2003/05/soap-envelope}Body"),
            (("lang", "xml"), "{http://www.w3.org/XML/1998/namespace}lang"),
        ]
    ],
)
def test_format_name(args, expected):
    assert winrm.format_name(*args) == expected


@pytest.mark.parametrize(
    "value, expected",
    [(0, "FALSE"), (1, "TRUE")],
)
def test_format_bool(value, expected):
    assert winrm.format_bool(value) == expected


@pytest.mark.parametrize(
    "args, expected",
    [
        pytest.param(args, expected, id=expected)
        for args, expected in [
            ({'hours': 6, 'seconds': 30}, "PT6H30.000S"),
            ({'minutes': 45}, "PT45M"),
        ]
    ],
)
def test_format_iso8601_duration(args, expected):
    format_duration = winrm.iso8601_duration
    assert format_duration(**args) == expected


def test_create_xml_element(proto):
    create_xml_element = winrm.create_xml_element
    soap_ns = winrm.NAMESPACES['s']
    elem = create_xml_element(
        "s:Body",
        {'s:mustUnderstand': "TRUE"},
        text="hello world",
        nsmap={'s': soap_ns},
    )
    assert elem.tag == "{" + soap_ns + "}Body"
    assert elem.attrib == {
        '{' + soap_ns + '}mustUnderstand': "TRUE",
    }
    assert elem.text == "hello world"
    assert elem.nsmap == {'s': soap_ns}


@pytest.mark.parametrize(
    "value, expected",
    [
        pytest.param(value, expected, id=repr(value))
        for value, expected in [
            (None, "$false"),
            (False, "$false"),
            (True, "$true"),
            (12, "12"),
            (1.0, "'1.000000'"),
            (b"f\0oo", "'foo'"),
            ("", "$false"),
            ("foo ' bar", "'foo '' bar'"),
            ([1, True, "foo"], "1,$true,'foo'"),
            ({'foo': True, 'bar': "a'b"}, "@{'bar'='a''b';'foo'=$true}"),
        ]
    ],
)
def test_escape_to_string(value, expected):
    assert winrm.escape_to_string(value) == expected


def test_escape_to_string_invalid():
    with pytest.raises(TypeError, match="No support for"):
        winrm.escape_to_string(object())


def test_dechunk_wsman_response():
    # ["hello,\r\n ", "  world\r\n"]
    chunks = ['aGVsbG8sDQog', 'ICB3b3JsZA0K']
    result = winrm.dechunk_wsman_response(chunks, "utf-8")
    assert result == "hello,\n   world\n"


def test_prepare_wsman_input_text():
    data = "hello,\n world"
    result = winrm.prepare_wsman_input(data, "utf-8")
    assert result == "aGVsbG8sDQogd29ybGQNCg=="


def test_prepare_wsman_input_lines():
    data = ["hello,", " world"]
    result = winrm.prepare_wsman_input(data, "utf-8")
    assert result == "aGVsbG8sDQogd29ybGQNCg=="


class _CompareXml(object):
    """ Hacky recursive xml.dom comparison """

    @staticmethod
    def get_node_data(node):
        """ Get node text data, if present. """
        if node.nodeType == node.TEXT_NODE:
            data = node.data.strip()
            p = node.parentNode
            if p and "MessageID" in p.tagName and data.startswith("uuid:"):
                # Replace MessageID uuid values, as they are randomly
                # generated, and can't easily be mocked.
                return "uuid:" + UUID
            return data
        return ""

    @classmethod
    def remove_whitespace(cls, nodes):
        """ Remove empty text nodes (whitespace). """
        return [
            node
            for node in nodes
            if node.nodeType != node.TEXT_NODE or cls.get_node_data(node)
        ]

    @staticmethod
    def parse_xml(text):
        """ Parse an xml document string. """
        return minidom.parseString(text)

    @classmethod
    def compare(cls, a, b):
        """ Compare two xml document strings. """
        return cls.compare_nodes(
            cls.parse_xml(a).documentElement,
            cls.parse_xml(b).documentElement,
            tuple(),
        )

    @staticmethod
    def print_diff(diff, a, b, path):
        """ Print a diff hint for debugging. """
        print("%s diff: %s != %s (%s)"
              % (diff, repr(a), repr(b), " -> ".join(path)))

    @classmethod
    def compare_nodes(cls, a, b, path):
        if a.nodeType == a.ELEMENT_NODE:
            path = path + (a.tagName,)

        if a.nodeType != b.nodeType:
            cls.print_diff("type", a.nodeType, b.nodeType, path)
            return False

        if a.nodeType == a.ELEMENT_NODE and a.tagName != b.tagName:
            cls.print_diff("tag", a.tagName, b.tagName, path)
            return False

        a_data, b_data = cls.get_node_data(a), cls.get_node_data(b)
        if a.nodeType == a.TEXT_NODE and a_data != b_data:
            cls.print_diff("text", a_data, b_data, path)
            return False

        a_attrs = sorted((getattr(a, "attributes") or {}).items())
        b_attrs = sorted((getattr(b, "attributes") or {}).items())
        if a_attrs != b_attrs:
            cls.print_diff("attr", a_attrs, b_attrs, path)
            return False

        a_children = cls.remove_whitespace(a.childNodes)
        b_children = cls.remove_whitespace(b.childNodes)

        if len(a_children) != len(b_children):
            cls.print_diff("size", a_children, b_children, path)
            return False

        for aa, bb in zip(a_children, b_children):
            if not cls.compare_nodes(aa, bb, path):
                return False

        return True


compare_xml = _CompareXml.compare


def test_winrm_protocol_format_command(proto):
    shell_id = UUID
    argv = ["cmd.exe", "systeminfo"]

    request = proto.format_wsman_request_command(shell_id, argv)
    result = winrm.xml_to_bytes(request, proto._winrm_encoding)
    expected = """
      <?xml version='1.0' encoding='UTF-8'?>
      <s:Envelope
          xmlns:cfg="http://schemas.microsoft.com/wbem/wsman/1/config"
          xmlns:rsp="http://schemas.microsoft.com/wbem/wsman/1/windows/shell"
          xmlns:s="http://www.w3.org/2003/05/soap-envelope"
          xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing"
          xmlns:wsen="http://schemas.xmlsoap.org/ws/2004/09/enumeration"
          xmlns:wsman="http://schemas.dmtf.org/wbem/wsman/1/wsman.xsd"
          xmlns:wsmid="http://schemas.dmtf.org/wbem/wsman/identity/1/wsmanidentity.xsd">
        <s:Header>
          <wsa:To>http://localhost:5985/wsman</wsa:To>
          <wsa:ReplyTo>
            <wsa:Address s:mustUnderstand="true">
              http://schemas.xmlsoap.org/ws/2004/08/addressing/role/anonymous
            </wsa:Address>
          </wsa:ReplyTo>
          <wsman:ResourceURI s:mustUnderstand="true">
            http://schemas.microsoft.com/wbem/wsman/1/windows/shell/cmd
          </wsman:ResourceURI>
          <wsa:Action s:mustUnderstand="true">
            http://schemas.microsoft.com/wbem/wsman/1/windows/shell/Command
          </wsa:Action>
          <wsman:MaxEnvelopeSize s:mustUnderstand="true">
            3073741824
          </wsman:MaxEnvelopeSize>
          <wsa:MessageID>
            uuid:AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE
          </wsa:MessageID>
          <wsman:Locale s:mustUnderstand="false" xml:lang="en-US"/>
          <wsman:OperationTimeout>PT300.000S</wsman:OperationTimeout>
          <wsman:SelectorSet>
            <wsman:Selector Name="ShellId">
              AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE
            </wsman:Selector>
          </wsman:SelectorSet>
          <wsman:OptionSet>
            <wsman:Option Name="WINRS_CONSOLEMODE_STDIN">TRUE</wsman:Option>
            <wsman:Option Name="WINRS_SKIP_CMD_SHELL">TRUE</wsman:Option>
          </wsman:OptionSet>
        </s:Header>
        <s:Body>
          <rsp:CommandLine>
            <rsp:Command>cmd.exe</rsp:Command>
            <rsp:Arguments>systeminfo</rsp:Arguments>
          </rsp:CommandLine>
        </s:Body>
      </s:Envelope>
    """.lstrip().encode("utf-8")
    assert compare_xml(result, expected)


def test_winrm_protocol_format_create(proto):
    request = proto.format_wsman_request_create()
    result = winrm.xml_to_bytes(request, proto._winrm_encoding)
    expected = """
      <?xml version='1.0' encoding='UTF-8'?>
      <s:Envelope
          xmlns:cfg="http://schemas.microsoft.com/wbem/wsman/1/config"
          xmlns:rsp="http://schemas.microsoft.com/wbem/wsman/1/windows/shell"
          xmlns:s="http://www.w3.org/2003/05/soap-envelope"
          xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing"
          xmlns:wsen="http://schemas.xmlsoap.org/ws/2004/09/enumeration"
          xmlns:wsman="http://schemas.dmtf.org/wbem/wsman/1/wsman.xsd"
          xmlns:wsmid="http://schemas.dmtf.org/wbem/wsman/identity/1/wsmanidentity.xsd">
        <s:Header>
          <wsa:To>http://localhost:5985/wsman</wsa:To>
          <wsa:ReplyTo>
            <wsa:Address s:mustUnderstand="true">
              http://schemas.xmlsoap.org/ws/2004/08/addressing/role/anonymous
            </wsa:Address>
          </wsa:ReplyTo>
          <wsman:ResourceURI s:mustUnderstand="true">
            http://schemas.microsoft.com/wbem/wsman/1/windows/shell/cmd
          </wsman:ResourceURI>
          <wsa:Action s:mustUnderstand="true">
            http://schemas.xmlsoap.org/ws/2004/09/transfer/Create
          </wsa:Action>
          <wsman:MaxEnvelopeSize s:mustUnderstand="true">
            3073741824
          </wsman:MaxEnvelopeSize>
          <wsa:MessageID>
            uuid:AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE
          </wsa:MessageID>
          <wsman:Locale s:mustUnderstand="false" xml:lang="en-US"/>
          <wsman:OperationTimeout>PT300.000S</wsman:OperationTimeout>
          <wsman:OptionSet>
            <wsman:Option Name="WINRS_NOPROFILE">TRUE</wsman:Option>
            <wsman:Option Name="WINRS_CODEPAGE">65001</wsman:Option>
          </wsman:OptionSet>
        </s:Header>
        <s:Body>
          <rsp:Shell>
            <rsp:Lifetime>PT10.000S</rsp:Lifetime>
            <rsp:InputStreams>stdin</rsp:InputStreams>
            <rsp:OutputStreams>stdout stderr</rsp:OutputStreams>
          </rsp:Shell>
        </s:Body>
      </s:Envelope>
    """.lstrip().encode("utf-8")
    assert compare_xml(result, expected)


def test_winrm_protocol_format_delete(proto):
    shell_id = UUID
    request = proto.format_wsman_request_delete(shell_id)
    result = winrm.xml_to_bytes(request, proto._winrm_encoding)
    expected = """
      <?xml version='1.0' encoding='UTF-8'?>
      <s:Envelope
          xmlns:cfg="http://schemas.microsoft.com/wbem/wsman/1/config"
          xmlns:rsp="http://schemas.microsoft.com/wbem/wsman/1/windows/shell"
          xmlns:s="http://www.w3.org/2003/05/soap-envelope"
          xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing"
          xmlns:wsen="http://schemas.xmlsoap.org/ws/2004/09/enumeration"
          xmlns:wsman="http://schemas.dmtf.org/wbem/wsman/1/wsman.xsd"
          xmlns:wsmid="http://schemas.dmtf.org/wbem/wsman/identity/1/wsmanidentity.xsd">
        <s:Header>
          <wsa:To>http://localhost:5985/wsman</wsa:To>
          <wsa:ReplyTo>
            <wsa:Address s:mustUnderstand="true">
              http://schemas.xmlsoap.org/ws/2004/08/addressing/role/anonymous
            </wsa:Address>
          </wsa:ReplyTo>
          <wsman:ResourceURI s:mustUnderstand="true">
            http://schemas.microsoft.com/wbem/wsman/1/windows/shell/cmd
          </wsman:ResourceURI>
          <wsa:Action s:mustUnderstand="true">
            http://schemas.xmlsoap.org/ws/2004/09/transfer/Delete
          </wsa:Action>
          <wsman:MaxEnvelopeSize s:mustUnderstand="true">
            3073741824
          </wsman:MaxEnvelopeSize>
          <wsa:MessageID>
            uuid:AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE
          </wsa:MessageID>
          <wsman:Locale s:mustUnderstand="false" xml:lang="en-US"/>
          <wsman:OperationTimeout>PT300.000S</wsman:OperationTimeout>
          <wsman:SelectorSet>
            <wsman:Selector Name="ShellId">
              AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE
            </wsman:Selector>
          </wsman:SelectorSet>
        </s:Header>
        <s:Body/>
      </s:Envelope>
    """.lstrip().encode("utf-8")
    assert compare_xml(result, expected)


def test_winrm_protocol_format_enumerate(proto):
    resource = "windows/shell"
    selector = None
    request = proto.format_wsman_request_enumerate(resource, selector)
    result = winrm.xml_to_bytes(request, proto._winrm_encoding)
    expected = """
      <?xml version='1.0' encoding='UTF-8'?>
      <s:Envelope
          xmlns:cfg="http://schemas.microsoft.com/wbem/wsman/1/config"
          xmlns:rsp="http://schemas.microsoft.com/wbem/wsman/1/windows/shell"
          xmlns:s="http://www.w3.org/2003/05/soap-envelope"
          xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing"
          xmlns:wsen="http://schemas.xmlsoap.org/ws/2004/09/enumeration"
          xmlns:wsman="http://schemas.dmtf.org/wbem/wsman/1/wsman.xsd"
          xmlns:wsmid="http://schemas.dmtf.org/wbem/wsman/identity/1/wsmanidentity.xsd">
        <s:Header>
          <wsa:To>http://localhost:5985/wsman</wsa:To>
          <wsa:ReplyTo>
            <wsa:Address s:mustUnderstand="true">
            http://schemas.xmlsoap.org/ws/2004/08/addressing/role/anonymous
          </wsa:Address>
          </wsa:ReplyTo>
          <wsman:ResourceURI s:mustUnderstand="true">
            http://schemas.microsoft.com/wbem/wsman/1/windows/shell
          </wsman:ResourceURI>
          <wsa:Action s:mustUnderstand="true">
            http://schemas.xmlsoap.org/ws/2004/09/enumeration/Enumerate
          </wsa:Action>
          <wsman:MaxEnvelopeSize s:mustUnderstand="true">
            3073741824
          </wsman:MaxEnvelopeSize>
          <wsa:MessageID>
            uuid:AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE
          </wsa:MessageID>
          <wsman:Locale s:mustUnderstand="false" xml:lang="en-US"/>
          <wsman:OperationTimeout>PT300.000S</wsman:OperationTimeout>
        </s:Header>
        <s:Body>
          <wsen:Enumerate/>
        </s:Body>
      </s:Envelope>
    """.lstrip().encode("utf-8")
    assert compare_xml(result, expected)


def test_winrm_protocol_format_get(proto):
    resource = "windows/shell"
    selector = None
    request = proto.format_wsman_request_get(resource, selector)
    result = winrm.xml_to_bytes(request, proto._winrm_encoding)
    expected = """
      <?xml version='1.0' encoding='UTF-8'?>
      <s:Envelope
          xmlns:cfg="http://schemas.microsoft.com/wbem/wsman/1/config"
          xmlns:rsp="http://schemas.microsoft.com/wbem/wsman/1/windows/shell"
          xmlns:s="http://www.w3.org/2003/05/soap-envelope"
          xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing"
          xmlns:wsen="http://schemas.xmlsoap.org/ws/2004/09/enumeration"
          xmlns:wsman="http://schemas.dmtf.org/wbem/wsman/1/wsman.xsd"
          xmlns:wsmid="http://schemas.dmtf.org/wbem/wsman/identity/1/wsmanidentity.xsd">
        <s:Header>
          <wsa:To>http://localhost:5985/wsman</wsa:To>
          <wsa:ReplyTo>
            <wsa:Address s:mustUnderstand="true">
              http://schemas.xmlsoap.org/ws/2004/08/addressing/role/anonymous
            </wsa:Address>
          </wsa:ReplyTo>
          <wsman:ResourceURI s:mustUnderstand="true">
            http://schemas.microsoft.com/wbem/wsman/1/windows/shell
          </wsman:ResourceURI>
          <wsa:Action s:mustUnderstand="true">
            http://schemas.xmlsoap.org/ws/2004/09/transfer/Get
          </wsa:Action>
          <wsman:MaxEnvelopeSize s:mustUnderstand="true">
            3073741824
          </wsman:MaxEnvelopeSize>
          <wsa:MessageID>
            uuid:AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE
          </wsa:MessageID>
          <wsman:Locale s:mustUnderstand="false" xml:lang="en-US"/>
          <wsman:OperationTimeout>PT300.000S</wsman:OperationTimeout>
        </s:Header>
        <s:Body/>
      </s:Envelope>
    """.lstrip().encode("utf-8")
    assert compare_xml(result, expected)


def test_winrm_protocol_format_identify(proto):
    request = proto.format_wsman_request_identify()
    result = winrm.xml_to_bytes(request, proto._winrm_encoding)
    expected = """
      <s:Envelope
          xmlns:cfg="http://schemas.microsoft.com/wbem/wsman/1/config"
          xmlns:rsp="http://schemas.microsoft.com/wbem/wsman/1/windows/shell"
          xmlns:s="http://www.w3.org/2003/05/soap-envelope"
          xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing"
          xmlns:wsen="http://schemas.xmlsoap.org/ws/2004/09/enumeration"
          xmlns:wsman="http://schemas.dmtf.org/wbem/wsman/1/wsman.xsd"
          xmlns:wsmid="http://schemas.dmtf.org/wbem/wsman/identity/1/wsmanidentity.xsd">
        <s:Header/>
        <s:Body>
          <wsmid:Identify/>
        </s:Body>
      </s:Envelope>
    """.lstrip().encode("utf-8")
    assert compare_xml(result, expected)


def test_winrm_protocol_format_pull(proto):
    resource = "windows/shell"
    context = None
    request = proto.format_wsman_request_pull(resource, context)

    result = winrm.xml_to_bytes(request, proto._winrm_encoding)
    expected = """
      <?xml version='1.0' encoding='UTF-8'?>
      <s:Envelope
          xmlns:cfg="http://schemas.microsoft.com/wbem/wsman/1/config"
          xmlns:rsp="http://schemas.microsoft.com/wbem/wsman/1/windows/shell"
          xmlns:s="http://www.w3.org/2003/05/soap-envelope"
          xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing"
          xmlns:wsen="http://schemas.xmlsoap.org/ws/2004/09/enumeration"
          xmlns:wsman="http://schemas.dmtf.org/wbem/wsman/1/wsman.xsd"
          xmlns:wsmid="http://schemas.dmtf.org/wbem/wsman/identity/1/wsmanidentity.xsd">
        <s:Header>
          <wsa:To>http://localhost:5985/wsman</wsa:To>
          <wsa:ReplyTo>
            <wsa:Address s:mustUnderstand="true">
              http://schemas.xmlsoap.org/ws/2004/08/addressing/role/anonymous
            </wsa:Address>
          </wsa:ReplyTo>
          <wsman:ResourceURI s:mustUnderstand="true">
            http://schemas.microsoft.com/wbem/wsman/1/windows/shell
          </wsman:ResourceURI>
          <wsa:Action s:mustUnderstand="true">
            http://schemas.xmlsoap.org/ws/2004/09/enumeration/Pull
          </wsa:Action>
          <wsman:MaxEnvelopeSize s:mustUnderstand="true">
            3073741824
          </wsman:MaxEnvelopeSize>
          <wsa:MessageID>
            uuid:AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE
          </wsa:MessageID>
          <wsman:Locale s:mustUnderstand="false" xml:lang="en-US"/>
          <wsman:OperationTimeout>PT300.000S</wsman:OperationTimeout>
        </s:Header>
        <s:Body>
          <wsen:Pull>
            <wsen:EnumerationContext/>
          </wsen:Pull>
        </s:Body>
      </s:Envelope>
    """.lstrip().encode("utf-8")
    assert compare_xml(result, expected)


def test_winrm_protocol_format_receive(proto):
    shell_id = UUID
    command_id = UUID
    sequence = 0
    request = proto.format_wsman_request_receive(shell_id, command_id,
                                                 sequence)

    result = winrm.xml_to_bytes(request, proto._winrm_encoding)
    expected = """
      <?xml version='1.0' encoding='UTF-8'?>
      <s:Envelope
          xmlns:cfg="http://schemas.microsoft.com/wbem/wsman/1/config"
          xmlns:rsp="http://schemas.microsoft.com/wbem/wsman/1/windows/shell"
          xmlns:s="http://www.w3.org/2003/05/soap-envelope"
          xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing"
          xmlns:wsen="http://schemas.xmlsoap.org/ws/2004/09/enumeration"
          xmlns:wsman="http://schemas.dmtf.org/wbem/wsman/1/wsman.xsd"
          xmlns:wsmid="http://schemas.dmtf.org/wbem/wsman/identity/1/wsmanidentity.xsd">
        <s:Header>
          <wsa:To>http://localhost:5985/wsman</wsa:To>
          <wsa:ReplyTo>
            <wsa:Address s:mustUnderstand="true">
              http://schemas.xmlsoap.org/ws/2004/08/addressing/role/anonymous
            </wsa:Address>
          </wsa:ReplyTo>
          <wsman:ResourceURI s:mustUnderstand="true">
            http://schemas.microsoft.com/wbem/wsman/1/windows/shell/cmd
          </wsman:ResourceURI>
          <wsa:Action s:mustUnderstand="true">
            http://schemas.microsoft.com/wbem/wsman/1/windows/shell/Receive
          </wsa:Action>
          <wsman:MaxEnvelopeSize s:mustUnderstand="true">
            3073741824
          </wsman:MaxEnvelopeSize>
          <wsa:MessageID>
            uuid:AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE
          </wsa:MessageID>
          <wsman:Locale s:mustUnderstand="false" xml:lang="en-US"/>
          <wsman:OperationTimeout>PT300.000S</wsman:OperationTimeout>
          <wsman:SelectorSet>
            <wsman:Selector Name="ShellId">
              AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE
            </wsman:Selector>
          </wsman:SelectorSet>
        </s:Header>
        <s:Body>
          <rsp:Receive SequenceId="0">
            <rsp:DesiredStream
                CommandId="AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE">
              stdout stderr
            </rsp:DesiredStream>
          </rsp:Receive>
        </s:Body>
      </s:Envelope>
    """.lstrip().encode("utf-8")
    assert compare_xml(result, expected)


def test_winrm_protocol_format_send(proto):
    shell_id = UUID
    command_id = UUID
    data = "test"
    request = proto.format_wsman_request_send(shell_id, command_id, data)

    result = winrm.xml_to_bytes(request, proto._winrm_encoding)
    expected = """
      <?xml version='1.0' encoding='UTF-8'?>
      <s:Envelope
          xmlns:cfg="http://schemas.microsoft.com/wbem/wsman/1/config"
          xmlns:rsp="http://schemas.microsoft.com/wbem/wsman/1/windows/shell"
          xmlns:s="http://www.w3.org/2003/05/soap-envelope"
          xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing"
          xmlns:wsen="http://schemas.xmlsoap.org/ws/2004/09/enumeration"
          xmlns:wsman="http://schemas.dmtf.org/wbem/wsman/1/wsman.xsd"
          xmlns:wsmid="http://schemas.dmtf.org/wbem/wsman/identity/1/wsmanidentity.xsd">
        <s:Header>
          <wsa:To>http://localhost:5985/wsman</wsa:To>
          <wsa:ReplyTo>
            <wsa:Address s:mustUnderstand="true">
              http://schemas.xmlsoap.org/ws/2004/08/addressing/role/anonymous
            </wsa:Address>
          </wsa:ReplyTo>
          <wsman:ResourceURI s:mustUnderstand="true">
            http://schemas.microsoft.com/wbem/wsman/1/windows/shell/cmd
          </wsman:ResourceURI>
          <wsa:Action s:mustUnderstand="true">
            http://schemas.microsoft.com/wbem/wsman/1/windows/shell/Send
          </wsa:Action>
          <wsman:MaxEnvelopeSize s:mustUnderstand="true">
            3073741824
          </wsman:MaxEnvelopeSize>
          <wsa:MessageID>
            uuid:AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE
          </wsa:MessageID>
          <wsman:Locale s:mustUnderstand="false" xml:lang="en-US"/>
          <wsman:OperationTimeout>PT300.000S</wsman:OperationTimeout>
          <wsman:SelectorSet>
            <wsman:Selector Name="ShellId">
              AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE
            </wsman:Selector>
          </wsman:SelectorSet>
        </s:Header>
        <s:Body>
          <rsp:Send>
            <rsp:Stream
                CommandId="AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"
                End="TRUE"
                Name="stdin">
              dGVzdA0K
            </rsp:Stream>
          </rsp:Send>

        </s:Body>
      </s:Envelope>
    """.lstrip().encode("utf-8")
    assert compare_xml(result, expected)


def test_winrm_protocol_format_signal(proto):
    shell_id = UUID
    command_id = UUID
    signal = "Terminate"
    request = proto.format_wsman_request_signal(shell_id, command_id, signal)

    result = winrm.xml_to_bytes(request, proto._winrm_encoding)
    expected = """
      <?xml version='1.0' encoding='UTF-8'?>
      <s:Envelope
          xmlns:cfg="http://schemas.microsoft.com/wbem/wsman/1/config"
          xmlns:rsp="http://schemas.microsoft.com/wbem/wsman/1/windows/shell"
          xmlns:s="http://www.w3.org/2003/05/soap-envelope"
          xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing"
          xmlns:wsen="http://schemas.xmlsoap.org/ws/2004/09/enumeration"
          xmlns:wsman="http://schemas.dmtf.org/wbem/wsman/1/wsman.xsd"
          xmlns:wsmid="http://schemas.dmtf.org/wbem/wsman/identity/1/wsmanidentity.xsd">
        <s:Header>
          <wsa:To>http://localhost:5985/wsman</wsa:To>
          <wsa:ReplyTo>
            <wsa:Address s:mustUnderstand="true">
              http://schemas.xmlsoap.org/ws/2004/08/addressing/role/anonymous
            </wsa:Address>
          </wsa:ReplyTo>
          <wsman:ResourceURI s:mustUnderstand="true">
            http://schemas.microsoft.com/wbem/wsman/1/windows/shell/cmd
          </wsman:ResourceURI>
          <wsa:Action s:mustUnderstand="true">
            http://schemas.microsoft.com/wbem/wsman/1/windows/shell/Signal
          </wsa:Action>
          <wsman:MaxEnvelopeSize s:mustUnderstand="true">
            3073741824
          </wsman:MaxEnvelopeSize>
          <wsa:MessageID>
            uuid:AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE
          </wsa:MessageID>
          <wsman:Locale s:mustUnderstand="false" xml:lang="en-US"/>
          <wsman:OperationTimeout>PT300.000S</wsman:OperationTimeout>
          <wsman:SelectorSet>
            <wsman:Selector Name="ShellId">
              AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE
            </wsman:Selector>
          </wsman:SelectorSet>
        </s:Header>
        <s:Body>
          <rsp:Signal CommandId="AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE">
            <rsp:Code>
              http://schemas.microsoft.com/wbem/wsman/1/windows/shell/Signal/Terminate
            </rsp:Code>
          </rsp:Signal>
        </s:Body>
      </s:Envelope>
    """.lstrip().encode("utf-8")
    assert compare_xml(result, expected)


#
# Test errors
#


# Example from running a powershell command that pipes into nothing, e.g.:
#   `Get-Help Get-ADAccount |`
exit_code_error_stderr = r"""
An empty pipe element is not allowed.
    + CategoryInfo          : ParserError: (:) [], ParentContainsErrorRecordEx
   ception
    + FullyQualifiedErrorId : EmptyPipeElement

""".lstrip()


def test_exit_code_exception():
    code = 1
    stderr = exit_code_error_stderr
    out = {'stderr': stderr}

    error = winrm.ExitCodeException(code, stderr, output=out)

    with pytest.raises(winrm.ExitCodeException,
                       match="Command failed: exitcode: 1") as exc_info:
        raise error

    assert stderr in six.text_type(exc_info.value)


# example stderr output from `Get-Content <file>` when <file> doesn't exist
powershell_error_stderr = r"""
Get-Content : Cannot find path 'C:\missing-file.txt' because it does not exist.
At line:1 char:223
+ ... eretest-ad04.local', $pass);          Get-Content C:\missing-file.txt
+                                           ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : ObjectNotFound: (C:\missing-file.txt:String) [Ge
   t-Content], ItemNotFoundException
    + FullyQualifiedErrorId : PathNotFound,Microsoft.PowerShell.Commands.GetCo
   ntentCommand

""".lstrip()


def test_powershell_exception():
    # Example from running a powershell command that pipes into nothing, e.g.:
    #   `Get-Help Get-ADAccount |`
    code = 1
    stderr = powershell_error_stderr
    out = {'stderr': stderr}

    error = winrm.PowershellException(code, stderr, output=out)

    with pytest.raises(winrm.PowershellException,
                       match="Command failed: exitcode: 1") as exc_info:
        raise error

    assert stderr in six.text_type(exc_info.value)
