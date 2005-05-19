# -*- coding: iso-8859-1 -*-
# Copyright 2002, 2003, 2004 University of Oslo, Norway
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

import cerebrum_path
import cereconf
import time
import xml.sax

from Cerebrum import Database
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.extlib import sets

# TODO: En del funksjoner finnes både som get_ og list_ variant.  Det
# kunne være en fordel om man etablerte en mekanisme for å slå sammen
# disse.  Det vil både redusere kodeduplisering, og være nyttig dersom
# man skal foreta inkrementelle operasjoner basert på endringer i FS.

# Note: The oracle database-driver does not support dates before 1970.
# Thus TO_DATE must be used when inserting dates
NOT_SET = 'ThisInputParameterIsNotSet'

class FSObject(object):
    """Parent class that all other fs-access methods inherit.
    Provides a number of utility methods."""

    def __init__(self, db):
        self.db = db
        t = time.localtime()[0:3]
        if t[1] <= 6:
            self.sem = 'V'
            self.semester = 'VÅR'
        else:
            self.sem = 'H'
            self.semester = 'HØST'
        self.year = t[0]
        self.mndnr = t[1]
        self.dday = t[2]
        self.YY = str(t[0])[2:]
        self.institusjonsnr = cereconf.DEFAULT_INSTITUSJONSNR
        
    def _is_alive(self):
	return "NVL(p.status_dod, 'N') = 'N'\n"

    def _get_termin_aar(self, only_current=0):
        if self.mndnr <= 6:
            # Months January - June == Spring semester
            current = "(r.terminkode = 'VÅR' AND r.arstall=%s)\n" % self.year;
            if only_current or self.mndnr >= 3 or (self.mndnr == 2 and self.dday > 15):
                return current
            return "(%s OR (r.terminkode = 'HØST' AND r.arstall=%d))\n" % (
                current, self.year-1)
        # Months July - December == Autumn semester
        current = "(r.terminkode = 'HØST' AND r.arstall=%d)\n" % self.year
        if only_current or self.mndnr >= 10 or (self.mndnr == 9 and self.dday > 15):
            return current
        return "(%s OR (r.terminkode = 'VÅR' AND r.arstall=%d))\n" % (current, self.year)

    def _get_next_termin_aar(self):
        """henter neste semesters terminkode og årstal."""
        if self.mndnr <= 6:
            next = "(r.terminkode LIKE 'H_ST' AND r.arstall=%s)\n" % self.year
        else:
            next = "(r.terminkode LIKE 'V_R' AND r.arstall=%s)\n" % (self.year + 1)
        return next

class Person(FSObject):
    def get_person(self, fnr, pnr):
        return self.db.query("""
        SELECT fornavn, etternavn, fornavn_uppercase, etternavn_uppercase,
               emailadresse, kjonn, dato_fodt
        FROM fs.person
        WHERE fodselsdato=:fnr AND personnr=:pnr""",  {'fnr': fnr, 'pnr': pnr})

    def add_person(self, fnr, pnr, fornavn, etternavn, email, kjonn,
                   birth_date):
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

    def get_personroller(self, fnr, pnr):
	return self.db.query("""
        SELECT fodselsdato, personnr, rollenr, rollekode, 
          dato_fra, dato_til, institusjonsnr, faknr, gruppenr, 
          studieprogramkode, emnekode, versjonskode, aktivitetkode, 
          terminkode, arstall, terminnr, etterutdkurskode, 
          kurstidsangivelsekode
        FROM personrolle
	WHERE 
          fodselsdato=:fnr AND 
          personnr=:pnr AND
          dato_fra < SYSDATE AND
	  NVL(dato_til,SYSDATE) >= sysdate""", {'fnr': fnr,
                                                'pnr': pnr})

    def get_fagperson(self, fnr, pnr):
        return self.db.query("""
        SELECT
          fodselsdato, personnr, adrlin1_arbeide, adrlin2_arbeide,
          postnr_arbeide, adrlin3_arbeide, telefonnr_arbeide, arbeidssted,
          institusjonsnr_ansatt, faknr_ansatt, instituttnr_ansatt,
          gruppenr_ansatt, stillingstittel_norsk, telefonnr_fax_arb,
          status_aktiv
        FROM fs.fagperson
        WHERE fodselsdato=:fnr AND personnr=:pnr""", {'fnr': fnr, 'pnr': pnr})

    def add_fagperson(self, fnr, pnr, adr1, adr2, postnr, adr3,
                      arbsted, institusjonsnr, fakultetnr, instiuttnr,
                      gruppenr, tlf, tittel, fax, status):
        return self.db.execute("""
        INSERT INTO fs.fagperson
          (fodselsdato, personnr, adrlin1_arbeide, adrlin2_arbeide,
           postnr_arbeide, adrlin3_arbeide, telefonnr_arbeide, arbeidssted,
           institusjonsnr_ansatt, faknr_ansatt, instituttnr_ansatt,
           gruppenr_ansatt, stillingstittel_norsk, telefonnr_fax_arb,
           status_aktiv)
        VALUES
          (:fnr, :pnr, :adr1, :adr2, :postnr, :adr3, :tlf, :arbsted,
           :institusjonsnr, :fakultetnr, :instiuttnr, :gruppenr, :tittel, :fax,
           :status)""", {
            'fnr': fnr, 'pnr': pnr,
            'adr1': adr1, 'adr2': adr2, 'postnr': postnr, 'adr3': adr3,
            'tlf': tlf, 'arbsted': arbsted,
            'institusjonsnr': institusjonsnr , 'fakultetnr': fakultetnr,
            'instiuttnr': instiuttnr, 'gruppenr':gruppenr,
            'tittel': tittel, 'fax': fax, 'status': status})

    def update_fagperson(self, fnr, pnr, adr1=NOT_SET, adr2=NOT_SET,
                         postnr=NOT_SET, adr3=NOT_SET,
                         arbsted=NOT_SET, institusjonsnr=NOT_SET,
                         fakultetnr=NOT_SET, instiuttnr=NOT_SET,
                         gruppenr=NOT_SET, tlf=NOT_SET,
                         tittel=NOT_SET, fax=NOT_SET, status=NOT_SET):
        """Updates the specified columns in fagperson"""
        col_map = {
            'adrlin1_arbeide': 'adr1', 'adrlin2_arbeide': 'adr2',
            'postnr_arbeide': 'postnr', 'adrlin3_arbeide': 'adr3',
            'telefonnr_arbeide': 'tlf', 'arbeidssted': 'arbsted',
            'institusjonsnr_ansatt': 'institusjonsnr',
            'faknr_ansatt': 'fakultetnr', 'instituttnr_ansatt': 'instiuttnr',
            'gruppenr_ansatt': 'gruppenr', 'stillingstittel_norsk': 'tittel',
            'telefonnr_fax_arb': 'fax', 'status_aktiv': 'status'
            }
        binds = {'fnr': fnr, 'pnr': pnr}
        set = []
        for col, arg in col_map.items():
            tmp = locals()[arg]
            if tmp != NOT_SET:
                set.append("%s=:%s"% (col, arg))
                binds[arg] = tmp

        return self.db.execute("""
        UPDATE fs.fagperson
        SET %s
        WHERE fodselsdato=:fnr AND personnr=:pnr""" % ", ".join(set), binds)

    def list_dead_persons(self): # GetDod
        """Henter en liste med de personer som ligger i FS og som er
           registrert som død.  Listen kan sikkert kortes ned slik at
           man ikke tar alle, men i denne omgang så gjør vi det
           slik."""
        qry = """
        SELECT p.fodselsdato, p.personnr
        FROM   fs.person p
        WHERE  p.status_dod = 'J'"""
        return self.db.query(qry)

    def list_fnr_endringer(self): # GetFnrEndringer
        """Hent informasjon om alle registrerte fødselsnummerendringer"""
        qry = """
        SELECT fodselsdato_naverende, personnr_naverende,
               fodselsdato_tidligere, personnr_tidligere,
               TO_CHAR(dato_foretatt, 'YYYY-MM-DD HH24:MI:SS') AS dato_foretatt
        FROM fs.fnr_endring
        ORDER BY dato_foretatt"""
        return self.db.query(qry)

    def list_email(self, fetchall = False): # GetAllPersonsEmail
        return self.db.query("""
        SELECT fodselsdato, personnr, emailadresse
        FROM fs.person""", fetchall = fetchall)

    def write_email(self, fodselsdato, personnr, email): # WriteMailAddr
        self.db.execute("""
        UPDATE fs.person
        SET emailadresse=:email
        WHERE fodselsdato=:fodselsdato AND personnr=:personnr""",
                        {'fodselsdato': fodselsdato,
                         'personnr': personnr,
                         'email': email})

    def list_uname(self, fetchall = False): # GetAllPersonsUname
        return self.db.query("""
        SELECT fodselsdato, personnr, brukernavn
        FROM fs.person""", fetchall = fetchall)

    def write_uname(self, fodselsdato, personnr, uname): # WriteUname
        self.db.execute("""
        UPDATE fs.person
        SET brukernavn = :uname
        WHERE fodselsdato = :fodselsdato AND personnr = :personnr""",
                        {'fodselsdato': fodselsdato,
                         'personnr': personnr,
                         'uname': uname})

class Student(FSObject):
    def list_semreg(self):   # GetStudinfRegkort
        """Hent informasjon om semester-registrering og betaling"""
        qry = """
        SELECT DISTINCT
               fodselsdato, personnr, regformkode, dato_endring, dato_opprettet
        FROM fs.registerkort r
        WHERE %s""" % self._get_termin_aar(only_current=1)
        return self.db.query(qry)

    def get_semreg(self,fnr,pnr):  # GetStudentSemReg
        """Hent data om semesterregistrering for student i nåværende semester."""
        qry = """
        SELECT DISTINCT
          r.regformkode, r.betformkode, r.dato_betaling, r.dato_regform_endret
        FROM fs.registerkort r, fs.person p
        WHERE r.fodselsdato = :fnr AND
              r.personnr = :pnr AND
              %s AND
              r.fodselsdato = p.fodselsdato AND
              r.personnr = p.personnr AND
              %s
        """ %(self._get_termin_aar(only_current=1), self._is_alive())
	return self.db.query(qry, {'fnr': fnr, 'pnr': pnr})

    def list_eksamensmeldinger(self):  # GetAlleEksamener
	"""Hent ut alle eksamensmeldinger i nåværende sem.
	samt fnr for oppmeldte(topics.xml)"""
        # TODO: Det er mulig denne skal splittes i to søk, ett som
        # returnerer lovlige, og et som returnerer "ulovlige"
        # eksamensmeldinger (sistnevnte er vel GetStudinfPrivatist?)
	qry = """
        SELECT p.fodselsdato, p.personnr, e.emnekode, e.studieprogramkode
        FROM fs.person p, fs.eksamensmelding e
        WHERE p.fodselsdato=e.fodselsdato AND
              p.personnr=e.personnr AND
              e.arstall=%s 
              AND %s
        ORDER BY fodselsdato, personnr
        """ % (self.year, self._is_alive())                            
      	return self.db.query(qry)

    def get_eksamensmeldinger(self, fnr, pnr): # GetStudentEksamen
	"""Hent alle aktive eksamensmeldinger for en student"""
        qry = """
        SELECT DISTINCT
          em.emnekode, em.dato_opprettet, em.status_er_kandidat
        FROM fs.eksamensmelding em, fs.person p
        WHERE em.fodselsdato = :fnr AND
              em.personnr = :pnr AND
              em.fodselsdato = p.fodselsdato AND
              em.personnr = p.personnr AND
              em.arstall >= %s
              AND %s""" % (self.year, self._is_alive())
        return self.db.query(qry, {'fnr': fnr,
                                   'pnr': pnr})

    def get_studierett(self, fnr, pnr): # GetStudentStudierett_50
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
    
    def get_emne_eksamensmeldinger(self, emnekode):  # GetEmneinformasjon
        """Hent informasjon om alle som er registrert på EMNEKODE"""
        query = """
        SELECT p.fodselsdato, p.personnr, p.fornavn, p.etternavn
        FROM person p, eksamensmelding e
        WHERE e.emnekode = :emnekode AND
             e.fodselsdato = p.fodselsdato AND
             e.personnr = p.personnr"""
        # NB! Oracle driver does not like :foo repeated multiple times :-(
        # That is why we interpolate variables into the query directly.
        if month < 6:
            time_part = """
                        AND e.arstall >= %(self.year)d
                        AND e.manednr >= %(self.mndnr)d
                        """ % locals()
        else:
            time_part = """
                        AND ((e.arstall = %(self.year)d AND
                              e.manednr >= %(self.mndnr)d) OR
                             (e.arstall > %(self.year)d))
                        """ % locals()
        return self.db.query(query + time_part, {"emnekode" : emnekode})

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

    def get_utdanningsplan(self, fnr, pnr): # GetStudentUtdPlan
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
        uklart"""

        qry = """
        SELECT DISTINCT
              p.fodselsdato, p.personnr, p.etternavn, p.fornavn, 
              p.adrlin1_hjemsted, p.adrlin2_hjemsted,
              p.postnr_hjemsted, p.adrlin3_hjemsted, p.adresseland_hjemsted,
              p.sprakkode_malform, osp.studieprogramkode, 
              p.status_reserv_nettpubl, p.kjonn, p.status_dod
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

    def list_utvekslings_student(self): # GetStudinfUtvekslingsStudent
        """ Henter personer som er registrert som utvekslingsSTUDENT i
            fs.utvekslingsperson. Vi henter 14 dager før studenten står
            på trappa. """ 
        qry = """
        SELECT DISTINCT s.fodselsdato, s.personnr, p.etternavn, p.fornavn,
               s.adrlin1_semadr,s.adrlin2_semadr, s.postnr_semadr,
               s.adrlin3_semadr, s.adresseland_semadr, p.adrlin1_hjemsted,
               p.adrlin2_hjemsted, p.postnr_hjemsted, p.adrlin3_hjemsted,
               p.adresseland_hjemsted, p.status_reserv_nettpubl, 
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

    def list_permisjon(self): # GetStudinfPermisjon
        """Hent personer som har innvilget permisjon.  Disse vil
        alltid ha opptak, så vi henter bare noen få kolonner.
        Disse tildeles affiliation student med kode permisjon
	til sp.faknr_studieansv, sp.instituttnr_studieansv, 
        sp.gruppenr_studieansv"""

        qry = """
        SELECT  pe.studieprogramkode, pe.fodselsdato, pe.personnr,
        	pe.fraverarsakkode_hovedarsak 
        FROM fs.innvilget_permisjon pe, fs.person p
        WHERE p.fodselsdato = pe.fodselsdato AND
              p.personnr = pe.personnr AND
              dato_fra < SYSDATE AND NVL(dato_til, SYSDATE) >= SYSDATE
              AND %s
        """ % self._is_alive()
        return self.db.query(qry)


    def list_drgrad(self): # GetStudinfDrgrad
	"""Henter info om aktive doktorgradsstudenter.  Aktive er
        definert til å være de som har en studierett til et program
        som har nivåkode lik 980, og der datoen for tildelt studierett
        er passert og datoen for fratatt studierett enten ikke er satt
        eller ikke passert."""

        qry = """
        SELECT DISTINCT
	       sps.fodselsdato, sps.personnr,
               sp.institusjonsnr_studieansv AS institusjonsnr,
               sp.faknr_studieansv AS faknr,
               sp.instituttnr_studieansv AS instituttnr, 
               sp.gruppenr_studieansv AS gruppenr,
               sps.dato_studierett_tildelt,
               sps.dato_studierett_gyldig_til,
               sps.studieprogramkode,
               p.adrlin1_hjemsted, p.adrlin2_hjemsted,
               p.adrlin3_hjemsted, postnr_hjemsted,
               p.adresseland_hjemsted
        FROM fs.studieprogramstudent sps, fs.studieprogram sp, fs.person p
        WHERE p.fodselsdato = sps.fodselsdato AND
              p.personnr = sps.personnr AND
              (NVL(sps.dato_beregnet_slutt, sysdate) >= SYSDATE OR
               NVL(sps.dato_planlagt_slutt, sysdate) >= SYSDATE) AND
              sps.studieprogramkode = sp.studieprogramkode AND
              sp.studienivakode >= 980"""
        return self.db.query(qry)

    def list_privatist(self):
	"""Her henter vi informasjon om privatister.
	Som privatist regnes alle studenter med en forekomst i
	FS.STUDIEPROGRAMSTUDENT der dato_studierett_gyldig_til
        er større eller lik dagens dato og studierettstatuskode
        er PRIVATIST eller status_privatist er satt til 'J'"""
	qry = """
        SELECT DISTINCT
          p.fodselsdato, p.personnr, p.etternavn,
          p.fornavn, p.kjonn, s.adrlin1_semadr,
          s.adrlin2_semadr, s.postnr_semadr, s.adrlin3_semadr,
          s.adresseland_semadr, p.adrlin1_hjemsted,
          p.sprakkode_malform,sps.studieprogramkode,
          sps.studieretningkode, sps.status_privatist, 
          s.studentnr_tildelt, p.telefonnr_mobil
        FROM fs.student s, fs.person p, fs.studieprogramstudent sps
        WHERE p.fodselsdato = s.fodselsdato AND
          p.personnr = s.personnr AND
          p.fodselsdato = sps.fodselsdato AND
          p.personnr = sps.personnr AND
          (sps.studierettstatkode = 'PRIVATIST' OR
          sps.status_privatist = 'J') AND
          sps.dato_studierett_gyldig_til >= sysdate """
        return self.db.query(qry)

class Undervisning(FSObject):
    def list_aktivitet(self, Instnr, emnekode, versjon, termk,
                       aar, termnr, aktkode): # GetStudUndAktivitet
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
	qry = """
	SELECT DISTINCT
	  fodselsdato, personnr, rollenr, rollekode,
	  dato_fra, dato_til, institusjonsnr, faknr, 
	  gruppenr, studieprogramkode, emnekode,
	  versjonskode, aktivitetkode, terminkode, 
	  arstall, terminnr, etterutdkurskode, 
	  kurstidsangivelsekode
        FROM fs.personrolle
	WHERE 
          dato_fra < SYSDATE AND
	  NVL(dato_til,SYSDATE) >= sysdate"""
        return self.db.query(qry)

    def list_undervisningenheter(self, year=None, sem=None): # GetUndervEnhetAll
        if year is None:
            year = self.year
        if sem is None:
            sem = self.semester
        return self.db.query("""
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
          ue.terminkode IN ('VÅR', 'HØST') AND
          ue.terminkode = t.terminkode AND
          (ue.arstall > :aar OR
           (ue.arstall = :aar2 AND
            EXISTS(SELECT 'x' FROM fs.arstermin tt
            WHERE tt.terminkode = :sem AND
                  t.sorteringsnokkel >= tt.sorteringsnokkel)))""",
                             {'aar': year,
                              'aar2': year, # db-driver bug work-around
                              'sem': sem})

    def list_aktiviteter(self, start_aar=time.localtime()[0],
                         start_semester=None):
        if start_semester is None:
            start_semester = self.semester
        return self.db.query("""
        SELECT  
          ua.institusjonsnr, ua.emnekode, ua.versjonskode,
          ua.terminkode, ua.arstall, ua.terminnr, ua.aktivitetkode,
          ua.undpartilopenr, ua.disiplinkode, ua.undformkode, ua.aktivitetsnavn
        FROM
          undaktivitet ua,
          arstermin t
        WHERE
          ua.undpartilopenr IS NOT NULL AND
          ua.disiplinkode IS NOT NULL AND
          ua.undformkode IS NOT NULL AND
          ua.terminkode IN ('VÅR', 'HØST') AND
          ua.terminkode = t.terminkode AND
          ((ua.arstall = :aar AND
            EXISTS (SELECT 'x' FROM fs.arstermin tt
                    WHERE tt.terminkode = :semester AND
                          t.sorteringsnokkel >= tt.sorteringsnokkel)) OR
           ua.arstall > :aar)""",
                             {'aar': start_aar,
                              'semester': start_semester})

    def get_undform_aktiviteter(self, Instnr, emnekode, versjon, termk,
                                aar, termnr, undformkode):
        """
        Returnerer alle aktiviteter med en gitt undformkode innen det
        oppgitte (år, semester)
        """

        return self.db.query("""
        SELECT
          ua.institusjonsnr, ua.emnekode, ua.versjonskode,
          ua.terminkode, ua.arstall, ua.terminnr, ua.aktivitetkode
        FROM
          undaktivitet ua,
          arstermin t
        WHERE
          ua.institusjonsnr = :Instnr AND
          ua.emnekode = :emnekode AND
          ua.versjonskode = :versjon AND
          ua.terminkode = :termk AND
          ua.terminnr = :termnr AND
          ua.undformkode = :undformkode AND
          ua.terminkode IN ('VÅR', 'HØST') AND
          ua.terminkode = t.terminkode AND
          ((ua.arstall = :aar AND
            EXISTS (SELECT 'x' FROM fs.arstermin tt
                    WHERE tt.terminkode = :termk AND
                    t.sorteringsnokkel >= tt.sorteringsnokkel)) OR
           ua.arstall > :aar)
          """, { "Instnr"      : Instnr,
                 "emnekode"    : emnekode,
                 "versjon"     : versjon,
                 "termk"       : termk,
                 "termnr"      : termnr,
                 "aar"         : aar,
                 "undformkode" : undformkode, })
    # end get_undform_aktiviteter


    def list_studenter_underv_enhet(self,  # GetStudUndervEnhet
                                Instnr, emnekode, versjon, termk, aar, termnr):
        if termk == 'VÅR':
            minmaned, maxmaned = 1, 6
        elif termk == 'HØST':
            minmaned, maxmaned = 7, 12
        else:
            # Ikke blant de terminkodene vi støtter i dag; sørg for at
            # eksamensmelding-delen av søket ikke gir noe resultat.
            minmaned, maxmaned = 13, 0
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
        SELECT
          fodselsdato, personnr
        FROM
          FS.EKSAMENSMELDING
        WHERE
          institusjonsnr = :instnr AND
          emnekode       = :emnekode AND
          versjonskode   = :versjon AND
          arstall        = :arstall AND
          manednr       >= :minmaned AND
          manednr       <= :maxmaned"""
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
                                   'minmaned': minmaned,
                                   'maxmaned': maxmaned})

    def list_fagperson_semester(self): # GetFagperson_50
        # (GetKursFagpersonundsemester var duplikat)
	"""Disse skal gis affiliation tilknyttet med kode fagperson 
        til stedskoden faknr+instituttnr+gruppenr
        Hent ut fagpersoner som har undervisning i inneværende
        eller forrige kalenderår"""

        qry = """
        SELECT DISTINCT 
              fp.fodselsdato, fp.personnr, p.etternavn, p.fornavn,
              fp.adrlin1_arbeide, fp.adrlin2_arbeide, fp.postnr_arbeide,
              fp.adrlin3_arbeide, fp.adresseland_arbeide,
              fp.telefonnr_arbeide, fp.telefonnr_fax_arb,
              p.adrlin1_hjemsted, p.adrlin2_hjemsted, p.postnr_hjemsted,
              p.adrlin3_hjemsted, p.adresseland_hjemsted, 
              p.telefonnr_hjemsted, fp.stillingstittel_engelsk, 
              fp.institusjonsnr_ansatt AS institusjonsnr,
              fp.faknr_ansatt AS faknr,
              fp.instituttnr_ansatt AS instituttnr,
              fp.gruppenr_ansatt AS gruppenr,
              fp.status_aktiv, p.status_reserv_lms AS status_publiseres,
              p.kjonn, p.status_dod
        FROM fs.person p, fs.fagperson fp
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
        return self.db.execute("""
        INSERT INTO fs.fagpersonundsemester
          (fodselsdato, personnr, terminkode, arstall, institusjonsnr, faknr,
           instituttnr, gruppenr, status_aktiv, status_publiseres)
        VALUES
          (:fnr, :pnr, :termin, :arstall, :institusjonsnr, :fakultetnr,
          :instiuttnr, :gruppenr, :status_aktiv, :status_publiseres)""", {
            'fnr': fnr, 'pnr': pnr,
            'institusjonsnr': institusjonsnr, 'fakultetnr': fakultetnr,
            'instiuttnr': instiuttnr, 'gruppenr': gruppenr,
            'termin': termin, 'arstall': arstall,
            'status_aktiv': status_aktiv, 'status_publiseres': status_publiseres})


class EVU(FSObject):
    def list(self):  # GetDeltaker_50
    	"""Hent info om personer som er ekte EVU-studenter ved
    	dvs. er registrert i EVU-modulen i tabellen 
    	fs.deltaker,  Henter alle som er knyttet til kurs som
        tidligst ble avsluttet for 30 dager siden."""

 	qry = """
        SELECT DISTINCT 
               p.fodselsdato, p.personnr, p.etternavn, p.fornavn,
               d.adrlin1_job, d.adrlin2_job, d.postnr_job,
               d.adrlin3_job, d.adresseland_job, d.adrlin1_hjem,
               d.adrlin2_hjem, d.postnr_hjem, d.adrlin3_hjem,
               d.adresseland_hjem, p.adrlin1_hjemsted,
               p.status_reserv_nettpubl, p.adrlin2_hjemsted,
               p.postnr_hjemsted, p.adrlin3_hjemsted,
               p.adresseland_hjemsted, d.deltakernr, d.emailadresse,
               k.etterutdkurskode, e.studieprogramkode,
               e.faknr_adm_ansvar, e.instituttnr_adm_ansvar,
               e.gruppenr_adm_ansvar, p.kjonn, p.status_dod
        FROM fs.deltaker d, fs.person p, fs.kursdeltakelse k,
             fs.etterutdkurs e
        WHERE p.fodselsdato=d.fodselsdato AND
              p.personnr=d.personnr AND
              d.deltakernr=k.deltakernr AND
              e.etterutdkurskode=k.etterutdkurskode AND
              (NVL(e.status_kontotildeling,'J')='J' OR 
              NVL(e.status_nettbasert_und,'J')='J') AND
              k.kurstidsangivelsekode = e.kurstidsangivelsekode AND
              NVL(e.dato_til, SYSDATE) >= SYSDATE - 30"""
	return self.db.query(qry)
        
    def list_kurs(self, date=time.localtime()):  # GetEvuKurs
        d = time.strftime("%Y-%m-%d", date)
        qry = """
        SELECT e.etterutdkurskode, e.kurstidsangivelsekode, e.etterutdkursnavn,
          e.etterutdkursnavnkort,
          e.institusjonsnr_adm_ansvar, e.faknr_adm_ansvar,
          e.instituttnr_adm_ansvar, e.gruppenr_adm_ansvar,
          TO_CHAR(NVL(e.dato_fra, SYSDATE), 'YYYY-MM-DD') AS dato_fra,
          TO_CHAR(NVL(e.dato_til, SYSDATE), 'YYYY-MM-DD') AS dato_til,
          e.status_aktiv, e.status_nettbasert_und
        FROM fs.etterutdkurs e
        WHERE NVL(TO_DATE('%s', 'YYYY-MM-DD'), SYSDATE) <
              NVL(e.dato_til, SYSDATE) + 30
        """ % d
        return self.db.query(qry)

    def get_kurs_informasjon(self, code): # GetEvuKursInformasjon
        """
        This one works similar to GetEvuKurs, except for the filtering
        criteria: in this method we filter by course code, not by time frame
        """
        query = """
        SELECT etterutdkurskode, kurstidsangivelsekode,
          TO_CHAR(dato_fra, 'YYYY-MM-DD') as dato_fra,
          TO_CHAR(dato_til, 'YYYY-MM-DD') as dato_til
        FROM etterutdkurs 
        WHERE etterutdkurskode = :code
        """
        return self.db.query(query, {"code" : code})

    def list_kurs_deltakere(self, kurskode, tid):  # GetEvuKursPameldte
        """List everyone registered for a given course"""
        query = """
        SELECT fodselsdato, personnr,
          fornavn, etternavn
        FROM person p, etterutdkurs] e,
          kursdeltakelse kd, deltaker d
        WHERE e.etterutdkurskode like :kurskode AND
          e.kurstidsangivelsekode like :tid AND
          e.etterutdkurskode = kd.etterutdkurskode AND
          e.kurstidsangivelsekode = kd.kurstidsangivelsekode AND
          kd.deltakernr = d.deltakernr AND
          d.fodselsdato = p.fodselsdato AND
          d.personnr = p.personnr"""
        return self.db.query(query, {"kurskode" : kurskode,
                                     "tid" : tid})

    def get_kurs_aktivitet(self, kurs, tid): # GetAktivitetEvuKurs
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



class Alumni(FSObject):
    def list(self):  # GetAlumni_50
        """Henter informasjon om alle som har fullført
        studium frem til en grad, min. Cand.Mag.  Disse regnes
        som 'Alumni' ved UiO."""
        qry = """
        SELECT DISTINCT s.fodselsdato, s.personnr, p.etternavn, p.fornavn,
               s.adrlin1_semadr,s.adrlin2_semadr, s.postnr_semadr,
               s.adrlin3_semadr, s.adresseland_semadr,
               p.adrlin1_hjemsted, p.adrlin2_hjemsted,
               p.postnr_hjemsted, p.adrlin3_hjemsted,
               p.adresseland_hjemsted, p.status_reserv_nettpubl,
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

