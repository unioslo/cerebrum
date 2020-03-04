# -*- coding: utf-8 -*-
# Copyright 2002-2019 University of Oslo, Norway
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

"""Klasser for aksesering av FS.  Institusjons-spesifik bruk av FS bør
håndteres ved å subklasse relevante deler av denne koden.  Tilsvarende
dersom man skal ha kode for en spesifik FS-versjon.

Disse klassene er ment brukt ved å instansiere klassen FS
"""
from __future__ import unicode_literals
import cereconf
import time
import xml.sax
import collections
import operator

from Cerebrum import database as Database
from Cerebrum import Errors
from Cerebrum.Utils import Factory, dyn_import

import phonenumbers


# A tuple to hold the version number
Version = collections.namedtuple('Version', 'major minor patch'.split())


def version_less(lhs, rhs):
    if lhs.major != rhs.major:
        return lhs.major < rhs.major
    if lhs.minor != rhs.minor:
        return lhs.minor < rhs.minor
    return lhs.patch < rhs.patch


def version_less_equal(lhs, rhs):
    if lhs.major != rhs.major:
        return lhs.major < rhs.major
    if lhs.minor != rhs.minor:
        return lhs.minor < rhs.minor
    return lhs.patch <= rhs.patch


def _get_fs_version(db):
    """Return FS version number.
    :param db: Database object.

    :return: tuple(major, minor, patch)
    """
    result = db.query_1("SELECT Sisteversjon_Database FROM fs.Systemverdier")
    assert result[:2] == "FS"
    return Version(*map(int, result[2:].split(".")[:3]))


class VersionSpec(object):
    """Holds a version spec for an implementation. We need this to deduce if
    a version can be used. Generally,
    * [v1, v2], [v1, v2), (v1, v2), or (v1, v2]
    * <v, <=v, or =v
    * >v, >=v
    """
    __slots__ = ('start', 'end', 'start_open', 'end_open')

    @staticmethod
    def assert_version(ver, allow_none=True):
        """Create a Version from ver"""
        if ver is None:
            if allow_none:
                return None
            raise Errors.ProgrammingError("Specified FS version None")
        if isinstance(ver, Version):
            return ver
        if isinstance(ver, basestring):
            if '.' in ver:
                return VersionSpec.assert_version(ver.split('.'))
            return Version(int(ver), 0, 0)
        if isinstance(ver, collections.Sequence):
            if len(ver) > 3:
                return Version(*ver[:3])
            ver = list(ver)
            while len(ver) < 3:
                ver.append(0)
            return Version(*map(int, ver))

    def __init__(self, start=None, end=None, start_open=False, end_open=True):
        self.start = self.assert_version(start)
        self.end = self.assert_version(end)
        self.start_open = start_open
        self.end_open = end_open
        if self.start and self.end and self.start > self.end:
            raise Errors.ProgrammingError(
                "VersionSpec cannot have end > start")
        if start is None and end is None:
            raise Errors.ProgrammingError("VersionSpec empty")

    def __eq__(self, other):
        return (isinstance(other, VersionSpec) and
                self.start == other.start and
                self.end == other.end and
                self.start_open == other.start_open and
                self.end_open == other.end_open)

    def __hash__(self):
        return reduce(operator.xor, map(hash,
                                        [self.start, self.end,
                                         self.start_open, self.end_open]))

    def __lt__(self, other):
        """
        """
        if self.start and other.start:
            return version_less(self.start, other.start)
        if self.end and other.end:
            return version_less(self.end, other.end)
        if self.start:
            if version_less(self.start, other.end):
                raise Errors.ProgrammingError(
                    "version spec conflict: {} and {}".format(self, other))
            return False
        if version_less(other.start, self.end):
            raise Errors.ProgrammingError("version spec conflict: {} and {}"
                                          .format(self, other))
        return True

    def __str__(self):
        st, e = self.start, self.end
        if st and e:
            return "{}{}.{}.{}, {}.{}.{}{}".format(
                '(' if self.start_open else '[',
                st.major, st.minor, st.patch,
                e.major, e.minor, e.patch,
                ')' if self.end_open else ']')
        elif st:
            return "{}{}.{}.{}".format(
                '>' if self.start_open else '>=',
                st.major, st.minor, st.patch)
        else:
            return "{}{}.{}.{}".format(
                '<' if self.end_open else '<=',
                st.major, st.minor, st.patch)

    def __repr__(self):
        return "VersionSpec({}, {}, {}, {})".format(self.start, self.end,
                                                    self.start_open,
                                                    self.end_open)

    def matches(self, version):
        """Returns true iff version matches this spec
        :param Version version: Version to check for.
        :returns: Bool
        """

        # init operators:
        # Operator open means strict less, closed means less or equal
        # op_start(self.start, version) must be true, or self.start is None
        op_start = version_less if self.start_open else version_less_equal
        # op_end(version, self.end) must be true, or self.end is None
        op_end = version_less if self.end_open else version_less_equal

        if self.start and self.end:
            return op_start(self.start, version) and op_end(version, self.end)
        elif self.start:
            return op_start(self.start, version)
        else:
            return op_end(version, self.end)


def parse_version_spec(spec):
    """
    Parse a version spec.

    >>> parse_version_spec("<1")
    <1.0.0
    >>> parse_version_spec(">=7.3")
    >=7.3.0
    >>> parse_version_spec((7, 8))
    [7.0.0, 8.0.0)
    >>> parse_version_spec({'start': 6, 'end': 8, 'end_open': False})
    [6.0.0, 8.0.0]

    :param str/tuple/dict spec: Specifies a VersionSpec
    :returns: Matching version spec
    :raises: Cerebrum.Errors.ProgrammingError on fail
    """
    if isinstance(spec, VersionSpec):
        return spec
    if isinstance(spec, basestring):
        if spec[0] in '<>=':
            closed = spec[1] == '='
            ver = spec[1+closed:].split('.')
            if spec[0] == '<':
                return VersionSpec(end=ver, end_open=not closed)
            elif spec[0] == '>':
                return VersionSpec(start=ver, start_open=not closed)
            return VersionSpec(start=ver, end=ver, end_open=False)
        elif spec[0] in '([' and spec[-1] in ')]':
            start_open = spec[0] == '('
            end_open = spec[-1] == ')'
            start, end = [int(x.strip().split('.'))
                          for x in spec[1:-1].split(',')]
            return VersionSpec(start=start,
                               end=end,
                               start_open=start_open,
                               end_open=end_open)
    if isinstance(spec, collections.Sequence):
        if isinstance(spec[0], collections.Sequence):
            return VersionSpec(*spec)
        return VersionSpec(spec)
    if isinstance(spec, collections.Mapping):
        return VersionSpec(**spec)
    raise Errors.ProgrammingError("Illegal version spec: {}".format(spec))


_default_fs_config = collections.defaultdict(
    lambda: collections.defaultdict(dict))


def fsobject(name, versions='>=1', version_to=None):
    """Declare object as fs-object to make_fs.
    Use this as:
        @fsobject('FS', '>7.1')
        class FS…

    :param str name: Name of accessor
    :param versions: Version spec, see parse_version_spec().
    :param version_to: if set, versions param is interpreted as from version,
    and (version, version_to) is sent to parse_version_spec().
    :return: Decorating function
    """
    import inspect
    if version_to:
        versions = tuple(versions, version_to)

    def fn(cls):
        module = inspect.getmodule(cls)
        if module is None:
            module = '__main__'
        else:
            module = module.__name__
        _default_fs_config[module][name][parse_version_spec(versions)] = cls
        return cls
    return fn


def find_best_version(module, name, version):
    """Finds the newest version matching spec.

    :param str module: Module name (e.g. 'Cerebrum.modules.no.access_FS)
    :param str name: Component name (e.g. FS)
    :param Version version: FS version

    :returns: Class for given component
    """
    candidates = _default_fs_config[module][name]
    for spec, cls in sorted(candidates.items(), key=operator.itemgetter(0),
                            reverse=True):
        if spec.matches(version):
            return cls


def make_fs(db=None, user=None, database=None, override_version=None):
    """Create FS object based on actual version number.
    Default is to look in this module, but if cereconf.FS_MODULE is set,
    it will override the default.

    :param Database db: DB to use, or none to use other params.
    :param str user: Username for db, defaults to cereconf.FS_USER
    :param str database: Database name for db,
        defaults to cereconf.FS_DATABASE_NAME
    :param Version override_version: Don't find version in db
        (useful for testing)
    :returns: New FS object, initialized with db
    """
    import inspect
    if db is None:
        user = user or cereconf.FS_USER
        database = database or cereconf.FS_DATABASE_NAME
        DB_driver = getattr(cereconf, 'DB_DRIVER_ORACLE', 'cx_Oracle')
        db = Database.connect(user=user, service=database,
                              DB_driver=DB_driver)
    if override_version:
        version = override_version
    else:
        version = _get_fs_version(db)
    module = getattr(cereconf, 'FS_MODULE', inspect.getmodule(
        make_fs).__name__)
    dyn_import(module)
    cls = find_best_version(module, 'FS', version)
    if cls:
        return cls(db)
    raise RuntimeError("Module {} holds no suitable FS for version {}"
                       .format(module, version))

# TODO: En del funksjoner finnes både som get_ og list_ variant.  Det
# kunne være en fordel om man etablerte en mekanisme for å slå sammen
# disse.  Det vil både redusere kodeduplisering, og være nyttig dersom
# man skal foreta inkrementelle operasjoner basert på endringer i FS.

# Note: The oracle database-driver does not support dates before 1970.
# Thus TO_DATE must be used when inserting dates


