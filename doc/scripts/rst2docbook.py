#!/usr/bin/python
# Use our own docbook writer

# Author: Ollie Rutherfurd
# Contact: oliver@rutherfurd.net
# Revision: $Revision$
# Date: $Date$
# Copyright: This module has been placed in the public domain.

"""
A minimal front end to the Docutils Publisher, producing DocBook XML.
"""

import locale
try:
    locale.setlocale(locale.LC_ALL, '')
except:
    pass

from docutils.core import publish_cmdline, default_description

# cerebrum-changes starts:
from docutils.parsers.rst import directives
from rst_extensions import sysinclude, namespace, known_vars
directives.register_directive('sysinclude', sysinclude)
directives.register_directive('namespace', namespace)
# cerebrum-changes ends

description = ('Generates DocBook XML documents from standalone reStructuredText '
               'sources.  ' + default_description)

publish_cmdline(writer_name='docbook', description=description)


# :indentSize=4:lineSeparator=\n:noTabs=true:tabSize=4:
