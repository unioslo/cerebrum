#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2019 University of Oslo, Norway
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
"""This module contains functionality for maintaining fs groups

Here is a bit of documentation compiled from the
populate_fronter_groups-scripts of uio, uia and uit:

Disse gruppene blir bl.a. brukt ved eksport av data til ClassFronter, og ved
populering av visse NIS (Ifi).

Først litt terminologi:

  - Studieprogram: et studium som normalt leder frem til en grad. Bygges opp
                   ved emner.
  - Emne: den enheten som er byggesteinen i alle studium. Har en omfang, og
          normalt en eller annen form for avsluttende evaluering.
  - Undervisningsenhet (undenh): en instansiering av et emne.
  - Undervisningsaktivitet (undakt): en serie aktivitet knyttet til en
                                     undenh. F.eks. en forelesningsrekke, et
                                     labparti, en serie regneøvinger. Kan også
                                     være en enkel aktivitet.
  - Kurs (evu): Samsvarer med undenh, men er for etter- og videreutdanning
  - Kursaktivitet: Samsvarer med undakt, men er for etter- og videreutdanning
  - Kull: Årsklasse av et studieprogram.

Gruppene er organisert i en tre-struktur.  Øverst finnes en supergruppe; denne
brukes for å holde orden på hvilke grupper som er automatisk opprettet av
dette scriptet, og dermed hvilke grupper som skal slettes i det dataene de
bygger på ikke lenger finnes i FS.  Supergruppen har navnet::

  internal:<domene>:fs:{supergroup}

Her representerer <domene> domenet til institusjonen hvor gruppa hører til.
Denne supergruppen har så medlemmer som også er grupper.
Medlemsgruppene har navn på følgende format::

  internal:<domene>:kurs:<emnekode>
  internal:<domene>:evu:<kurskode>
  internal:<domene>:kull:<studieprogram>

Hver av disse 'enhet-supergruppene' har medlemmer som er grupper med navn på
følgende format::

  internal:<domene>:fs:kurs:<institusjonsnr>:<emnekode>:<versjon>:<sem>:<år>
  internal:<domene>:fs:evu:<kurskode>:<tidsangivelse>
  internal:<domene>:fs:kull:<studieprogram>:<terminkode>:<aar>

Merk at for undenh, så er ikke en tilsvarende 'enhet'-gruppe *helt* ekvivalent
med begrepet undervisningsenhet slik det brukes i FS.  Gruppen representerer
semesteret et gitt kurs startet i (terminnr == 1).  For kurs som strekker seg
over mer enn ett semester vil det derfor i FS finnes multiple
undervisningsenheter, mens gruppen som representerer kurset vil beholde navnet
sitt i hele kurstiden.

'enhet'-gruppene har igjen grupper som medlemmer; disse kan deles i to
kategorier:

  - Grupper (med primærbrukermedlemmer) som brukes ved eksport til
    ClassFronter, har navn på følgende format::

      Rolle ved undenh:     <domene>:fs:<enhetid>:<rolletype>
      Rolle ved undakt:     <domene>:fs:<enhetid>:<rolletype>:<aktkode>
      Ansvar und.enh:       <domene>:fs:<enhetid>:enhetsansvar
      Ansvar und.akt:       <domene>:fs:<enhetid>:aktivitetsansvar:<aktkode>
      Alle stud. v/enh:     <domene>:fs:<enhetid>:student
      Alle stud. v/akt:     <domene>:fs:<enhetid>:student:<aktkode>

  - Ytterligere grupper hvis medlemmer kun er ikke-primære ('sekundære')
    konti. Genereres kun for informatikk-emner, og har navn på formen::

      Ansvar und.enh:       <domene>:fs:<enhetid>:enhetsansvar-sek
      Ansvar und.akt:       <domene>:fs:<enhetid>:aktivitetsansvar-sek:<aktkode>
      Alle stud. v/enh:     <domene>:fs:<enhetid>:student-sek

<rolletype> er en av 12 predefinerte roller (jfr. valid_roles). enhetsansvar
og aktivitetsansvar-gruppene finnes kun for Ifi, som ønsker sine grupper (for
NIS) bygget litt annerledes. Alle slike grupper hvor det er meningen det skal
være accounts, får en passende fronterspread, basert på informasjonen fra
FS. Det er kun slike grupper, hvis fronterspreads vil ha noe å si (dvs. andre
grupper kan også få fronterspreads, men generate_fronter_full.py vil ignorere
dem).

Poenget med å ha dette nokså kompliserte hierarkiet var å tillate
DML/Houston/andre å kunne enkelt si at de vil eksportere en bestemt entitet
til fronter uten å bry seg om gruppene som måtte være generert for denne
entiteten. Dette er ikke mer nødvendig for undenh/undakt/kurs/kursakt, siden
de populeres automatisk, men det *er* nødvendig for kull.

Kullgruppene har også grupper som medlemmer; det er en gruppe med studenter,
samt en gruppe for hver rolle ved kullet::

  Alle stud. på kull:   <domene>:fs:<enhetid>:student
  Rolle ved kull:       <domene>:fs:<enhetid>:<rolletype>

Siden <enhetid> inneholder gruppetypen (kurs, evu og kull), vil det ikke
oppstå navnekollisjon forskjellige enhetgrupper imellom.

I tillegg blir disse nettgruppene laget med spread til Ifi::

  Ansvar und.enh:        g<enhetid>-0          (alle konti)
  Ansvar und.akt:        g<enhetid>-<aktkode>  (alle konti)
  Ansvar enh. og akt.:   g<enhetid>            (alle konti)
  Alle stud. v/enh:      s<enhetid>            (alle konti)
  Alle stud. v/akt:      s<enhetid>-<aktkode>  (primærkonti)
  Alle stud. kun eks:    s<enhetid>-e          (primærkonti)
  Alle akt-ansv:         ifi-g                 (alle konti)
  Alle akt- og enh-ansv: lkurs                 (alle konti)

Som sagt, populering av disse gruppene er litt annerledes. *Alle* med en eller
annen rolle til Ifi-kursene havner i 'g'-ansvarlige-gruppene.


Noen institusjoner (ikke uio) har i tillegg en del grupper som følger en litt
annen navne-syntaks:

   1  Gruppering av alle undervisningsenhet-relaterte grupper ved en
      institusjon
        internal:DOMAIN:fs:INSTITUSJONSNR:undenh
        Eks "internal:hia.no:fs:201:undenh"
      2  Gruppering av alle undervisningsenhet-grupper i et semester
           internal:DOMAIN:fs:INSTITUSJONSNR:undenh:ARSTALL:TERMINKODE
           Eks "internal:hia.no:fs:201:undenh:2004:vår"
         3  Gruppering av alle grupper knyttet til en bestemt und.enhet
              internal:DOMAIN:fs:INSTITUSJONSNR:undenh:ARSTALL:
                TERMINKODE:EMNEKODE:VERSJONSKODE:TERMINNR
              Eks "internal:hia.no:fs:201:undenh:2004:vår:be-102:g:1"
            4  Gruppe med studenter som tar und.enhet
                 Eks "internal:hia.no:fs:201:undenh:2004:vår:be-102:g:1:
                      student"
            4  Gruppe med forelesere som gir und.enhet
                 Eks "internal:hia.no:fs:201:undenh:2004:vår:be-102:g:1:
                      foreleser"
            4  Gruppe med studieledere knyttet til en und.enhet
                 Eks "internal:hia.no:fs:201:undenh:2004:vår:be-102:g:1:
                      studieleder"
   1  Gruppering av alle grupper relatert til studieprogram ved en
      institusjon
        internal:DOMAIN:fs:INSTITUSJONSNR:studieprogram
        Eks "internal:hia.no:fs:201:studieprogram"
      2  Gruppering av alle grupper knyttet til et bestemt studieprogram
           internal:DOMAIN:fs:INSTITUSJONSNR:studieprogram:STUDIEPROGRAMKODE
           Eks "internal:hia.no:fs:201:studieprogram:tekn.eksp"
         3  Gruppering av alle studiekull-grupper for et studieprogram
              internal:DOMAIN:fs:INSTITUSJONSNR:studieprogram:
                STUDIEPROGRAMKODE:studiekull
              Eks "internal:hia.no:fs:201:studieprogram:tekn.eksp:studiekull"
            4  Gruppe med alle studenter i et kull
                 internal:DOMAIN:fs:INSTITUSJONSNR:studieprogram:
                   STUDIEPROGRAMKODE:studiekull:ARSTALL_KULL:
                   TERMINKODE_KULL:student
                 Eks "internal:hia.no:fs:201:studieprogram:tekn.eksp:
                      studiekull:2004:vår:student"
         3  Gruppering av alle personrolle-grupper for et studieprogram
              internal:DOMAIN:fs:INSTITUSJONSNR:studieprogram:
                STUDIEPROGRAMKODE:rolle
              Eks "internal:hia.no:fs:201:studieprogram:tekn.eksp:rolle"
            4  Gruppe med alle studieledere knyttet til et studieprogram
                 internal:DOMAIN:fs:INSTITUSJONSNR:studieprogram:
                   STUDIEPROGRAMKODE:rolle:studieleder
                 Eks "internal:hia.no:fs:201:studieprogram:tekn.eksp:
                      rolle:studieleder"
   1  Gruppering av alle grupper relatert til EVU
        Eks "internal:DOMAIN:fs:INSTITUSJONSNR:evu"
      2  Gruppering av alle grupper knyttet til et bestemt EVU-kurs
           Eks "internal:DOMAIN:fs:INSTITUSJONSNR:evu:94035B:2005 vår"
         3  Gruppe med kursdeltakere på et bestemt EVU-kurs
              Eks "internal:DOMAIN:fs:INSTITUSJONSNR:evu:94035B:2005 vår:
                   kursdeltakere"
         3  Gruppe med forelesere på et bestemt EVU-kurs
              Eks "internal:DOMAIN:fs:INSTITUSJONSNR:evu:94035B:2005 vår:
                   forelesere"
"""

from __future__ import unicode_literals
import re
import datetime
import logging

import cereconf

from Cerebrum.Utils import Factory

logger = logging.getLogger(__name__)

org_regex = r'(?:internal:)?(?P<org>[^:]+):fs'

# Evu-related regexes (non-uio)
evu_supergroup = ':'.join((
    org_regex,
    r'(?P<institusjonsnr>\d+)',
    r'(?P<type>evu)',
))

non_uio_evu = ':'.join((
    evu_supergroup,
    r'(?P<kurs>[^:]+)',
    r'(?P<kurstid>[^:]+)',
))

# Undenh-related regexes (non-uio)
undenh_supergroup = ':'.join((
    org_regex,
    r'(?P<institusjonsnr>\d+)',
    r'(?P<type>undenh)',
))

undenh_term = ':'.join((
    undenh_supergroup,
    r'(?P<year>\d{4})',
    r'(?P<sem>[^:]+)',
))

undenh = ':'.join((
    undenh_term,
    r'(?P<emne>[^:]+)',
    r'(?P<ver>[^:]+)',
    r'(?P<n>[^:]+)',
))

# Studieprogram-related regexes (non-uio)
sp_supergroup = ':'.join((
    org_regex,
    r'(?P<institusjonsnr>\d+)',
    r'(?P<type>studieprogram)',
))

sp = ':'.join((
    sp_supergroup,
    r'(?P<prog>[^:]+)',
))

sp_kull_type = ':'.join((
    sp,
    r'(?P<kull>(studiekull|rolle-kull){1})',
))

sp_rolle_type = ':'.join((
    sp,
    r'(?P<rolle>(rolle-program|rolle){1})',
))

sp_kull = ':'.join((
    sp_kull_type,
    r'(?P<year>\d{4})',
    r'(?P<sem>[^:]+)',
))

# Kurs-related regexes
kurs = ':'.join((
    org_regex,
    r'(?P<type>kurs)',
    r'(?P<emne>[^:]+)',
))

kurs_unit = ':'.join((
    org_regex,
    r'(?P<type>kurs)',
    r'(?P<institusjonsnr>\d+)',
    r'(?P<emne>[^:]+)',
    r'(?P<ver>[^:]+)',
    r'(?P<sem>[^:]+)',
    r'(?P<year>\d{4})',
))

kurs_unit_id = ':'.join((
    org_regex,
    r'(?P<type>kurs)',
    r'(?P<institusjonsnr>\d+)',
    r'(?P<emne>[^:]+)',
    r'(?P<ver>[^:]+)',
    r'(?P<sem>[^:]+)',
    r'(?P<year>\d{4})',
    r'(?P<n>\d+)',
))

# Evu-related regexes
evu = ':'.join((org_regex, r'(?P<type>evu)', r'(?P<kurs>[^:]+)',))
evu_unit = ':'.join((evu, r'(?P<kurstid>[^:]+)',))
evu_year = re.compile(r'(?P<year>\d{4})')

# Kull-related regexes
kull = ':'.join((org_regex, r'(?P<type>kull)', '(?P<prog>[^:]+)'))
kull_unit = ':'.join((kull, '(?P<termin>[^:]+)', r'(?P<year>\d+)'))

# Role-related regexes
role = r'(?P<role>[^:]+)'
subrole = ':'.join((role, r'(?P<akt>[^:]+)'))


def make_regex(*args):
    return re.compile('^' + ':'.join(args) + '$')