class FSObject(object):
    """Parent class that all other fs-access methods inherit.
    Provides a number of utility methods."""

    def __init__(self, db):
        self.db = db
        t = time.localtime()[0:3]
        if t[1] <= 6:
            self.sem = 'V'
            self.semester = 'VÅR'
            self.prev_semester = 'HØST'
            self.next_semester = 'HØST'
            self.prev_semester_year = t[0] - 1
            self.next_semester_year = t[0]
        else:
            self.sem = 'H'
            self.semester = 'HØST'
            self.prev_semester = 'VÅR'
            self.next_semester = 'VÅR'
            self.prev_semester_year = t[0]
            self.next_semester_year = t[0] + 1
        self.year = t[0]
        self.mndnr = t[1]
        self.dday = t[2]
        self.YY = str(t[0])[2:]
        self.institusjonsnr = cereconf.DEFAULT_INSTITUSJONSNR

    def _is_alive(self):
        return "NVL(p.status_dod, 'N') = 'N'\n"

    def _get_termin_aar(self, only_current=False):
        """Generate an SQL query part for limiting registerkort to the current
        term and maybe also the previous term. The output from this method
        should be a part of an SQL query, and must have a reference to
        L{fs.registerkort} by the character 'r'.

        FS is working in terms and not with proper dates, so the query is
        generated differently depending on the current date:

        - From 1st of January to 15th of February: This year's 'VÅR' is
          returned. If L{only_current} is False, also last year's 'HØST' is
          included.

        - From 15th of February to 30th of June: Only this year's 'VÅR' is
          returned.

        - From 1st of July to 15th of September: This year's 'HØST' is
        returned. If L{only_current} is False, also this year's 'VÅR' is
        included.

        - From 15th of September to 31st of December: Only this year's 'HØST'
        is returned.

        @type only_current: bool
        @param only_current: If set to True, the query is limiting to only the
            current term. If False, the previous term is also included if we
            are early in the current term. This has no effect if the current
            date is more than halfway into the current term.

        @rtype: string
        @return: An SQL formatted string that should be put in a larger query.
            Example:
                (r.terminkode = 'HØST' and r.arstall = 2013)
            where 'r' refers to 'fs.registerkort r'.

        """
        if self.mndnr <= 6:
            # Months January - June == Spring semester
            current = u"(r.terminkode = :spring AND r.arstall=%s)\n" % (
                self.year)
            if only_current or self.mndnr >= 3 or (self.mndnr == 2 and
                                                   self.dday > 15):
                return current
            return (u"(%s OR (r.terminkode = :autumn AND r.arstall=%d))\n" % (
                current, self.year-1))
        # Months July - December == Autumn semester
        current = u"(r.terminkode = :autumn AND r.arstall=%d)\n" % self.year
        if only_current or self.mndnr >= 10 or (self.mndnr == 9 and
                                                self.dday > 15):
            return current
        return (u"(%s OR (r.terminkode = :spring AND r.arstall=%d))\n" % (
            current, self.year))

    def _get_next_termin_aar(self):
        """Henter neste semesters terminkode og årstall."""
        if self.mndnr <= 6:
            next = "(r.terminkode = :autumn AND r.arstall=%s)\n" % self.year
        else:
            next = "(r.terminkode = :spring AND r.arstall=%s)\n" % (
                self.year + 1)
        return next


@fsobject('person')
class Person(FSObject):
    """Update person class with new structure in FS 7.8.

    What is new?
    ============

    To us, the important change is how telephone numbers are stored.
    FS now has a new table ``fs.persontelefon``, replacing various instances
    of fields named ``telefonX``. In more detail, various tables would
    have fields named

    * ``telefonlandnr_X``
    * ``telefonretnnr_X``
    * ``telefonnr_X``

    coupling the data for a telephone number. Each of these instances is
    replaced with a row in fs.persontelefon, and with an additional
    ``telefonnrtypekode`` signifying the X.

    The following have been converted from FS 7.7:

    +-----------+------------+---------+
    | table     | X          | kode    |
    +-----------+------------+---------+
    | person    | hjemsted   | HJEM    |
    | person    | mobil      | MOBIL   |
    | fagperson | fax_arb    | FAKS    |
    | student   | semtelefon | SEM     |
    | fagperson | arbeide    | ARB     |
    | soknad    | kontakt    | KONTAKT |
    | soknad    | kontakt2   | KONTAKT |
    | student   | arbeid     | ARB     |
    +-----------+------------+---------+

    The field ``telefonretnnr`` is gone, and if the value is set, it
    is baked into ``telefonnr``: telefonnr = telefonretnnr SPACE telefonnr.

    The field ``telefonlandnr`` have gotten leading regex(\\+?0*) stripped
    (i.e. +47, +0047, and 0047 → 47). If telefonlandnr was unset, the new
    value assumes Norway, i.e. NULL → 47.

    The table indicates priority (most important at top). I.e. if a person has
    ``ARB`` both from ``fagperson`` and ``student``, the value from
    ``fagperson`` will win, but the value from ``student`` is not discarded,
    rather it is inserted to the ``merknad`` field of ``persontelefon``
    as (yes, there is a typing error in FS upgrade script)::

        'Alterativt nr: {telefonlandnr} {telefonretnnr} {telefonnr}'.format(…)
    """
    def add_telephone(self, fodselsdato, personnr, kind, phone, country=None):
        """Insert telephone number for person.

        :param fodselsdato, personnr: Identifies person.
        :param phone: The telephone number
        """
        if not isinstance(kind, basestring):
            kind = kind[0]
        qry = """
        INSERT INTO fs.persontelefon (institusjonsnr_eier,
                                      fodselsdato,
                                      personnr,
                                      telefonnrtypekode,
                                      telefonlandnr,
                                      telefonnr)
        VALUES (:instno, :fodselsdato, :personnr, :kind, :country, :phone)"""
        country, phone = self._phone_to_country(country, phone)
        return self.db.execute(qry, {'fodselsdato': fodselsdato,
                                     'personnr': personnr,
                                     'country': country,
                                     'phone': phone,
                                     'kind': kind,
                                     'instno': cereconf.DEFAULT_INSTITUSJONSNR
                                     })

    def update_telephone(self, fodselsdato, personnr, kind, phone,
                         country=None):
        """Insert telephone number for person.

        :param fodselsdato, personnr: Identifies person.
        :param phone: The telephone number
        """
        if not isinstance(kind, basestring):
            kind = kind[0]
        binds = {'fodselsdato': fodselsdato,
                 'personnr': personnr,
                 'kind': kind}

        if phone is None:
            self.db.execute("""DELETE FROM fs.persontelefon
                            WHERE fodselsdato = :fodselsdato AND
                                  personnr = :personnr AND
                                  telefonnrtypekode = :kind""",
                            binds)
        qry = """
        UPDATE fs.persontelefon
        SET
            telefonlandnr = :country,
            telefonnr = :phone
        WHERE fodselsdato = :fodselsdato AND
              personnr = :personnr AND
              telefonnrtypekode = :kind"""
        binds['country'], binds['phone'] = self._phone_to_country(country,
                                                                  phone)
        return self.db.execute(qry, binds)

    def get_telephone(self, fodselsdato, personnr, institusjonsnr, kind=None,
                      fetchall=False):
        """List persons telephone number.

        :param fodselsdato, personnr: Keys for person.
        :param str kind: Type of telephone (HJEM, MOBIL, FAKS or ARB) None=all.
        :param fetchall: Fetch all?
        :returns: DB rows
        """
        qry = """
        SELECT telefonlandnr, telefonnr, telefonnrtypekode
        FROM fs.persontelefon
        WHERE fodselsdato = :fodselsdato AND personnr = :personnr {kind}
        """
        binds = {'fodselsdato': fodselsdato,
                 'personnr': personnr}
        if kind:
            where_kind = 'AND telefonnrtypekode = :kind'
            binds['kind'] = kind
        else:
            where_kind = ''
        return self.db.query(qry.format(kind=where_kind), binds,
                             fetchall=fetchall)

    def get_person(self, fnr, pnr):
        return self.db.query("""
        SELECT fornavn, etternavn, fornavn_uppercase, etternavn_uppercase,
               emailadresse, kjonn, dato_fodt
        FROM fs.person
        WHERE fodselsdato=:fnr AND personnr=:pnr""",  {'fnr': fnr, 'pnr': pnr})

    def add_person(self, fnr, pnr, fornavn, etternavn, email, kjonn,
                   birth_date, ansattsnr=None):
        """Adds a person to the FS database.
        Ansattnr is not used in this implementation."""

        return self.db.execute("""
        INSERT INTO fs.person
          (fodselsdato, personnr, fornavn, etternavn, fornavn_uppercase,
           etternavn_uppercase, emailadresse, kjonn, dato_fodt)
        VALUES
          (:fnr, :pnr, :fornavn, :etternavn, UPPER(:fornavn2),
          UPPER(:etternavn2), :email, :kjonn,
          TO_DATE(:birth_date, 'YYYY-MM-DD'))""", {
            'fnr': fnr, 'pnr': pnr, 'fornavn': fornavn,
            'etternavn': etternavn, 'email': email,
            'kjonn': kjonn, 'birth_date': birth_date,
            'fornavn2': fornavn, 'etternavn2': etternavn})

    def set_ansattnr(self, fnr, pnr, asn):
        """Sets the ansattnr for a person. This is NOT implemented."""
        pass

    def get_ansattnr(self, fnr, pnr):
        """Gets the ansattnr for a person. This is NOT implemented."""
        pass

    def get_personroller(self, fnr, pnr):
        """Helt alle personroller til fnr+pnr."""

        return self.db.query("""
        /* Vi henter absolutt *alle* attributtene og lar valideringskoden vår
           ta hånd om verifisering av attributtene. På denne måten får vi en
           ERROR-melding i loggene når FS finner på å populere tidligere
           upopulerte attributter. */
        SELECT *
        FROM fs.personrolle
        WHERE
          fodselsdato=:fnr AND
          personnr=:pnr AND
          dato_fra < SYSDATE AND
          NVL(dato_til,SYSDATE) >= sysdate""", {'fnr': fnr,
                                                'pnr': pnr})

    def get_fagperson(self, fodselsdato, personnr):
        return self.db.query("""
        SELECT
          fodselsdato, personnr, adrlin1_arbeide, adrlin2_arbeide,
          postnr_arbeide, adrlin3_arbeide, arbeidssted,
          institusjonsnr_ansatt, faknr_ansatt, instituttnr_ansatt,
          gruppenr_ansatt, stillingstittel_norsk,
          status_aktiv
        FROM fs.fagperson
        WHERE fodselsdato=:fodselsdato AND personnr=:personnr
        """, {"fodselsdato": fodselsdato, "personnr": personnr})

    def add_fagperson(self, fodselsdato, personnr, **rest):
        binds = {"fodselsdato": fodselsdato, "personnr": personnr}
        binds.update(rest)
        return self.db.execute("""
        INSERT INTO fs.fagperson
          (%s)
        VALUES
          (%s)
        """ % (", ".join(binds),
               ", ".join(":" + x for x in binds)), binds)

    def update_fagperson(self, fodselsdato, personnr, **rest):
        """Updates the specified columns in fagperson"""

        binds = {"fodselsdato": fodselsdato, "personnr": personnr, }
        names_to_set = ["%s = :%s" % (x, x) for x in rest]
        binds.update(rest)
        return self.db.execute("""
        UPDATE fs.fagperson
        SET %s
        WHERE fodselsdato = :fodselsdato AND personnr = :personnr
        """ % ", ".join(names_to_set), binds)

    def is_dead(self, fodselsdato, personnr):
        """Check if a given person is registered as dead (status_dod) in FS."""
        ret = self.db.query("""
            SELECT p.status_dod as dod
            FROM fs.person p
            WHERE p.fodselsdato = :fodselsdato AND p.personnr = :personnr""",
                            {'fodselsdato': fodselsdato, 'personnr': personnr})
        if ret:
            return ret[0]['dod'] == 'J'
        return False

    def list_dead_persons(self):  # GetDod
        """Henter en liste med de personer som ligger i FS og som er
           registrert som død.  Listen kan sikkert kortes ned slik at
           man ikke tar alle, men i denne omgang så gjør vi det
           slik."""
        qry = """
        SELECT p.fodselsdato, p.personnr
        FROM   fs.person p
        WHERE  p.status_dod = 'J'"""
        return self.db.query(qry)

    def list_status_nettpubl(self, fodselsdato=None, personnr=None, type=None):
        """Hent info om data om en student skal publiseres i
        nettkatalogen eller ikke.

        Tabellen fs.PERSONAKSEPTANSE benyttes for å angi om en student
        har akseptert at det blir publisert data i nettkatalogen eller
        ikke.

        Dersom det finnes en rad i denne tabellen med
        AKSEPTANSETYPEKODE='NETTPUBL' og STATUS_SVAR='J', skal data om
        studenten publiseres i nettkatalogen. Hvis ikke, skal data om
        studenten ikke publiseres.

        Det er ikke påkrevd med noen noen entry i denne tabellen, slik
        at det kan finnes personer det ikke forekommer noen rader
        for. Data om disse studentene skal ikke publiseres. Man har
        dermed 3 forskjellige scenarioer:

        1) Det finnes ingen rad i tabellen med
           AKSEPTANSETYPEKODE='NETTPUBL'.

        2) Det finnes en rad i tabellen med
           AKSEPTANSETYPEKODE='NETTPUBL' og STATUS_SVAR='N'.

        3) Det finnes en rad i tabellen med
           AKSEPTANSETYPEKODE='NETTPUBL' og STATUS_SVAR='J'.

        For scenario 1 og 2 skal data om studenten ikke publiseres,
        for scenario 3 skal data om studenten publiseres.

        Merk: Funksjonen er skrevet generell så man kan hente ut alle
        typer akseptansekode.
        """

        check_extra = ""
        if fodselsdato and personnr and type:
            check_extra = """WHERE fodselsdato=:fodselsdato
                             AND personnr=:personnr
                             AND akseptansetypekode=:type"""
        elif fodselsdato and personnr:
            check_extra = ("WHERE fodselsdato=:fodselsdato "
                           "AND personnr=:personnr")
        elif type:
            check_extra = "WHERE akseptansetypekode=:type"

        qry = """
        SELECT DISTINCT
            fodselsdato, personnr, akseptansetypekode, status_svar,
            dato_svar
        FROM
            fs.personakseptanse
        %s
        ORDER by akseptansetypekode, status_svar
        """ % (check_extra)
        return self.db.query(qry, locals())

    def list_fnr_endringer(self):  # GetFnrEndringer
        """Hent informasjon om alle registrerte fødselsnummerendringer"""
        qry = """
        SELECT fodselsdato_naverende, personnr_naverende,
               fodselsdato_tidligere, personnr_tidligere,
               TO_CHAR(dato_foretatt, 'YYYY-MM-DD HH24:MI:SS') AS dato_foretatt
        FROM fs.fnr_endring
        ORDER BY dato_foretatt"""
        return self.db.query(qry)

    def list_email(self, fetchall=False):  # GetAllPersonsEmail
        return self.db.query("""
        SELECT fodselsdato, personnr, emailadresse
        FROM fs.person""", fetchall=fetchall)

    def write_email(self, fodselsdato, personnr, email):  # WriteMailAddr
        self.db.execute("""
        UPDATE fs.person
        SET emailadresse=:email
        WHERE fodselsdato=:fodselsdato AND personnr=:personnr""",
                        {'fodselsdato': fodselsdato,
                         'personnr': personnr,
                         'email': email})

    def list_uname(self, fetchall=False):  # GetAllPersonsUname
        return self.db.query("""
        SELECT fodselsdato, personnr, brukernavn
        FROM fs.person""", fetchall=fetchall)

    def write_uname(self, fodselsdato, personnr, uname):  # WriteUname
        self.db.execute("""
        UPDATE fs.person
        SET brukernavn = :uname
        WHERE fodselsdato = :fodselsdato AND personnr = :personnr""",
                        {'fodselsdato': fodselsdato,
                         'personnr': personnr,
                         'uname': uname})

    # Mapping 7.8 schema to older schema
    _telephone_mapping = {
        'HJEM': [('person', 'hjemsted')],
        'MOBIL': [('person', 'mobil')],
        'FAKS': [('fagperson', 'fax_arb')],
        # 'SEM': [('student', 'semtelefon')],
        'ARB': [('fagperson', 'arbeide'),
                ('student', 'arbeid')],
        # 'KONTAKT': [('soknad', 'kontakt')] ,
    }

    def _phone_to_country(self, country, phone):
        if phone is None:
            return None, None
        if phone.startswith('+'):
            p = phonenumbers.parse(phone)
            num = str(p.national_number)
            if p.country_code == 47 and len(num) > 8:
                raise ValueError("FS doesn't allow more than 8 digits in "
                                 "Norwegian phone numbers")
            return str(p.country_code), num
        elif phone.startswith('00'):
            # TODO: Should we do this?
            p = phonenumbers.parse('+' + phone[2:])
            num = str(p.national_number)
            if p.country_code == 47 and len(num) > 8:
                raise ValueError("FS doesn't allow more than 8 digits in "
                                 "Norwegian phone numbers")
            return str(p.country_code), num
        elif country is None or country == '47':
            p = phonenumbers.parse(phone, region='NO')
            num = str(p.national_number)
            if len(num) > 8:
                raise ValueError("FS doesn't allow more than 8 digits in "
                                 "Norwegian phone numbers")
            return str(p.country_code), num
        else:
            p = phonenumbers.parse(phone,
                                   region=phonenumbers.
                                   region_code_for_country_code(int(country)))
            return str(p.country_code), str(p.national_number)