class StudieInfo(FSObject):
    def list_studieprogrammer(self): # GetStudieproginf
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
        return self.db.query(qry)

    def list_emner(self): # GetEmneinf
	"""For hvert definerte emne henter vi informasjon om 
           ansvarlig sted."""
        qry = """
        SELECT e.emnekode, e.versjonskode, e.institusjonsnr,
               e.faknr_reglement, e.instituttnr_reglement,
               e.gruppenr_reglement, e.studienivakode
        FROM fs.emne e
        WHERE e.institusjonsnr = %s AND
              NVL(e.arstall_eks_siste, %s) >= %s - 1""" % (self.institusjonsnr, self.year, self.year)
        return self.db.query(qry)

    def get_emne_i_studieprogram(self,emne): # GetEmneIStudProg
        """Hent alle studieprogrammer et gitt emne kan inngå i."""
        qry = """
        SELECT DISTINCT 
          studieprogramkode   
        FROM fs.emne_i_studieprogram
        WHERE emnekode = :emne
        """ 
        return self.db.query(qry, {'emne': emne})

    def list_ou(self, institusjonsnr=0): # GetAlleOUer
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

    def list_kull(self):
       	"""Henter informasjon om aktive studiekull."""
	qry = """
        SELECT
          studieprogramkode, kullkode, studiekullnavn, 
          klassetrinn_start, terminnr_maks
        FROM  fs.studiekull
        WHERE status_aktiv = 'J' """
        return self.db.query(qry) 

