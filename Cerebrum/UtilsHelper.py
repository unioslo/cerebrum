# -*- coding: iso-8859-1 -*-
# Copyright 2002-2012 University of Oslo, Norway
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

"""ISO-8859-1 related code"""

import cereconf
import re
from string import maketrans

# TODO: Deprecate when switching over to Python 3.x
# TODO: Make it possible to put this class in a utf-8 encoded .py file


class Latin1:

    def __init__(self):
        self.lat1_646_tr = maketrans(
            'ÆØÅæø¦¿åÀÁÂÃÄÇÈÉÊËÌÍÎÏÑÒÓÔÕÖÙÚÛÝàáâãäçèéêëìíîïñòóôõöùúûýÿ¨­¯´',
            '[\\]{|||}AAAAACEEEEIIIINOOOOOUUUYaaaaaceeeeiiiinooooouuuyy"--\'')
        self.lat1_646_subst = re.compile(
            '[^\x1f-\x7e\xff]').sub  # Should be [^\x20-\x7e].
        self.lat1_646_cache = {}

        # U-umlaut is treated specially and is therefore defined in
        # latin1_specials to be transcribed to 'ue' instead of the single
        # character 'u'. The reason for this is a wish for email addresses to
        # reflect the common transcribation choice for this
        # character. O-umlaut and a-umlaut are not getting such special
        # treatment.
        self.latin1_specials = {'Ð': 'Dh', 'ð': 'dh',
                                'Þ': 'Th', 'þ': 'th',
                                'ß': 'ss', 'Ü': 'Ue',
                                'ü': 'ue'}
        self.latin1_wash_cache = {}

    def to_iso646_60(self, s, substitute=''):
        """Wash known accented letters and some common charset confusions."""
        try:
            xlate_match = self.lat1_646_cache[substitute]
        except KeyError:
            xlate = self.latin1_specials.copy()
            for ch in filter(self.lat1_646_subst.__self__.match, self.lat1_646_tr):
                xlate.setdefault(ch, substitute)
            xlate_match = self.lat1_646_cache[
                substitute] = lambda m: xlate[m.group()]
        return self.lat1_646_subst(xlate_match, str(s).translate(self.lat1_646_tr))

    def wash(self, data, target_charset, expand_chars=False, substitute=''):
        # TBD: The code in this function is rather messy, as it tries to
        # deal with multiple combinations of target charsets etc.  It
        # *might* be worth it to reimplement this stuff as a few proper
        # Python codecs, i.e. registered via codecs.register() and hence
        # usable via the Python builtin str.encode().  On the other hand,
        # that might be seen as involving excess amounts of magic for such
        # an apparently simple task.
        key = (target_charset, bool(expand_chars), substitute)
        try:
            (tr, xlate_subst, xlate_match) = self.latin1_wash_cache[key]
        except KeyError:
            tr_from = ('ÆØÅæøå[\\]{|}¦¿'
                       'ÀÁÂÃÄÇÈÉÊËÌÍÎÏÑÒÓÔÕÖÙÚÛÝàáâãäçèéêëìíîïñòóôõöùúûýÿ'
                       '¨­¯´')
            xlate = self.latin1_specials.copy()
            if target_charset == 'iso646-60':
                tr_to = ('[\\]{|}[\\]{|}||'
                         'AAAAACEEEEIIIINOOOOOUUUYaaaaaceeeeiiiinooooouuuyy'
                         '"--\'')
                xlate_re = '[^\x1f-\x7e\xff]'  # Should be [^\x20-\x7e].
            elif target_charset == 'POSIXname':
                tr_to = ('AOAaoaAOAaoaoo'
                         'AAAAACEEEEIIIINOOOOOUUUUYaaaaaceeeeiiiinooooouuuyy'
                         '"--\'')
                if expand_chars:
                    xlate.update({'Æ': 'Ae', 'æ': 'ae', 'Å': 'Aa', 'å': 'aa',
                                  'Ü': 'Ue', 'ü': 'ue'})
                xlate_re = r'[^a-zA-Z0-9 -]'
            else:
                raise ValueError(
                    "Unknown target charset: %r" %
                    (target_charset,))

            tr = dict(zip(tr_from, tr_to))
            for ch in filter(xlate.has_key, tr_from):
                del tr[ch]
            tr = maketrans("".join(tr.keys()), "".join(tr.values()))

            xlate_re = re.compile(xlate_re)
            for ch in filter(xlate_re.match, tr):
                xlate.setdefault(ch, substitute)

            (tr, xlate_subst, xlate_match) = self.latin1_wash_cache[key] = (
                tr, xlate_re.sub, lambda match: xlate[match.group()])

        return xlate_subst(xlate_match, str(data).translate(tr))
