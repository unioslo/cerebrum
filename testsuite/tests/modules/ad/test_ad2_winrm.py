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

from Cerebrum.modules.ad2 import winrm
# from Cerebrum.utils import text_compat
from Cerebrum.testutils.log_utils import StrictNullHandler


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


def test_winrm_protocol_init(proto):
    assert proto.host == "localhost"
    assert proto.port == 5985
    assert not proto.encrypted


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
    # Not really needed
    parse_fault = proto._parse_fault

    fault_text = textwrap.dedent(
        """
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
    ).strip()
    fault_buffer = io.BytesIO(fault_text.encode(proto._winrm_encoding))

    fault_codes, reasons, details = parse_fault(fault_buffer)

    assert fault_codes == ["s:Sender", "w:QuotaLimit"]

    assert len(reasons) == 1
    assert reasons[0].strip().startswith("The WS-Management service ")
    assert reasons[0].strip().endswith(" user.")

    assert len(details) == 1
    assert details[0].strip().startswith("<s:Detail")
    assert details[0].strip().endswith("</s:Detail>")


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
def test_format_iso8601_duration(proto, args, expected):
    format_duration = proto._xml_duration
    assert format_duration(**args) == expected


def test_format_xml_element(proto):
    format_xml_element = proto._xml_element
    soap_ns = winrm.namespaces['s']
    elem = format_xml_element(
        "Body", "s",
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


class _CompareXml(object):
    """
    Hacky recursive xml.dom comparison
    """

    @staticmethod
    def parse_xml(text):
        return minidom.parseString(text)

    @staticmethod
    def get_node_data(node):
        if node.nodeType == node.TEXT_NODE:
            data = node.data.strip()
            p = node.parentNode
            if p and "MessageId" in p.tagName and data.startswith("uuid:"):
                # strip out uuid values
                return "uuid:" + UUID
            return data
        return ""

    @staticmethod
    def print_diff(diff, a, b, path):
        pretty_path = " -> ".join(path)
        print("%s diff: %s != %s (%s)" % (diff, repr(a), repr(b), pretty_path))

    @classmethod
    def filter_empty_text(cls, nodes):
        """ Remove empty text nodes. """
        return [
            node
            for node in nodes
            if node.nodeType != node.TEXT_NODE or cls.get_node_data(node)
        ]

    @classmethod
    def compare(cls, a, b):
        return cls.compare_nodes(
            cls.parse_xml(a).documentElement,
            cls.parse_xml(b).documentElement,
            tuple(),
        )

    @classmethod
    def compare_nodes(cls, a, b, path):
        path = path + (a.tagName,)
        if a.tagName != b.tagName:
            cls.print_diff("tag", a.tagName, b.tagName, path)
            return False

        if sorted(a.attributes.items()) != sorted(b.attributes.items()):
            cls.print_diff("attr", a.attributes, b.attributes, path)
            return False

        a_children = cls.filter_empty_text(a.childNodes)
        b_children = cls.filter_empty_text(b.childNodes)

        if len(a_children) != len(b_children):
            cls.print_diff("size", a.childNodes, b.childNodes, path)
            return False

        # path = path + (a.tagname,)
        for ac, bc in zip(a_children, b_children):
            if ac.nodeType != bc.nodeType:
                cls.print_diff("type", ac.nodeType, bc.nodeType, path)
                return False

            ac_data, bc_data = cls.get_node_data(ac), cls.get_node_data(bc)
            if ac.nodeType == ac.TEXT_NODE and ac_data != bc_data:
                if not all(d.startswith("uuid:") for d in (ac_data, bc_data)):
                    cls.print_diff("text", ac_data, bc_data, path)
                    return False

            if (ac.nodeType == ac.ELEMENT_NODE
                    and not cls.compare_nodes(ac, bc, path)):
                return False

        return True


compare_xml = _CompareXml.compare


UUID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"


def test_winrm_protocol_format_command(proto):
    xml_to_string = proto._xml_render
    shell_id = UUID
    argv = ["cmd.exe", "systeminfo"]

    request = proto.format_wsman_request_command(shell_id, argv)
    result = xml_to_string(request)
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
            uuid:ABABABAB-912447273160438756905213720643
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
    xml_to_string = proto._xml_render

    request = proto.format_wsman_request_create()
    result = xml_to_string(request)
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
    xml_to_string = proto._xml_render
    shell_id = UUID
    request = proto.format_wsman_request_delete(shell_id)
    result = xml_to_string(request)
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
    xml_to_string = proto._xml_render
    resource = "windows/shell"
    selector = None
    request = proto.format_wsman_request_enumerate(resource, selector)
    result = xml_to_string(request)
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
    xml_to_string = proto._xml_render
    resource = "windows/shell"
    selector = None
    request = proto.format_wsman_request_get(resource, selector)
    result = xml_to_string(request)
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
    xml_to_string = proto._xml_render
    request = proto.format_wsman_request_identify()
    result = xml_to_string(request)
    expected = """
      <ns0:Envelope xmlns:ns0="http://www.w3.org/2003/05/soap-envelope">
        <ns0:Header/>
        <ns0:Body>
          <ns0:Identify
            xmlns:ns0="http://schemas.dmtf.org/wbem/wsman/identity/1/wsmanidentity.xsd"/>
        </ns0:Body>
      </ns0:Envelope>
    """.lstrip().encode("utf-8")
    assert compare_xml(result, expected)


def test_winrm_protocol_format_pull(proto):
    xml_to_string = proto._xml_render
    resource = "windows/shell"
    context = None
    request = proto.format_wsman_request_pull(resource, context)

    result = xml_to_string(request)
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
    xml_to_string = proto._xml_render
    shell_id = UUID
    command_id = UUID
    sequence = 0
    request = proto.format_wsman_request_receive(shell_id, command_id,
                                                 sequence)

    result = xml_to_string(request)
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
    xml_to_string = proto._xml_render
    shell_id = UUID
    command_id = UUID
    data = "test"
    request = proto.format_wsman_request_send(shell_id, command_id, data)

    print(winrm.etree.tostring(request, pretty_print=True))

    result = xml_to_string(request)
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
    xml_to_string = proto._xml_render
    shell_id = UUID
    command_id = UUID
    signal = "Terminate"
    request = proto.format_wsman_request_signal(shell_id, command_id, signal)

    print(winrm.etree.tostring(request, pretty_print=True))

    result = xml_to_string(request)
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
              http://schemas.microsoft.com/wbem/wsman/1/windows/shell/signal/Terminate
            </rsp:Code>
          </rsp:Signal>
        </s:Body>
      </s:Envelope>
    """.lstrip().encode("utf-8")
    assert compare_xml(result, expected)