class FS(object):
    def __init__(self, db=None, user=None, database=None):
        if db is None:
            # TBD: Should user and database have default values in
            # cereconf?
            db = Database.connect(user = user, service = database,
                                  DB_driver = 'Oracle')
        self.db = db
        self.person = Person(db)
        self.student = Student(db)
        self.undervisning = Undervisning(db)
        self.evu = EVU(db)
        self.alumni = Alumni(db)
        # self.info = AdministrativInfo(db)

    def list_dbfg_usernames(self, fetchall = False):
        """
        Get all usernames and return them as a sequence of db_rows.

        NB! This function does *not* return a 2-tuple. Only a sequence of
        all usernames (the column names can be obtains from db_row objects)
        """

        query = """
        SELECT username as username
        FROM all_users
        """
        return self.db.query(query, fetchall = fetchall)

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

    def __init__(self, filename, callback, encoding='iso8859-1'):
        self._callback = callback
        self._encoding = encoding
        xml.sax.parse(filename, self)

    def startElement(self, name, attrs):
        if name not in self.elements:
            raise ValueError, \
                  "Unknown XML element: %r" % (name,)
        # Only set self._in_element etc. for interesting elements.
        if self.elements[name]:
            data = {}
            for k, v in attrs.items():
                data[k] = v.encode(self._encoding)
            self._callback(name, data)

