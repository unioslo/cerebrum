# -*- coding: utf-8 -*-
#
# Copyright 2012-2025 University of Oslo, Norway
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
Attribute types for the AD attributes module.

For legacy reasons, these are typically imported from
:mod:`Cerebrum.modules.ad2`.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
from Cerebrum import Constants


class _ADAttrCode(Constants._CerebrumCode):
    """Code values for AD-attributes, used in table ad_attribute."""

    _lookup_table = "[:table schema=cerebrum name=ad_attribute_code]"

    def __init__(self, code, description=None, multivalued=False):
        self.multivalued = bool(multivalued)
        super(_ADAttrCode, self).__init__(code, description)

    def insert(self):
        self.sql.execute(
            """
            INSERT INTO %(code_table)s
              (%(code_col)s, %(str_col)s, %(desc_col)s, multivalued)
            VALUES
              (%(code_seq)s, :str, :desc, :multivalued)
            """ % {
                'code_table': self._lookup_table,
                'code_col': self._lookup_code_column,
                'str_col': self._lookup_str_column,
                'desc_col': self._lookup_desc_column,
                'code_seq': self._code_sequence,
            },
            {
                'str': self.str,
                'desc': self._desc,
                'multivalued': bool(self.multivalued),
            },
        )


class AdAttributeConstants(Constants.Constants):
    """
    AD Attribute constants

    This, along with `.CLConstants`, should probably be moved into
    a separate `<ad-attrs>.constants` module when (or if) we move the AD
    attribute related functionality into its own module.
    """

    ad_attribute_homedir = _ADAttrCode(
        "HomeDirectory",
        "HomeDirectory for an object in AD",
        False,
    )

    ad_attribute_homedrive = _ADAttrCode(
        "HomeDrive",
        "HomeDrive for an account in AD",
        False,
    )

    ad_attribute_scriptpath = _ADAttrCode(
        "ScriptPath",
        "ScriptPath for an account in AD",
        False,
    )

    # No need for Title - as this is stored as a PersonName or
    # EntityNameWithLanguage
    # ad_attribute_title = _ADAttrCode(
    #     "Title",
    #     "Title for an account in AD",
    #     False,
    # )

    # Mail is either handled by the mail-module, or stored as EntityContactInfo
    # ad_attribute_mail = _ADAttrCode(
    #     "Mail",
    #     "Mail address for an account in AD",
    #     False,
    # )

    # TODO: should we make group scope (global/universal) and group category
    # (security/distribution) be set through attributes?

    ADAttribute = _ADAttrCode


class AdAttributeChangeConstants(Constants.CLConstants):
    """
    Changelog types for `mod_ad_attributes`
    """

    ad_attr_add = Constants._ChangeTypeCode(
        "ad_attr",
        "add",
        "added AD-attribute for %(subject)s",
        (
            ", ".join((
                "spread=%(string:spread)s",
                "attr=%(string:attr)s",
                "value=%(string:value)s",
            )),
        ),
    )

    ad_attr_del = Constants._ChangeTypeCode(
        "ad_attr",
        "remove",
        "removed AD-attribute for %(subject)s",
        (
            ", ".join((
                "spread=%(string:spread)s",
                "attr=%(string:attr)s",
            )),
        ),
    )
