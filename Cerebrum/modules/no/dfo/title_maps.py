# -*- coding: utf-8 -*-

# Copyright 2021 University of Oslo, Norway
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
Utils for mapping/translating employee titles.

Cerebrum stores a job title (WORKTITLE) and a personal title (PERSONALTITLE) as
an EntityNameWithLanguage entry (EntityNameCode), in multiple languages.

DFØ impose a personal title length limit, includes job code in job titles, and
doesn't have English translations for either of these fields.  This module adds
support for mapping these incomplete titles to localized titles.

Configuration
-------------
This module fetches titles from a config module attribute,
``user_title_map.USER_TITLE_MAP``.


.. note::
   USER_TITLE_MAP isn't actually a list, but a dict (for no reason).  TODO: Fix
   this.

This attribute should be a list of title mappings from the
*Stillingsbetegnelser* API.

Source
------
The mappings and localized titles should be fetched from the
*Stillingsbetegnelser* API.  See
`<https://api-uio.intark.uh-it.no/#!/apis/75790b88-84e2-44b8-b90b-8884e2a4b8b2>`_
for more info.

API example data:

::

    [{
        'code': 214,
        'norTitle': 'Rektor',
        'engTitle': 'Rector',
    }, {
        'code': 787,
        'norTitle': "Spesialtannlege",
        'engTitle': "Specialist Dentist",
    }, {
        'customTitleId': "Fung.fak.dir",
        'norTitle': "Fungerende fakultetsdirektør",
        'engTitle': "Acting Faculty Director",
    }, {
        'customTitleId': "Fung.forsk.led",
        'norTitle': "Fungerende forskningsleder",
        'engTitle': "Acting Head of Research",
    }]


"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import logging
import re
import warnings

import six

from Cerebrum.utils.mappings import SimpleMap

try:
    from user_title_map import USER_TITLE_MAP as _titles  # noqa: N811
    _titles = tuple(_titles.values())
except ImportError as e:
    warnings.warn('Missing title localization ({})'.format(e), ImportWarning)
    _titles = tuple()

logger = logging.getLogger(__name__)


class _TitleMap(SimpleMap):

    def transform_value(self, value):
        keys = set(('nb', 'en'))
        missing = keys - set(value)
        if missing:
            logger.warning('incomplete translation (missing %s): %s',
                           (', '.join(missing), repr(value)))
        return {k: value[k] for k in keys}


class JobTitleMap(_TitleMap):
    """
    A map of SKO (stillingskode) to job title (WORKTITLE in Cerebrum).

    >>> job_titles = JobTitleMap({
    ...     214: {'nb': 'Rektor', 'en': 'Rector'},
    ...     787: {'nb': "Spesialtannlege", 'en': "Specialist Dentist"},
    ... })

    Supports looking up work titles as code, e.g.:

    >>> job_titles[214]
    {'nb': 'Rektor', 'en': 'Rector'}

    .. or as code + title strings, e.g.:

    >>> job_titles['0214 Rektor']
    {'nb': 'Rektor', 'en': 'Rector'}
    """
    WORK_TITLE_FORMAT = re.compile(r'^(?P<code>\d+).*$')

    def transform_key(self, value):
        if isinstance(value, int):
            return value

        if isinstance(value, six.string_types):
            match = self.WORK_TITLE_FORMAT.match(value)
            if match:
                return int(match.group('code'))
        raise KeyError('invalid work title key: ' + repr(value))


class PersonalTitleMap(SimpleMap):
    """
    A map of personal title ids to personal title.

    A personal title id is a shortened, norwegian title from the source system.

    >>> titles = PersonalTitleMap({
    ...     "Fung.fak.dir": {
    ...         'nb': "Fungerende fakultetsdirektør",
    ...         'en': "Acting Faculty Director",
    ...     },
    ...     "Fung.forsk.led": {
    ...         'nb': "Fungerende forskningsleder",
    ...         'en': "Acting Head of Research",
    ...     }})

    Supports looking up work titles from shortname, e.g.:

    >>> titles['Fung.fak.dir']
    {'nb': "Fungerende fakultetsdirektør", 'en': "Acting Faculty Director"}

    """
    def transform_key(self, value):
        # TODO: normalize text?
        return six.text_type(value)


def _get_titles(title_obj):
    """
    Extract titles from an api title object.

    >>> dict(_get_titles({'norTitle': 'foo', 'engTitle': 'bar'}))
    {'nb': 'foo', 'en': 'bar'}

    """
    for from_lang, to_lang in (('norTitle', 'nb'),
                               ('engTitle', 'en')):
        if from_lang in title_obj:
            yield to_lang, title_obj[from_lang]


def get_job_titles(titles):
    """ Extract job titles from a list of api title objects. """
    for title_obj in titles:
        if 'code' not in title_obj:
            # object is not a job title
            continue

        titles = dict(_get_titles(title_obj))
        if titles:
            yield int(title_obj['code']), titles


def get_personal_titles(titles):
    """ Extract personal titles from a list of api title objects. """
    for title_obj in titles:
        if 'customTitleId' not in title_obj:
            continue

        titles = dict(_get_titles(title_obj))
        if titles:
            yield title_obj['customTitleId'], titles


job_titles = JobTitleMap(get_job_titles(_titles))
personal_titles = PersonalTitleMap(get_personal_titles(_titles))