@fsobject('student')
class Student(FSObject):
    """Student in FS 7.8 and up.
    See class Person78.
    """

    def get_student(self, fnr, pnr):
        """Hent generell studentinfo for en person. Kan brukes for å
           registrere eksterne id'er (studentnr, bibsysnr) i Cerebrum
           for alle personer som har en studentforekomst"""
        return self.db.query("""
        SELECT fodselsdato, personnr, studentnr_tildelt, dato_opprettet,
               bibsyslanetakerid
        FROM fs.student
        WHERE fodselsdato=:fnr AND personnr=:pnr""",  {'fnr': fnr, 'pnr': pnr})

    def list_semreg(self):   # GetStudinfRegkort
        """Hent informasjon om semester-registrering og betaling"""
        qry = """
        SELECT DISTINCT
               r.fodselsdato, r.personnr, p.dato_fodt, r.regformkode,
               r.dato_endring, r.dato_opprettet
        FROM fs.registerkort r, fs.person p
        WHERE r.fodselsdato = p.fodselsdato AND r.personnr = p.personnr AND
        %s AND
        NVL(r.status_ugyldig, 'N') = 'N'
        """ % self._get_termin_aar(only_current=1)
        return self.db.query(qry, {'autumn': 'HØST',
                                   'spring': 'VÅR'})

    # GetStudentSemReg
    def get_semreg(self, fnr, pnr, only_valid=True, semester='current'):
        """Hent data om semesterregistrering for student i nåværende semester.
        Henter for neste semester om man setter semester='next'.
        Om only_valid er True, vil berre gyldige registreringar bli
        returnerte, altså det som reknast som "gyldig registerkort"."""
        sjekk_betaling = ''
        if only_valid:
            sjekk_betaling = """r.status_bet_ok = 'J'
                                AND r.status_reg_ok = 'J' AND"""
        # Default dict for the query
        qry_dict = {'semester': self.semester,
                    'year': self.year,
                    'termin': self._get_termin_aar(only_current=True),
                    'is_alive': self._is_alive(),
                    'sjekk_betaling': sjekk_betaling}
        # Modified query for next semester
        if semester == 'next':
            qry_dict = {'semester': self.next_semester,
                        'year': self.next_semester_year,
                        'termin': self._get_next_termin_aar(),
                        'is_alive': self._is_alive(),
                        'sjekk_betaling': sjekk_betaling}
        qry = """
        SELECT DISTINCT
          r.regformkode, r.betformkode, r.dato_betaling,
          r.dato_regform_endret, r.status_bet_ok, r.status_reg_ok,
          r.arstall, r.terminkode,
          (SELECT dato_endring from
            (SELECT f.dato_endring
             FROM fs.fakturareskontro f
             WHERE f.fodselsdato = :fnr AND
                   f.personnr = :pnr AND
                   f.terminkode = '%(semester)s' AND
                   f.arstall = %(year)s
             ORDER BY f.dato_endring DESC)
           WHERE rownum = 1) dato_endring
        FROM fs.registerkort r, fs.person p
        WHERE r.fodselsdato = :fnr AND
              r.personnr = :pnr AND
              %(termin)s AND
              %(sjekk_betaling)s
              NVL(r.status_ugyldig, 'N') = 'N' AND
              r.fodselsdato = p.fodselsdato AND
              r.personnr = p.personnr AND
              %(is_alive)s
        """ % qry_dict
        return self.db.query(qry, {'fnr': fnr,
                                   'pnr': pnr,
                                   'autumn': 'HØST',
                                   'spring': 'VÅR'})

    # TODO: Måten vi knytter vurdkombenhet mot vurdtidkode bør
    # sjekkes nærmere med Geir.
    def list_eksamensmeldinger(self):  # GetAlleEksamener
        """Hent ut alle eksamensmeldinger i nåværende sem.
        samt fnr for oppmeldte(topics.xml)"""
        qry = """
        SELECT p.fodselsdato, p.personnr, p.dato_fodt, vm.emnekode,
               vm.studieprogramkode, vm.arstall,
               vm.versjonskode, vm.vurdtidkode, vt.terminkode_gjelder_i,
               vt.arstall_gjelder_i
        FROM fs.person p, fs.vurdkombmelding vm,
             fs.vurderingskombinasjon vk, fs.vurderingstid vt,
             fs.vurdkombenhet ve
        WHERE p.fodselsdato=vm.fodselsdato AND
              p.personnr=vm.personnr AND
              vk.institusjonsnr = vm.institusjonsnr AND
              vk.emnekode = vm.emnekode AND
              vk.versjonskode = vm.versjonskode AND
              vk.vurdkombkode = vm.vurdkombkode AND
              vk.vurdordningkode IS NOT NULL and
              ve.arstall = vm.arstall AND
              ve.vurdtidkode = vm.vurdtidkode AND
              ve.emnekode = vm.emnekode AND
              ve.versjonskode = vm.versjonskode AND
              ve.vurdkombkode = vm.vurdkombkode AND
              ve.vurdtidkode = vm.vurdtidkode AND
              ve.institusjonsnr = vm.institusjonsnr AND
              ve.arstall_reell=vt.arstall AND
              ve.vurdtidkode_reell=vt.vurdtidkode AND
              vt.arstall_gjelder_i = %s AND
              %s
        ORDER BY fodselsdato, personnr
        """ % (self.year, self._is_alive())
        return self.db.query(qry)

    # TODO: Denne må oppdateres til å samsvare med
    # list_eksamensmeldinger!
    def get_eksamensmeldinger(self, fnr, pnr):  # GetStudentEksamen
        """Hent alle aktive eksamensmeldinger for en student"""
        qry = """
        SELECT DISTINCT vm.emnekode, vm.dato_opprettet,
               vm.status_er_kandidat
        FROM fs.person p, fs.vurdkombmelding vm,
             fs.vurderingskombinasjon vk, fs.vurderingstid vt,
             fs.vurdkombenhet ve
        WHERE p.fodselsdato = :fnr AND
              p.personnr = :pnr AND
              p.fodselsdato = vm.fodselsdato AND
              p.personnr = vm.personnr AND
              vk.institusjonsnr = vm.institusjonsnr AND
              vk.emnekode = vm.emnekode AND
              vk.versjonskode = vm.versjonskode AND
              vk.vurdkombkode = vm.vurdkombkode AND
              vk.vurdordningkode IS NOT NULL and
              vt.arstall = vm.arstall AND
              vt.vurdtidkode = vm.vurdtidkode AND
              ve.emnekode = vm.emnekode AND
              ve.versjonskode = vm.versjonskode AND
              ve.vurdkombkode = vm.vurdkombkode AND
              ve.vurdtidkode = vm.vurdtidkode AND
              ve.institusjonsnr = vm.institusjonsnr AND
              ve.arstall = vt.arstall AND
              ve.vurdtidkode = vt.vurdtidkode AND
              ve.arstall_reell = %s AND
              %s
              """ % (self.year, self._is_alive())
        return self.db.query(qry, {'fnr': fnr,
                                   'pnr': pnr})

    def get_undervisningsmelding(self, fnr, pnr):
        """Hent alle aktive undervisningsmeldinger for en gitt student."""
        qry = """
        SELECT DISTINCT
            u.emnekode, u.versjonskode, u.terminkode, u.arstall,
            u.dato_endring
        FROM
            fs.undervisningsmelding u, fs.person p
        WHERE
            u.fodselsdato = :fnr AND
            u.personnr = :pnr AND
            p.fodselsdato = u.fodselsdato AND
            p.personnr = u.personnr AND
            u.institusjonsnr = %d AND
            u.arstall = %d AND
            u.terminkode = '%s' AND
            NVL(u.status_opptatt, 'N') = 'J' AND
            %s
        """ % (self.institusjonsnr, self.year, self.semester,
               self._is_alive())
        return self.db.query(qry, {'fnr': fnr, 'pnr': pnr})

    def get_studierett(self, fnr, pnr):  # GetStudentStudierett_50
        """Hent info om alle studierett en student har eller har hatt"""
        qry = """
        SELECT DISTINCT
           sps.studieprogramkode, sps.studierettstatkode,
           sps.studieretningkode,sps.dato_studierett_tildelt,
           sps.dato_studierett_gyldig_til,sps.status_privatist,
           sps.studentstatkode
        FROM fs.studieprogramstudent sps, fs.person p
        WHERE sps.fodselsdato=:fnr AND
              sps.personnr=:pnr AND
              sps.fodselsdato=p.fodselsdato AND
              sps.personnr=p.personnr
              AND %s
        """ % self._is_alive()
        return self.db.query(qry, {'fnr': fnr, 'pnr': pnr})

    def list_betalt_semesteravgift(self):
        """Hent informasjon om semesterregistrering og betaling"""
        qry = """
        SELECT DISTINCT
        r.fodselsdato, r.personnr
        FROM fs.registerkort r
        WHERE (status_bet_ok = 'J' OR betformkode = 'FRITATT') AND
               NVL(r.status_ugyldig, 'N') = 'N' AND
        %s""" % self._get_termin_aar(only_current=1)
        return self.db.query(qry, {'autumn': 'HØST',
                                   'spring': 'VÅR'})
    # end list_betalt_semesteravgift

    def get_emne_eksamensmeldinger(self, emnekode):  # GetEmneinformasjon
        """Hent informasjon om alle som er vurderingsmeldt til
           EMNEKODE i inneværende semester"""
        query = """
        SELECT DISTINCT p.fodselsdato, p.personnr, p.dato_fodt, p.fornavn,
             p.etternavn,
             vm.emnekode, vm.studieprogramkode, vm.arstall, vm.versjonskode,
             vt.terminkode_gjelder_i, vt.arstall_gjelder_i
        FROM fs.person p, fs.vurdkombmelding vm,
             fs.vurderingskombinasjon vk,
             fs.vurdkombenhet ve, fs.vurderingstid vt
        WHERE vm.emnekode = :emnekode AND
              p.fodselsdato=vm.fodselsdato AND
              p.personnr=vm.personnr AND
              vk.institusjonsnr = vm.institusjonsnr AND
              vk.emnekode = vm.emnekode AND
              vk.versjonskode = vm.versjonskode AND
              vk.vurdkombkode = vm.vurdkombkode AND
              vk.vurdordningkode IS NOT NULL and
              ve.arstall = vm.arstall AND
              ve.vurdtidkode = vm.vurdtidkode AND
              ve.emnekode = vm.emnekode AND
              ve.versjonskode = vm.versjonskode AND
              ve.vurdkombkode = vm.vurdkombkode AND
              ve.vurdtidkode = vm.vurdtidkode AND
              ve.institusjonsnr = vm.institusjonsnr AND
              ve.arstall_reell=vt.arstall AND
              ve.vurdtidkode_reell=vt.vurdtidkode AND
              vt.arstall_gjelder_i = %s AND
              %s
        """ % (self.year, self._is_alive())
        return self.db.query(query, {"emnekode": emnekode})

    def get_student_kull(self, fnr, pnr):
        """Hent opplysninger om hvilken klasse studenten er en del av og
        hvilken kull studentens klasse tilhører."""
        qry = """
        SELECT DISTINCT
          sps.studieprogramkode, sps.terminkode_kull, sps.arstall_kull,
          k.status_aktiv
        FROM fs.studieprogramstudent sps, fs.kull k, fs.person p
        WHERE sps.fodselsdato = :fnr AND
          sps.personnr = :pnr AND
          p.fodselsdato = sps.fodselsdato AND
          p.personnr = sps.personnr AND
          sps.studieprogramkode = k.studieprogramkode AND
          sps.terminkode_kull = k.terminkode AND
          sps.arstall_kull = k.arstall AND
          %s""" % self._is_alive()
        return self.db.query(qry, {'fnr': fnr,
                                   'pnr': pnr})

    def get_utdanningsplan(self, fnr, pnr):  # GetStudentUtdPlan
        """Hent opplysninger om utdanningsplan for student"""
        qry = """
        SELECT DISTINCT
          utdp.studieprogramkode, utdp.terminkode_bekreft,
          utdp.arstall_bekreft, utdp.dato_bekreftet
        FROM fs.studprogstud_planbekreft utdp, fs.person p
        WHERE utdp.fodselsdato = :fnr AND
              utdp.personnr = :pnr AND
              utdp.fodselsdato = p.fodselsdato AND
              utdp.personnr = p.personnr AND
              %s
        """ % self._is_alive()
        return self.db.query(qry, {'fnr': fnr,
                                   'pnr': pnr})

    def list_tilbud(self):  # GetStudentTilbud_50
        # OBS! Denne metoden er ikke lenger i bruk og virker ikke
        # med FS 6.4
        """Hent personer som har fått tilbud om opptak og
        har takket ja til tilbudet.
        Disse skal gis affiliation student med kode tilbud til
        stedskoden sp.faknr_studieansv+sp.instituttnr_studieansv+
        sp.gruppenr_studieansv. Personer som har fått tilbud om
        opptak til et studieprogram ved institusjonen vil inngå i
        denne kategorien.  Alle søkere til studierved institusjonen
        registreres i tabellen fs.soknadsalternativ og informasjon om
        noen har fått tilbud om opptak hentes også derfra (feltet
        fs.soknadsalternativ.tilbudstatkode er et godt sted å
        begynne å lete etter personer som har fått tilbud). Hvis vi skal
        kjøre dette på UiO kan det hende at vi må ha:
        "sa.opptakstypekode = 'NOM'" med i søket. Dette er imidlertid
        uklart. """

        qry = """
        SELECT DISTINCT
              p.fodselsdato, p.personnr, p.dato_fodt, p.etternavn, p.fornavn,
              p.adrlin1_hjemsted, p.adrlin2_hjemsted,
              p.postnr_hjemsted, p.adrlin3_hjemsted, p.adresseland_hjemsted,
              p.sprakkode_malform, osp.studieprogramkode,
              p.kjonn, p.status_dod
        FROM fs.soknadsalternativ sa, fs.person p, fs.opptakstudieprogram osp,
             fs.studieprogram sp
        WHERE p.fodselsdato=sa.fodselsdato AND
              p.personnr=sa.personnr AND
              sa.institusjonsnr=%s AND
              sa.tilbudstatkode IN ('I', 'S') AND
              sa.svarstatkode_svar_pa_tilbud='J' AND
              sa.studietypenr = osp.studietypenr AND
              osp.studieprogramkode = sp.studieprogramkode AND
              %s
              """ % (self.institusjonsnr, self._is_alive())
        return self.db.query(qry)

    def list_utvekslings_student(self):  # GetStudinfUtvekslingsStudent
        """ Henter personer som er registrert som utvekslingsSTUDENT i
            fs.utvekslingsperson. Vi henter 14 dager før studenten står
            på trappa. """
        qry = """
        SELECT DISTINCT s.fodselsdato, s.personnr, p.dato_fodt, p.etternavn,
               p.fornavn,
               s.adrlin1_semadr,s.adrlin2_semadr, s.postnr_semadr,
               s.adrlin3_semadr, s.adresseland_semadr, p.adrlin1_hjemsted,
               p.adrlin2_hjemsted, p.postnr_hjemsted, p.adrlin3_hjemsted,
               p.adresseland_hjemsted,
               p.sprakkode_malform, p.kjonn, u.institusjonsnr_internt,
               u.faknr_internt, u.instituttnr_internt, u.gruppenr_internt
        FROM fs.student s, fs.person p, fs.utvekslingsperson u
        WHERE s.fodselsdato = p.fodselsdato AND
              s.personnr = p.personnr AND
              s.fodselsdato = u.fodselsdato AND
              s.personnr = u.personnr AND
              u.utvpersonkatkode = 'STUDENT' AND
              u.status_innreisende = 'J' AND
              u.dato_fra <= (SYSDATE + 14) AND
              u.dato_til >= SYSDATE
      """
        return self.db.query(qry)

    def list_permisjon(self):  # GetStudinfPermisjon
        """Hent personer som har innvilget permisjon.  Disse vil
        alltid ha opptak, så vi henter bare noen få kolonner.
        Disse tildeles affiliation student med kode permisjon
        til sp.faknr_studieansv, sp.instituttnr_studieansv,
        sp.gruppenr_studieansv"""

        qry = """
        SELECT  pe.studieprogramkode, pe.fodselsdato, pe.personnr,
                p.dato_fodt, pe.fraverarsakkode_hovedarsak
        FROM fs.innvilget_permisjon pe, fs.person p
        WHERE p.fodselsdato = pe.fodselsdato AND
              p.personnr = pe.personnr AND
              dato_fra < SYSDATE AND NVL(dato_til, SYSDATE) >= SYSDATE
              AND %s
        """ % self._is_alive()
        return self.db.query(qry)

    def list_drgrad(self):  # GetStudinfDrgrad
        """Henter info om aktive doktorgradsstudenter.  Aktive er
        definert til å være de som har en studierett til et program
        som har nivåkode større eller lik 900, og der datoen for
        tildelt studierett er passert og datoen for fratatt studierett
        enten ikke er satt eller ikke passert."""

        qry = """
        SELECT DISTINCT
               sps.fodselsdato, sps.personnr, p.dato_fodt,
               sp.institusjonsnr_studieansv AS institusjonsnr,
               sp.faknr_studieansv AS faknr,
               sp.instituttnr_studieansv AS instituttnr,
               sp.gruppenr_studieansv AS gruppenr,
               sps.dato_studierett_tildelt,
               sps.dato_studierett_gyldig_til,
               sps.studieprogramkode,
               s.adrlin1_semadr,s.adrlin2_semadr, s.postnr_semadr,
               s.adrlin3_semadr, s.adresseland_semadr,
               p.adrlin1_hjemsted, p.adrlin2_hjemsted,
               p.adrlin3_hjemsted, p.postnr_hjemsted,
               p.adresseland_hjemsted,
               pt.telefonlandnr telefonlandnr_mobil,
               '' telefonretnnr_mobil,
               pt.telefonnr telefonnr_mobil
        FROM fs.studieprogramstudent sps, fs.studieprogram sp,
             fs.student s, fs.person p
             LEFT JOIN fs.persontelefon pt ON
              pt.fodselsdato = p.fodselsdato AND
              pt.personnr = p.personnr AND
              pt.telefonnrtypekode = 'MOBIL'

        WHERE p.fodselsdato = sps.fodselsdato AND
              p.personnr = sps.personnr AND
              p.fodselsdato = s.fodselsdato AND
              p.personnr = s.personnr AND
              NVL(sps.dato_studierett_gyldig_til, sysdate) >= SYSDATE AND
              sps.status_privatist='N' AND
              sps.studieprogramkode = sp.studieprogramkode AND
              %s AND
              sp.studienivakode in (900,980)""" % self._is_alive()
        return self.db.query(qry)

    def list_privatist(self):
        """Her henter vi informasjon om privatister.
        Som privatist regnes alle studenter med en forekomst i
        FS.STUDIEPROGRAMSTUDENT der dato_studierett_gyldig_til
        er større eller lik dagens dato og studierettstatuskode
        er PRIVATIST eller status_privatist er satt til 'J'"""
        qry = """
        SELECT DISTINCT
          p.fodselsdato, p.personnr, p.dato_fodt, p.etternavn,
          p.fornavn, p.kjonn, s.adrlin1_semadr,
          s.adrlin2_semadr, s.postnr_semadr, s.adrlin3_semadr,
          s.adresseland_semadr, p.adrlin1_hjemsted,
          p.sprakkode_malform,sps.studieprogramkode,
          sps.studieretningkode, sps.status_privatist,
          s.studentnr_tildelt,
          pt.telefonlandnr telefonlandnr_mobil,
          '' telefonretnnr_mobil,
          pt.telefonnr telefonnr_mobil
        FROM fs.student s, fs.studieprogramstudent sps, fs.person p
             LEFT JOIN fs.persontelefon pt ON
             pt.fodselsdato = p.fodselsdato AND
             pt.personnr = p.personnr AND
             pt.telefonnrtypekode = 'MOBIL'
        WHERE p.fodselsdato = s.fodselsdato AND
          p.personnr = s.personnr AND
          p.fodselsdato = sps.fodselsdato AND
          p.personnr = sps.personnr AND
          (sps.studierettstatkode = 'PRIVATIST' OR
          sps.status_privatist = 'J') AND
          sps.dato_studierett_gyldig_til >= sysdate """
        return self.db.query(qry)


