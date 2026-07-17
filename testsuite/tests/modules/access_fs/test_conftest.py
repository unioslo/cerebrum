# -*- coding: utf-8 -*-
""" unit tests for :mod:`Cerebrum.modules.no.access_FS`. """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import textwrap

from Cerebrum.testutils import file_utils


#
# write_xml_file fixture test
#


def test_write_xml_file(write_xml_file):
    content = textwrap.dedent(
        """
        <?xml version="1.0" encoding="utf-8"?>
        <data></data>
        """
    ).strip()
    filename = write_xml_file(content)
    result = file_utils.read_text(filename)
    assert result == content