class non_nested_xml_parser(element_attribute_xml_parser):

    def __init__(self, filename, callback, encoding='iso8859-1'):
        self._in_element = None
        self._attrs = None
        super(non_nested_xml_parser, self).__init__(
            filename, callback, encoding)

    def startElement(self, name, attrs):
        if name not in self.elements:
            raise ValueError, \
                  "Unknown XML element: %r" % (name,)
        if self._in_element is not None:
            raise RuntimeError, \
                  "Can't deal with nested elements (<%s> before </%s>)." % (
                name, self._in_element)
        # Only set self._in_element etc. for interesting elements.
        if self.elements[name]:
            self._in_element = name
            self._data = {}
            for k, v in attrs.items():
                self._data[k] = v.encode(self._encoding)

    def endElement(self, name):
        if name not in self.elements:
            raise ValueError, \
                  "Unknown XML element: %r" % (name,)
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
        # Verifiser at rollen _enten_ gjelder en (fullstendig
        # spesifisert) undervisningsenhet _eller_ en und.aktivitet
        # _eller_ et studieprogram, osv. -- og ikke litt av hvert.
        col2target = {
            'fodselsdato': None,
            'personnr': None,
            'rollenr': None,
            'rollekode': None,
            'dato_fra': None,
            'dato_til': None,
            'institusjonsnr': ['sted', 'emne', 'undenh', 'undakt', 'evu'],
            'faknr': ['sted'],
            'instituttnr': ['sted'],
            'gruppenr': ['sted'],
            'studieprogramkode': ['stprog'],
            'emnekode': ['emne', 'undenh', 'undakt'],
            'versjonskode': ['emne', 'undenh', 'undakt'],
            'aktivitetkode': ['undakt', 'kursakt'],
            'terminkode': ['undenh', 'undakt'],
            'arstall': ['undenh', 'undakt'],
            'terminnr': ['undenh', 'undakt'],
            'etterutdkurskode': ['evu', 'kursakt'],
            'kurstidsangivelsekode': ['evu', 'kursakt'],
            'saksbehinit_opprettet': None,
            'dato_opprettet': None,
            'saksbehinit_endring': None,
            'dato_endring': None,
            'merknadtekst': None,
            }
        data = attrs.copy()
        target = None
        not_target = sets.Set()
        possible_targets = sets.Set()
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
                    target = sets.Set(targs)
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
        if len(target) <> 1:
            if len(target) > 1:
                self.logger.error("Personrolle har flertydig angivelse av",
                                  " targets, kan være: %r (XML = %r).",
                                  target, attrs)
                attrs[self.target_key] = target
            else:
                self.logger.error("Personrolle har ingen tilstrekkelig"
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

    elements = { "data" : False,
                 "evukurs" : True }
# end evukurs_xml_parser


class deltaker_xml_parser(xml.sax.ContentHandler, object):
    "Parserklasse for å hente EVU kursdeltaker informasjon."
                          
    def __init__(self, filename, callback, encoding="iso8859-1"):
        self._callback = callback
        self._encoding = encoding
        self._in_person = False
        self._legal_elements = ("person", "evu", "aktiv", "tilbud",
                                "data", "privatist_studieprogram")
        xml.sax.parse(filename, self)
    # end __init__

    def startElement(self, name, attrs):
        if name not in self._legal_elements:
            raise ValueError, "Unknown XML element: %r" % (name,)
        # fi

        if name not in ("person", "evu"):
            return
        # fi

        tmp = dict()
        for k, v in attrs.items():
            tmp[k] = v.encode(self._encoding)
        # od

        if name == "person":
            assert not self._in_person, "Nested <person> element!"
            self._in_person = { "evu" : list(), }
            self._in_person.update(tmp)
        else:
            assert self._in_person, "<evu> outside of <person>!"
            self._in_person["evu"].append(tmp)
        # fi
    # end startElement


    def endElement(self, name):
        if name not in self._legal_elements:
            raise ValueError, "Unknown XML element: %r" % (name,)
        # fi

        if name == "person":
            self._callback(name, self._in_person)
            self._in_person = None
        # fi
    # end endElement
# end deltaker_xml_parser



        

# arch-tag: 15c18bb0-05e8-4c3b-a47c-c84566e57803
