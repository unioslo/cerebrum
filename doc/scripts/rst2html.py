#!/usr/bin/python2.2


# Author: David Goodger
# Contact: goodger@python.org
# Revision: $Revision$
# Date: $Date$
# Copyright: This module has been placed in the public domain.

"""
A minimal front end to the Docutils Publisher, producing HTML.
"""

try:
    import locale
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


description = ('Generates (X)HTML documents from standalone reStructuredText '
               'sources.  ' + default_description)

publish_cmdline(writer_name='html', description=description)