@fsobject('undervisning')
class Undervisning(FSObject):
    def list_aktivitet(self, Instnr, emnekode, versjon, termk,
                       aar, termnr, aktkode):  # GetStudUndAktivitet
        qry = """
        SELECT
          su.fodselsdato, su.personnr
        FROM
          FS.STUDENT_PA_UNDERVISNINGSPARTI su,
          FS.undaktivitet ua
        WHERE
          ua.institusjonsnr = :instnr AND
          ua.emnekode       = :emnekode AND
          ua.versjonskode   = :versjon AND
          ua.terminkode     = :terminkode AND
          ua.arstall        = :arstall AND
          ua.terminnr       = :terminnr AND
          ua.aktivitetkode  = :aktkode AND
          su.terminnr       = ua.terminnr       AND
          su.institusjonsnr = ua.institusjonsnr AND
          su.emnekode       = ua.emnekode       AND
          su.versjonskode   = ua.versjonskode   AND
          su.terminkode     = ua.terminkode     AND
          su.arstall        = ua.arstall        AND
          su.undpartilopenr = ua.undpartilopenr AND
          su.disiplinkode   = ua.disiplinkode   AND
          su.undformkode    = ua.undformkode"""

        return self.db.query(qry, {
            'instnr': Instnr,
            'emnekode': emnekode,
            'versjon': versjon,
            'terminkode': termk,
            'arstall': aar,
            'terminnr': termnr,
            'aktkode': aktkode})

    def list_alle_personroller(self):
        """Hent alle roller til aller personer."""
        qry = """
        /* Som i get_personroller, henter vi *alle* kolonnene */
        SELECT *
        FROM fs.personrolle
        WHERE
          dato_fra < SYSDATE AND
          NVL(dato_til,SYSDATE) >= sysdate"""
        return self.db.query(qry)

    # GetUndervEnhetAll
    def list_undervisningenheter(self, year=None, sem=None):
        if year is None:
            year = self.year
        if sem is None:
            sem = self.semester
        return self.db.query(u"""
        SELECT
          ue.institusjonsnr, ue.emnekode, ue.versjonskode, ue.terminkode,
          ue.arstall, ue.terminnr, e.institusjonsnr_kontroll,
          e.faknr_kontroll, e.instituttnr_kontroll, e.gruppenr_kontroll,
          e.emnenavn_bokmal, e.emnenavnfork
        FROM
          fs.undervisningsenhet ue, fs.emne e, fs.arstermin t
        WHERE
          ue.institusjonsnr = e.institusjonsnr AND
          ue.emnekode       = e.emnekode AND
          ue.versjonskode   = e.versjonskode AND
          ue.terminkode IN (:spring, :autumn) AND
          ue.terminkode = t.terminkode AND
          (ue.arstall > :aar OR
           (ue.arstall = :aar2 AND
            EXISTS(SELECT 'x' FROM fs.arstermin tt
            WHERE tt.terminkode = :sem AND
                  t.sorteringsnokkel >= tt.sorteringsnokkel)))""",
                             {'aar': year,
                              'aar2': year,  # db-driver bug work-around
                              'sem': sem,
                              'autumn': 'HØST',
                              'spring': 'VÅR'})

    def list_aktiviteter(self, start_aar=time.localtime()[0],
                         start_semester=None):
        if start_semester is None:
            start_semester = self.semester
        return self.db.query(u"""
        SELECT
          ua.institusjonsnr, ua.emnekode, ua.versjonskode,
          ua.terminkode, ua.arstall, ua.terminnr, ua.aktivitetkode,
          ua.undpartilopenr, ua.disiplinkode, ua.undformkode, ua.aktivitetsnavn
        FROM
          fs.undaktivitet ua,
          fs.arstermin t
        WHERE
          ua.undpartilopenr IS NOT NULL AND
          ua.disiplinkode IS NOT NULL AND
          ua.undformkode IS NOT NULL AND
          ua.terminkode IN (:spring, :autumn) AND
          ua.terminkode = t.terminkode AND
          ((ua.arstall = :aar AND
            EXISTS (SELECT 'x' FROM fs.arstermin tt
                    WHERE tt.terminkode = :semester AND
                          t.sorteringsnokkel >= tt.sorteringsnokkel)) OR
           ua.arstall > :aar)""",
                             {'aar': start_aar,
                              'semester': start_semester,
                              'autumn': 'HØST',
                              'spring': 'VÅR'})

    def get_undform_aktiviteter(self, Instnr, emnekode, versjon, termk,
                                aar, termnr, undformkode):
        """
        Returnerer alle aktiviteter med en gitt undformkode innen det
        oppgitte (år, semester)
        """

        return self.db.query(u"""
        SELECT
          ua.institusjonsnr, ua.emnekode, ua.versjonskode,
          ua.terminkode, ua.arstall, ua.terminnr, ua.aktivitetkode
        FROM
          fs.undaktivitet ua,
          fs.arstermin t
        WHERE
          ua.institusjonsnr = :Instnr AND
          ua.emnekode = :emnekode AND
          ua.versjonskode = :versjon AND
          ua.terminkode = :termk AND
          ua.terminnr = :termnr AND
          ua.undformkode = :undformkode AND
          ua.terminkode IN (:spring, :autumn) AND
          ua.terminkode = t.terminkode AND
          ((ua.arstall = :aar AND
            EXISTS (SELECT 'x' FROM fs.arstermin tt
                    WHERE tt.terminkode = :termk AND
                    t.sorteringsnokkel >= tt.sorteringsnokkel)) OR
           ua.arstall > :aar)""",
                             {"Instnr": Instnr,
                              "emnekode": emnekode,
                              "versjon": versjon,
                              "termk": termk,
                              "termnr": termnr,
                              "aar": aar,
                              "undformkode": undformkode,
                              'autumn': 'HØST',
                              'spring': 'VÅR'})
    # end get_undform_aktiviteter

    def list_undform_aktiviteter(self, undformkode):
        """Hent alle aktivitetene med en gitt undformkode. Omtrent som
        get_undform_aktiviteter, bare at denne henter *alle*"""

        return self.db.query(u"""
        SELECT
          ua.institusjonsnr, ua.emnekode, ua.versjonskode,
          ua.terminkode, ua.arstall, ua.terminnr, ua.aktivitetkode,
          ua.undformkode
        FROM
          fs.undaktivitet ua,
          fs.arstermin t
        WHERE
          ua.undformkode = :undformkode AND
          ua.terminkode IN (:spring, :autumn) AND
          ua.terminkode = t.terminkode AND
          (EXISTS (SELECT 'x' FROM fs.arstermin tt
                   WHERE t.sorteringsnokkel >= tt.sorteringsnokkel))
          """, {"undformkode": undformkode,
                'autumn': 'HØST',
                'spring': 'VÅR'})

    def list_studenter_underv_enhet(self, Instnr, emnekode,
                                    versjon, termk, aar, termnr):
        # Den ulekre repetisjonen av bind-parametere under synes
        # dessverre å være nødvendig; ut fra foreløpig testing ser det
        # ut til at enten Oracle eller DCOracle2 krever at dersom et
        # statement består av flere uavhengige SELECTs, og SELECT
        # nr. N bruker minst en bind-variabel nevnt i SELECT nr. x,
        # der x < N, må SELECT nr. N *kun* bruke de bind-variablene
        # som også finnes i SELECT nr. x.
        qry = """
        SELECT
          fodselsdato, personnr
        FROM
          FS.UNDERVISNINGSMELDING
        WHERE
          institusjonsnr = :und_instnr AND
          emnekode       = :und_emnekode AND
          versjonskode   = :und_versjon AND
          terminkode     = :und_terminkode AND
          arstall        = :und_arstall AND
          terminnr       = :und_terminnr
        UNION
        SELECT DISTINCT
          fodselsdato, personnr
        FROM
          fs.vurdkombmelding vm, fs.vurderingstid vt,
          fs.vurdkombenhet ve, fs.vurderingskombinasjon vk
        WHERE
          vm.institusjonsnr    = :instnr AND
          vm.emnekode          = :emnekode AND
          vm.versjonskode      = :versjon AND
          vt.arstall_gjelder_i = :arstall AND
          ve.arstall_reell = vt.arstall AND
          ve.vurdtidkode_reell = vt.vurdtidkode AND
          vm.institusjonsnr=ve.institusjonsnr AND
          vm.emnekode=ve.emnekode AND
          vm.versjonskode=ve.versjonskode AND
          vm.vurdkombkode=ve.vurdkombkode AND
          vm.vurdtidkode=ve.vurdtidkode AND
          vm.arstall=ve.arstall AND
          vm.vurdkombkode=ve.vurdkombkode AND
          ve.institusjonsnr = vk.institusjonsnr AND
          ve.emnekode = vk.emnekode AND
          ve.versjonskode = vk.versjonskode AND
          ve.vurdkombkode = vk.vurdkombkode AND
          vk.vurdordningkode IS NOT NULL AND
          vt.terminkode_gjelder_i = :termk
        """
        return self.db.query(qry, {'und_instnr': Instnr,
                                   'und_emnekode': emnekode,
                                   'und_versjon': versjon,
                                   'und_terminkode': termk,
                                   'und_arstall': aar,
                                   'und_terminnr': termnr,
                                   'instnr': Instnr,
                                   'emnekode': emnekode,
                                   'versjon': versjon,
                                   'arstall': aar,
                                   'termk': termk})

    def list_fagperson_semester(self):  # GetFagperson_50
        # (GetKursFagpersonundsemester var duplikat)
        """Disse skal gis affiliation tilknyttet med kode fagperson
        til stedskoden faknr+instituttnr+gruppenr
        Hent ut fagpersoner som har undervisning i inneværende
        eller forrige kalenderår"""

        qry = """
        SELECT DISTINCT
              fp.fodselsdato, fp.personnr, p.dato_fodt, p.etternavn, p.fornavn,
              fp.adrlin1_arbeide, fp.adrlin2_arbeide, fp.postnr_arbeide,
              fp.adrlin3_arbeide, fp.adresseland_arbeide,
              ptw.telefonnr telefonnr_arbeide,
              ptf.telefonnr telefonnr_fax_arb,
              p.adrlin1_hjemsted, p.adrlin2_hjemsted, p.postnr_hjemsted,
              p.adrlin3_hjemsted, p.adresseland_hjemsted,
              pth.telefonnr telefonnr_hjemsted, fp.stillingstittel_engelsk,
              fp.institusjonsnr_ansatt AS institusjonsnr,
              fp.faknr_ansatt AS faknr,
              fp.instituttnr_ansatt AS instituttnr,
              fp.gruppenr_ansatt AS gruppenr,
              fp.status_aktiv, p.status_reserv_lms AS status_publiseres,
              p.kjonn, p.status_dod
        FROM fs.fagperson fp, fs.person p
             LEFT JOIN fs.persontelefon ptw ON
              (ptw.fodselsdato = p.fodselsdato AND
               ptw.personnr = p.personnr AND
               ptw.telefonnrtypekode = 'ARB')
             LEFT JOIN fs.persontelefon ptf ON
              (ptf.fodselsdato = p.fodselsdato AND
               ptf.personnr = p.personnr AND
               ptf.telefonnrtypekode = 'FAKS')
             LEFT JOIN fs.persontelefon pth ON
              (pth.fodselsdato = p.fodselsdato AND
               pth.personnr = p.personnr AND
               pth.telefonnrtypekode = 'HJEM')
        WHERE fp.fodselsdato = p.fodselsdato AND
              fp.personnr = p.personnr AND
              fp.status_aktiv = 'J' AND
              fp.institusjonsnr_ansatt IS NOT NULL AND
              fp.faknr_ansatt IS NOT NULL AND
              fp.instituttnr_ansatt IS NOT NULL AND
              fp.gruppenr_ansatt IS NOT NULL
        """
        return self.db.query(qry)

    def get_fagperson_semester(self, fnr, pnr, institusjonsnr, fakultetnr,
                               instiuttnr, gruppenr, termin, arstall):
        return self.db.query("""
        SELECT
          terminkode, arstall, institusjonsnr, faknr, instituttnr,
          gruppenr, status_aktiv, status_publiseres
        FROM fs.fagpersonundsemester r
        WHERE
          fodselsdato=:fnr AND personnr=:pnr AND
          terminkode=:termin AND arstall=:arstall AND
          institusjonsnr=:institusjonsnr AND faknr=:fakultetnr AND
          instituttnr=:instiuttnr AND gruppenr=:gruppenr""", {
            'fnr': fnr, 'pnr': pnr,
            'institusjonsnr': institusjonsnr, 'fakultetnr': fakultetnr,
            'instiuttnr': instiuttnr, 'gruppenr': gruppenr,
            'termin': termin, 'arstall': arstall})

    def add_fagperson_semester(self, fnr, pnr, institusjonsnr,
                               fakultetnr, instiuttnr, gruppenr, termin,
                               arstall, status_aktiv, status_publiseres):
        return self.db.execute(
            """
            INSERT INTO fs.fagpersonundsemester
            (fodselsdato, personnr, terminkode, arstall, institusjonsnr, faknr,
            instituttnr, gruppenr, status_aktiv, status_publiseres)
            VALUES
            (:fnr, :pnr, :termin, :arstall, :institusjonsnr, :fakultetnr,
            :instiuttnr, :gruppenr, :status_aktiv, :status_publiseres)""",
            {'fnr': fnr,
             'pnr': pnr,
             'institusjonsnr': institusjonsnr,
             'fakultetnr': fakultetnr,
             'instiuttnr': instiuttnr,
             'gruppenr': gruppenr,
             'termin': termin,
             'arstall': arstall,
             'status_aktiv': status_aktiv,
             'status_publiseres': status_publiseres})

    def list_studenter_alle_undakt(self):
        """Hent alle studenter på alle undakt.

        NB! Det kan være mange hundretusen rader i FSPROD i
        student_pa_undervisningsparti. Det koster da en del minne.
        """

        qry = """
        SELECT
          su.fodselsdato, su.personnr,
          ua.institusjonsnr, ua.emnekode, ua.versjonskode, ua.terminkode,
          ua.arstall, ua.terminnr, ua.aktivitetkode
        FROM
          fs.student_pa_undervisningsparti su,
          fs.undaktivitet ua
        WHERE
          su.terminnr       = ua.terminnr       AND
          su.institusjonsnr = ua.institusjonsnr AND
          su.emnekode       = ua.emnekode       AND
          su.versjonskode   = ua.versjonskode   AND
          su.terminkode     = ua.terminkode     AND
          su.arstall        = ua.arstall        AND
          su.undpartilopenr = ua.undpartilopenr AND
          su.disiplinkode   = ua.disiplinkode   AND
          su.undformkode    = ua.undformkode AND
          su.arstall >= :aar
        """

        return self.db.query(qry, {"aar": self.year}, fetchall=False)

    def list_studenter_kull(self, studieprogramkode, terminkode, arstall):
        """Hent alle studentene som er oppført på et gitt kull."""

        query = """
        SELECT DISTINCT
            fodselsdato, personnr
        FROM
            fs.studieprogramstudent
        WHERE
            studentstatkode IN ('AKTIV', 'PERMISJON') AND
            NVL(dato_studierett_gyldig_til,SYSDATE)>= SYSDATE AND
            studieprogramkode = :studieprogramkode AND
            terminkode_kull = :terminkode_kull AND
            arstall_kull = :arstall_kull
        """

        return self.db.query(query, {"studieprogramkode": studieprogramkode,
                                     "terminkode_kull": terminkode,
                                     "arstall_kull": arstall})

    def list_studenter_alle_kull(self):
        query = """
        SELECT DISTINCT
            fodselsdato, personnr, studieprogramkode, terminkode_kull,
            arstall_kull
        FROM
            fs.studieprogramstudent
        WHERE
            studentstatkode IN ('AKTIV', 'PERMISJON') AND
            NVL(dato_studierett_gyldig_til,SYSDATE)>= SYSDATE AND
            /* IVR 2007-11-12: According to baardj, it makes no sense to
               register 'kull' for earlier timeframes. */
            arstall_kull >= 2002
        """

        return self.db.query(query)


