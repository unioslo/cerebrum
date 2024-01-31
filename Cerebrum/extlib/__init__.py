# -*- coding: utf-8 -*-
#
# Copyright 2002-2022 University of Oslo, Norway
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
Bundled and/or modified third party modules.

``db_row``
    Heavily modified version of *db_row v0.8*, a comprehensive module with
    various row object implementations.  Deprecated, as *db_row* only supports
    Python 2.  Will be replaced with `records` in time.

``records``
    This module contains the row objects from *records v0.5.3*.  Introduced to
    replace `db_row`.

``xmlprinter``
    Simplified xml formatting util, based on *xmlprinter v0.1.0*.  Widely used
    in contrib scripts for formatting XML output.  Also used in:

    - ``Cerebrum.modules.fs.import_from_FS.ImportFromFs``
    - ``Cerebrum.modules.xmlutils.GeneralXMLWriter.XMLWriter``
"""
