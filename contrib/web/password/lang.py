#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
# Copyright 2007 University of Oslo, Norway
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
#
# $Id$


"""
This file serves as an empty placeholder/template so that the password
service can be run 'as is' without any import errors or
suchlike.

To customize the language-strings for a given language at your site,
simply add new entries in the Language*-classes below, corresponding
to variables in the default language classes. 'sitename' in particular
is a good example of something you wish to customize.

If there is text common across the language, e.g. as usually is the
case with HTML-templates, simply define a superclass here that
overrides the approrpiate fields in the Default-class, then let the
classes here have that class as the first class they inherit from.

"""

__version__ = "$Revision$"
# $Source$


import default_lang


supported_languages = default_lang.supported_languages


def get_text_by_language(lang=None):
    """Factory-method for retrieving the language-class as determined
    by either the user's choice, the browser's default or the site's
    default, as expressed through the 'lang'-parameter.

    """    
    if lang is None:
        raise RuntimeError("Language lookup error")
        
    if lang == "en":
        return LanguageEn()
    elif lang == "no-bok":
        return LanguageNoBok()
    elif lang == "no-nyn":
        return LanguageNoNyn()


class LanguageEn(default_lang.LanguageEn):
    pass


class LanguageNoBok(default_lang.LanguageNoBok):
    pass


class LanguageNoNyn(default_lang.LanguageNoNyn):
    pass