@fsobject('evu')
class EVU(FSObject):
    def list(self):  # GetDeltaker_50
        """Hent info om personer som er ekte EVU-studenter ved
        dvs. er registrert i EVU-modulen i tabellen
        fs.deltaker,  Henter alle som er knyttet til kurs som
        tidligst ble avsluttet for 30 dager siden."""

        qry = """
        SELECT DISTINCT
               p.fodselsdato, p.personnr, p.dato_fodt, p.etternavn, p.fornavn,
               d.adrlin1_job, d.adrlin2_job, d.postnr_job,
               d.adrlin3_job, d.adresseland_job, d.adrlin1_hjem,
               d.adrlin2_hjem, d.postnr_hjem, d.adrlin3_hjem,
               d.adresseland_hjem, p.adrlin1_hjemsted,
               p.adrlin2_hjemsted,
               p.postnr_hjemsted, p.adrlin3_hjemsted,
               p.adresseland_hjemsted, d.deltakernr, d.emailadresse,
               pt.telefonlandnr telefonlandnr_mobil,
               '' telefonretnnr_mobil,
               pt.telefonnr telefonnr_mobil,
               k.etterutdkurskode, k.kurstidsangivelsekode,
               e.studieprogramkode, e.faknr_adm_ansvar,
               e.instituttnr_adm_ansvar, e.gruppenr_adm_ansvar,
               p.kjonn, p.status_dod
        FROM fs.deltaker d, fs.kursdeltakelse k,
             fs.etterutdkurs e, fs.person p
             LEFT JOIN fs.persontelefon pt ON
              pt.fodselsdato = p.fodselsdato AND
              pt.personnr = p.personnr AND
              pt.telefonnrtypekode = 'MOBIL'
        WHERE p.fodselsdato=d.fodselsdato AND
              p.personnr=d.personnr AND
              d.deltakernr=k.deltakernr AND
              e.etterutdkurskode=k.etterutdkurskode AND
              NVL(e.status_nettbasert_und, 'J') = 'J' AND
              k.kurstidsangivelsekode = e.kurstidsangivelsekode AND
              NVL(e.dato_til, SYSDATE) >= SYSDATE - 30"""
        return self.db.query(qry)

    def list_kurs(self):  # GetEvuKurs
        """Henter info om aktive EVU-kurs, der aktive er de som har
        status_aktiv satt til 'J' og som ikke er avsluttet
        (jmf. dato_til)."""

        qry = """
        SELECT etterutdkurskode, kurstidsangivelsekode,
          etterutdkursnavn, etterutdkursnavnkort, emnekode,
          institusjonsnr_adm_ansvar, faknr_adm_ansvar,
          instituttnr_adm_ansvar, gruppenr_adm_ansvar,
          TO_CHAR(NVL(dato_fra, SYSDATE), 'YYYY-MM-DD') AS dato_fra,
          TO_CHAR(NVL(dato_til, SYSDATE), 'YYYY-MM-DD') AS dato_til,
          status_aktiv, status_nettbasert_und
        FROM fs.etterutdkurs
        WHERE status_aktiv='J' AND
          NVL(dato_til, SYSDATE) >= (SYSDATE - 30)
        """
        return self.db.query(qry)

    def get_kurs_informasjon(self, code):  # GetEvuKursInformasjon
        """
        This one works similar to GetEvuKurs, except for the filtering
        criteria: in this method we filter by course code, not by time frame
        """
        query = """
        SELECT etterutdkurskode, kurstidsangivelsekode,
          TO_CHAR(dato_fra, 'YYYY-MM-DD') as dato_fra,
          TO_CHAR(dato_til, 'YYYY-MM-DD') as dato_til
        FROM fs.etterutdkurs
        WHERE etterutdkurskode = :code
        """
        return self.db.query(query, {"code": code})

    def list_kurs_deltakere(self, kurskode, tid):  # GetEvuKursPameldte
        """List everyone registered for a given course"""
        query = """
        SELECT p.fodselsdato, p.personnr, p.dato_fodt,
          p.fornavn, p.etternavn
        FROM fs.person p, fs.etterutdkurs e,
          fs.kursdeltakelse kd, fs.deltaker d
        WHERE e.etterutdkurskode like :kurskode AND
          e.kurstidsangivelsekode like :tid AND
          e.etterutdkurskode = kd.etterutdkurskode AND
          e.kurstidsangivelsekode = kd.kurstidsangivelsekode AND
          kd.deltakernr = d.deltakernr AND
          d.fodselsdato = p.fodselsdato AND
          d.personnr = p.personnr"""
        return self.db.query(query, {"kurskode": kurskode,
                                     "tid": tid})

    def get_kurs_aktivitet(self, kurs, tid):  # GetAktivitetEvuKurs
        qry = """
        SELECT k.etterutdkurskode, k.kurstidsangivelsekode, k.aktivitetskode,
               k.aktivitetsnavn, k.undformkode
        FROM fs.kursaktivitet k
        WHERE k.etterutdkurskode='%s' AND
              k.kurstidsangivelsekode='%s'
        """ % (kurs, tid)

        return self.db.query(qry)

    def list_kurs_stud(self, kurs, tid):  # GetStudEvuKurs
        qry = """
        SELECT d.fodselsdato, d.personnr
        FROM fs.deltaker d, fs.kursdeltakelse k
        WHERE k.etterutdkurskode=:kurs AND
              k.kurstidsangivelsekode=:tid AND
              k.deltakernr=d.deltakernr AND
              d.fodselsdato IS NOT NULL AND
              d.personnr IS NOT NULL"""
        return self.db.query(qry, {'kurs': kurs, 'tid': tid})

    def list_aktivitet_stud(self, kurs, tid, aktkode):  # GetStudEvuAktivitet
        qry = """
        SELECT d.fodselsdato, d.personnr
        FROM fs.deltaker d, fs.kursaktivitet_deltaker k
        WHERE k.etterutdkurskode=:kurs AND
              k.kurstidsangivelsekode=:tid AND
              k.aktivitetskode=:aktkode AND
              k.deltakernr = d.deltakernr"""
        return self.db.query(qry, {
            'kurs': kurs,
            'tid': tid,
            'aktkode': aktkode})