def _date_or_none(d):
    if d is None:
        return None
    return d.pydate()


def get_year(cat, match):
    try:
        if cat in ('evu-ue',
                   'evu-role',
                   'evu-role-sub',
                   'non-uio-evu',
                   'non-uio-evu-role'):
            year = max(int(year) for year in evu_year.findall(
                match.group('kurstid')
            ))
        else:
            year = int(match.group('year'))
    except IndexError:
        year = None
    except ValueError:
        year = None
        logger.error('Non-numeric year!')
    return year


def get_expire_date(lifetime, year, group_name, today=None):
    if not lifetime:
        return None
    today = today or datetime.date.today()
    if not year:
        return today + datetime.timedelta(days=lifetime * 365)
    if not today.year + 5 > year > 1990:
        logger.warning('Year %s not in allowed range, %s',
                       year,
                       group_name)
        return today + datetime.timedelta(days=lifetime * 365)

    years_until_expiration = year + lifetime + 1 - today.year
    if years_until_expiration <= 0:
        return (today +
                datetime.timedelta(days=cereconf.FS_GROUP_GRACE_PERIOD))
    return today + datetime.timedelta(days=years_until_expiration * 365)


class FsGroupCategorizer(object):
    def __init__(self, db, fs_group_prefix=None):
        self.db = db
        self.fs_group_prefix = fs_group_prefix or cereconf.FS_GROUP_PREFIX
        if self.fs_group_prefix is None:
            raise Exception('No prefix given')
        # The elements of categories are tuples of category, regex and lifetime
        self.categories = (
            ('super', make_regex(org_regex, '{supergroup}'), None),
            ('auto', make_regex(org_regex, '{autogroup}'), None),
            ('ifi_auto_fg', make_regex(org_regex, '{ifi_auto_fg}'), None),
            # fs:kurs
            ('kurs', make_regex(kurs), 3),
            ('kurs-ue', make_regex(kurs_unit), 2),
            ('kurs-role', make_regex(kurs_unit_id, role), 2),
            ('kurs-role-sub', make_regex(kurs_unit_id, subrole), 2),
            # fs:evu
            ('evu', make_regex(evu), 3),
            ('evu-ue', make_regex(evu_unit), 2),
            ('evu-role', make_regex(evu_unit, role), 2),
            ('evu-role-sub', make_regex(evu_unit, subrole), 2),
            # fs:kull
            ('kull-ue', make_regex(kull), 6),
            ('kull-ua', make_regex(kull_unit), 6),
            ('kull-role', make_regex(kull_unit, role), 6),

            # Non uio types:
            # fs:<institusjonsnr>:evu
            ('non-uio-evu-super', make_regex(evu_supergroup), None),
            ('non-uio-evu', make_regex(non_uio_evu), 2),
            ('non-uio-evu-role', make_regex(non_uio_evu, role), 2),
            # fs:<institusjonsnr>:undenh
            ('undenh-super', make_regex(undenh_supergroup), None),
            ('undenh', make_regex(undenh), 3),
            ('undenh-term', make_regex(undenh_term), 3),
            ('undenh-role', make_regex(undenh, role), 2),
            ('undenh-role-sub', make_regex(undenh, subrole), 2),
            # fs:<institusjonsnr>:studieprogram
            ('sp-super', make_regex(sp_supergroup), None),
            ('sp', make_regex(sp), 3),

            ('sp-kull-type', make_regex(sp_kull_type), 6),
            ('sp-kull-role', make_regex(sp_kull, role), 6),
            ('sp-kull-role-sub', make_regex(sp_kull, subrole), 6),

            ('sp-rolle-type', make_regex(sp_rolle_type), 3),
            ('sp-rolle', make_regex(sp_rolle_type, role), 3),
        )

    def get_groups(self):
        gr = Factory.get('Group')(self.db)
        # co = Factory.get('Constants')(db)
        for row in gr.search(name='%{}%'.format(self.fs_group_prefix)):
            yield {
                'id': int(row['group_id']),
                'name': row['name'],
                # 'visibility': co.GroupVisibility(row['visibility']),
                # 'description': row['description'],
                'expire_date': _date_or_none(row['expire_date']),
            }

    def get_group_category(self, group_name):
        category = match = lifetime = None
        for cat, regex, l in self.categories:
            m = regex.match(group_name)
            if m:
                if not category:
                    category = cat
                    match = m
                    lifetime = l
                else:
                    raise LookupError('Multiple categories for %s', group_name)

        if category:
            return category, match, lifetime
        raise LookupError('No category for %s', group_name)