@fsobject('forkurs')
class Forkurs(FSObject):
    pass


@fsobject('alumni')
class Alumni(FSObject):
    def list(self):  # GetAlumni_50
        """Henter informasjon om alle som har fullført
        studium frem til en grad, min. Cand.Mag.  Disse regnes
        som 'Alumni' ved UiO."""
        qry = u"""
        SELECT DISTINCT s.fodselsdato, s.personnr, p.dato_fodt, p.etternavn,
               p.fornavn,
               s.adrlin1_semadr,s.adrlin2_semadr, s.postnr_semadr,
               s.adrlin3_semadr, s.adresseland_semadr,
               p.adrlin1_hjemsted, p.adrlin2_hjemsted,
               p.postnr_hjemsted, p.adrlin3_hjemsted,
               p.adresseland_hjemsted,
               p.sprakkode_malform,sps.studieprogramkode,
               sps.studierettstatkode, p.kjonn, p.status_dod

        FROM fs.student s, fs.person p, fs.studieprogramstudent sps,
             fs.studieprogram sp
        WHERE  p.fodselsdato=s.fodselsdato AND
               p.personnr=s.personnr AND
               p.fodselsdato=sps.fodselsdato AND
               p.personnr=sps.personnr AND
               sps.studieprogramkode = sp.studieprogramkode AND
               sps.studentstatkode = 'FULLFØRT'  AND
               sps.studierettstatkode IN ('AUTOMATISK', 'CANDMAG', 'DIVERSE',
               'OVERGANG', 'ORDOPPTAK')
               """
        return self.db.query(qry)


@fsobject('studieinfo')
class StudieInfo(FSObject):
    def list_studieprogrammer(self, expired=True):  # GetStudieproginf
        """For hvert definerte studieprogram henter vi
        informasjon om utd_plan og eier samt studieprogkode. Vi burde
        her ha en sjekk på om studieprogrammet er utgått, men datagrunnalget
        er for svakt. ( WHERE status_utgatt = 'N')"""
        qry = """
        SELECT studieprogramkode, status_utdplan,
               institusjonsnr_studieansv, faknr_studieansv,
               instituttnr_studieansv, gruppenr_studieansv,
               studienivakode, status_utgatt, studieprognavn
        FROM fs.studieprogram"""
        if not expired:
            qry += " WHERE status_utgatt = 'N'"
        return self.db.query(qry)

    def list_emner(self):  # GetEmneinf
        """For hvert definerte emne henter vi informasjon om
           ansvarlig sted."""
        qry = """
        SELECT e.emnekode, e.versjonskode, e.institusjonsnr,
               e.faknr_reglement, e.instituttnr_reglement,
               e.gruppenr_reglement, e.studienivakode
        FROM fs.emne e
        WHERE e.institusjonsnr = %s AND
        NVL(e.arstall_eks_siste, %s) >= %s - 1""" % (
            self.institusjonsnr, self.year, self.year)
        return self.db.query(qry)

    def get_emne_i_studieprogram(self, emne):  # GetEmneIStudProg
        """Hent alle studieprogrammer et gitt emne kan inngå i."""
        qry = """
        SELECT DISTINCT
          studieprogramkode
        FROM fs.emne_i_studieprogram
        WHERE emnekode = :emne
        """
        return self.db.query(qry, {'emne': emne})

    def list_ou(self, institusjonsnr=0):  # GetAlleOUer
        """Hent data om stedskoder registrert i FS"""
        qry = """
        SELECT DISTINCT
          institusjonsnr, faknr, instituttnr, gruppenr, stedakronym,
          stednavn_bokmal, faknr_org_under, instituttnr_org_under,
          gruppenr_org_under, adrlin1, adrlin2, postnr, adrlin3,
          stedkortnavn, telefonnr, faxnr, adrlin1_besok, emailadresse,
          adrlin2_besok, postnr_besok, url, bibsysbeststedkode,
          stedkode_konv
        FROM fs.sted
        WHERE institusjonsnr=%s
        """ % self.institusjonsnr
        return self.db.query(qry)

    def get_ou(self, fakultetnr, instituttnr, gruppenr, institusjonsnr):
        return self.db.query("""
        SELECT DISTINCT
          institusjonsnr, faknr, instituttnr, gruppenr, stedakronym,
          stednavn_bokmal, faknr_org_under, instituttnr_org_under,
          gruppenr_org_under, adrlin1, adrlin2, postnr, adrlin3,
          stedkortnavn, telefonnr, faxnr, adrlin1_besok, emailadresse,
          adrlin2_besok, postnr_besok, url, bibsysbeststedkode,
          stedkode_konv
        FROM fs.sted
        WHERE institusjonsnr=:institusjonsnr AND
              faknr=:fakultetnr AND
              instituttnr=:instituttnr AND
              gruppenr=:gruppenr
        """, {"institusjonsnr": institusjonsnr,
              "fakultetnr": fakultetnr,
              "instituttnr": instituttnr,
              "gruppenr": gruppenr})

    def list_kull(self):
        """Henter informasjon om aktive studiekull."""
        qry = """
        SELECT
          k.studieprogramkode, k.terminkode, k.arstall, k.studiekullnavn,
          k.kulltrinn_start, k.terminnr_maks, k.status_generer_epost,
          s.institusjonsnr_studieansv, s.faknr_studieansv,
          s.instituttnr_studieansv, s.gruppenr_studieansv
        FROM  fs.kull k, fs.studieprogram s
        WHERE
          k.status_aktiv = 'J' AND
          s.studieprogramkode = k.studieprogramkode
        """
        return self.db.query(qry)


@fsobject("FS")
class FS(object):
    def __init__(self, db=None, user=None, database=None):
        if db is None:
            user = user or cereconf.FS_USER
            database = database or cereconf.FS_DATABASE_NAME
            DB_driver = getattr(cereconf, 'DB_DRIVER_ORACLE', 'cx_Oracle')
            db = database.connect(user=user, service=database,
                                  DB_driver=DB_driver)
        self.db = db
        self.fsversion = _get_fs_version(self.db)
        for comp in 'person student undervisning evu alumni forkurs'.split():
            setattr(self, comp, self._component(comp)(db))
        self.info = self._component('studieinfo')(db)

    def _component(self, name):
        """Find fsobject for sub objects."""
        # TODO: Should we follow mro instead of use self and this module
        import inspect
        cand = find_best_version(inspect.getmodule(self).__name__,
                                 name,
                                 self.fsversion)
        if cand is None:
            cand = find_best_version(inspect.getmodule(FS).__name__,
                                     name,
                                     self.fsversion)
        return cand

    def list_dbfg_usernames(self, fetchall=False):
        """Get all usernames and return them as a sequence of db_rows.

        Usernames may be prefixed with a institution specific tag, if the db
        has defined this. If defined, only usernames with the prefix are
        returned, and the prefix is stripped out.

        NB! This function does *not* return a 2-tuple. Only a sequence of
        all usernames (the column names can be obtains from db_row objects)
        """
        prefix = self.get_username_prefix()
        ret = ({'username': row['username'][len(prefix):]} for row in
               self.db.query("""
                            SELECT username as username
                            FROM all_users
                            WHERE username LIKE :prefixed
                        """, {'prefixed': '%s%%' % prefix},
                             fetchall=fetchall))
        if fetchall:
            return list(ret)
        return ret

    def list_dba_usernames(self, fetchall=False):
        """Get all usernames for internal statistics."""

        query = """
        SELECT
           lower(username) as username
        FROM
           dba_users
        WHERE
           default_tablespace = 'USERS' and account_status = 'OPEN'
        """

        return self.db.query(query, fetchall=fetchall)

    def get_username_prefix(self):
        """Get the database' defined username prefix, or '' if not defined."""
        try:
            return self.db.query_1(
                "SELECT brukerprefiks FROM fs.systemverdier")
        except self.db.DatabaseError:
            pass
        return ''


class element_attribute_xml_parser(xml.sax.ContentHandler, object):

    elements = {}
    """A dict containing all valid element names for this parser.

    The dict must have a key for each of the XML element names that
    are valid for this parser.  The corresponding values indicate
    whether or not the parser class should invoke the callback
    function upon encountering such an element.

    Subclasses should override this entire attribute (i.e. subclasses
    should do elements = {key: value, ...}) rather than add more keys
    to the class attribute in their parent class (i.e. subclasses
    should not do elements[key] = value)."""

    def __init__(self, filename, callback):
        self._callback = callback
        xml.sax.parse(filename, self)

    def startElement(self, name, attrs):
        if name not in self.elements:
            raise ValueError("Unknown XML element: %r" % (name,))
        # Only set self._in_element etc. for interesting elements.
        if self.elements[name]:
            data = {}
            for k, v in attrs.items():
                data[k] = v
            self._callback(name, data)


class non_nested_xml_parser(element_attribute_xml_parser):

    def __init__(self, filename, callback):
        self._in_element = None
        self._attrs = None
        super(non_nested_xml_parser, self).__init__(filename, callback)

    def startElement(self, name, attrs):
        if name not in self.elements:
            raise ValueError("Unknown XML element: %r" % (name,))
        if self._in_element is not None:
            raise RuntimeError(
                "Can't deal with nested elements (<%s> before </%s>)." % (
                    name, self._in_element))
        # Only set self._in_element etc. for interesting elements.
        if self.elements[name]:
            self._in_element = name
            self._data = {}
            for k, v in attrs.items():
                self._data[k] = v

    def endElement(self, name):
        if name not in self.elements:
            raise ValueError("Unknown XML element: %r" % (name,))
        if self._in_element == name:
            self._callback(name, self._data)
            self._in_element = None


class ou_xml_parser(element_attribute_xml_parser):
    "Parserklasse for ou.xml."

    elements = {'data': False,
                'sted': True,
                'komm': True,
                }


class person_xml_parser(non_nested_xml_parser):
    "Parserklasse for person.xml."

    elements = {'data': False,
                'aktiv': True,
                'tilbud': True,
                'evu': True,
                'privatist_studieprogram': True,
                'eksamen': True
                }


class roles_xml_parser(non_nested_xml_parser):
    "Parserklasse for studieprog.xml."

    elements = {'data': False,
                'rolle': True,
                }

    target_key = "::rolletarget::"

    def __init__(self, *rest):
        self.logger = Factory.get_logger()
        super(roles_xml_parser, self).__init__(*rest)

    def endElement(self, name):
        if name == 'rolle':
            do_callback = self.validate_role(self._data)
            if not do_callback:
                self._in_element = None
        return super(roles_xml_parser, self).endElement(name)

    def validate_role(self, attrs):
        # Verifiser at rollen _enten_ gjelder en (fullstendig spesifisert)
        # undervisningsenhet _eller_ en und.aktivitet _eller_ et
        # studieprogram, osv. -- og ikke litt av hvert. Hovedproblemet er at
        # personrolletabellen i FS har overhodet ingen skranker på seg og man
        # kan stappe inn hva som helst av attributter (noe som gjerne også
        # blir gjort).
        #
        # Det er *KJEMPE*viktig at man er *VELDIG* forsiktig med å endre på
        # reglene i denne tabellen. Det er til syvende og sist de som
        # bestemmer om rollene blir bedømt som gyldige/ugyldige.
        #
        # Dersom FS tar i bruk nye attributter (som resulterer i
        # feilmeldingene i loggene våre), *MÅ* man avklare attributtbruken med
        # dem FØR denne tabellen oppdateres.
        #
        # Nøklene i tabellen er kolonnenavn fra FS (== attributtnavn i
        # roles.xml-filen generert fra FS).
        #
        # Verdiene forteller enten at attributtet ikke har noe betydning
        # (None), eller forteller hvilke rolletyper den nøkkelen kan være en
        # del av. Legg merke til at selv om et attributt ikke har noe
        # betydning, så er oppføringen i seg selv en bekreftelse av at
        # attributtet er gyldig.
        col2target = {
            'fodselsdato': None,
            'personnr': None,
            'rollenr': None,
            'rollekode': None,
            'dato_fra': None,
            'dato_til': None,
            'institusjonsnr': ['sted', 'emne', 'undenh', 'undakt', 'timeplan'],
            'faknr': ['sted'],
            'instituttnr': ['sted'],
            'gruppenr': ['sted'],
            'studieprogramkode': ['stprog', 'kull', 'kullklasse'],
            'emnekode': ['emne', 'undenh', 'undakt', 'timeplan'],
            'versjonskode': ['emne', 'undenh', 'undakt', 'timeplan'],
            'aktivitetkode': ['undakt', 'kursakt', 'timeplan'],
            'terminkode': ['kull', 'kullklasse',
                           'undenh', 'undakt', 'timeplan'],
            'arstall': ['kull', 'kullklasse', 'undenh', 'undakt', 'timeplan'],
            'terminnr': ['undenh', 'undakt', 'timeplan'],
            'etterutdkurskode': ['evu', 'kursakt'],
            'kurstidsangivelsekode': ['evu', 'kursakt'],
            'saksbehinit_opprettet': None,
            'dato_opprettet': None,
            'saksbehinit_endring': None,
            'dato_endring': None,
            'merknadtekst': None,
            'prioritetsnr': None,
            'klassekode': ['kullklasse'],
            'undplanlopenr': ['timeplan'],
            'status_publisering': None,
            'status_default_veileder': None,
            'institusjonsnr_eier': None,
            }
        data = attrs.copy()
        target = None
        not_target = set()
        possible_targets = set()
        for col, targs in col2target.iteritems():
            if col in data:
                del data[col]
                if targs is None:
                    continue
                possible_targets = possible_targets.union(targs)
                if target is None:
                    # Har ikke sett noen kolonner som har med
                    # spesifisering av target å gjøre før; target
                    # må være en av de angitt i 'targs'.
                    target = targs and set(targs) or set()
                else:
                    # Target må være i snittet mellom 'targs' og
                    # 'target'.
                    target = target.intersection(targs)
            else:
                if targs is None:
                    continue
                # Kolonnen kan spesifisere target, men er ikke med i
                # denne posteringen; oppdater not_target.
                not_target = not_target.union(targs)

        do_callback = True
        if data:
            # Det fantes kolonner i posteringen som ikke er tatt med i
            # 'col2target'-dicten.
            self.logger.error("Ukjente kolonner i FS.PERSONROLLE: %r", data)
            do_callback = False

        if target is not None:
            target = tuple(target - not_target)
        else:
            # Denne personrollen inneholdt ikke _noen_
            # target-spesifiserende kolonner.
            target = ()
        if len(target) != 1:
            if len(target) > 1:
                self.logger.error("Personrolle har flertydig angivelse av",
                                  " targets, kan være: %r (XML = %r).",
                                  target, attrs)
                attrs[self.target_key] = target
            else:
                self.logger.warning("Personrolle har ingen tilstrekkelig"
                                    " spesifisering av target, inneholder"
                                    " elementer fra: %r (XML = %r).",
                                    tuple(possible_targets), attrs)
                attrs[self.target_key] = tuple(possible_targets)
            do_callback = False
        else:
            self.logger.debug("Personrolle OK, target = %r (XML = %r).",
                              target[0], attrs)
            # Target er entydig og tilstrekkelig spesifisert; gjør
            # dette tilgjengelig for callback.
            attrs[self.target_key] = target
        return do_callback


class studieprog_xml_parser(non_nested_xml_parser):
    "Parserklasse for studieprog.xml."

    elements = {'data': False,
                'studprog': True,
                }


class underv_enhet_xml_parser(non_nested_xml_parser):
    "Parserklasse for underv_enhet.xml."

    elements = {'undervenhet': False,
                'undenhet': True,
                }


class student_undenh_xml_parser(non_nested_xml_parser):
    "Parserklasse for student_undenh.xml."

    elements = {'data': False,
                'student': True
                }


class evukurs_xml_parser(non_nested_xml_parser):
    "Parserklasse for evukurs.xml."

    elements = {"data": False,
                "evukurs": True}
# end evukurs_xml_parser


class emne_xml_parser(non_nested_xml_parser):
    elements = {"data": False,
                "emne": True}
# end emne_xml_parser


class deltaker_xml_parser(xml.sax.ContentHandler, object):
    "Parserklasse for å hente EVU kursdeltaker informasjon."

    def __init__(self, filename, callback):
        self._callback = callback
        self._in_person = False
        self._legal_elements = ("person", "evu", "aktiv", "tilbud",
                                "data", "privatist_studieprogram", "eksamen",
                                "nettpubl")
        xml.sax.parse(filename, self)

    def startElement(self, name, attrs):
        if name not in self._legal_elements:
            raise ValueError("Unknown XML element: %r" % (name,))

        if name not in ("person", "evu"):
            return

        tmp = dict()
        for k, v in attrs.items():
            tmp[k] = v

        if name == "person":
            assert not self._in_person, "Nested <person> element!"
            self._in_person = {"evu": list()}
            self._in_person.update(tmp)
        else:
            assert self._in_person, "<evu> outside of <person>!"
            self._in_person["evu"].append(tmp)

    def endElement(self, name):
        if name not in self._legal_elements:
            raise ValueError("Unknown XML element: %r" % (name,))

        if name == "person":
            self._callback(name, self._in_person)
            self._in_person = None
