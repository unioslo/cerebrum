# -*- coding: iso-8859-1 -*-
# Copyright 2002, 2003 University of Oslo, Norway
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

import time
import sys
from Cerebrum.modules.no import access_FS

class UiTOU(access_FS.StudieInfo):
    def GetAktiveOUer(self,institusjonsnr=186):
        """Henter data om aktive OU'er fra FS"""
        qry="""
        SELECT DISTINCT
        INSTITUSJONSNR,FAKNR,INSTITUTTNR,GRUPPENR,STEDAKRONYM,STEDNAVN_BOKMAL,ORGNIVAKODE,INSTITUSJONSNR_ORG_UNDER,FAKNR_ORG_UNDER,INSTITUTTNR_ORG_UNDER,GRUPPENR_ORG_UNDER,ADRLIN1,ADRLIN2,POSTNR,ADRLIN3,ADRESSELAND,STEDKORTNAVN,STEDNAVN_NYNORSK,STEDNAVN_ENGELSK,TELEFONLANDNR,TELEFONRETNNR,TELEFONNR,FAXNR,INSTITUSJONSNR_ERSTATTES_AV,FAKNR_ERSTATTES_AV,INSTITUTTNR_ERSTATTES_AV,GRUPPENR_ERSTATTES_AV,DATO_AKTIV_FRA,DATO_AKTIV_TIL,NSD_AVDKODE,EIERTYPEKODE,ADRLIN1_BESOK,ADRLIN2_BESOK,POSTNR_BESOK,ADRLIN3_BESOK,ADRESSELAND_BESOK,EMAILADRESSE,KODEVERDITYPE,NSDINSTKODE,INSTTYPEKODE,UTRSTEDKODE,LANDNR,TELEFONLANDNR_FAX,TELEFONRETNNR_FAX,TELEFONNR_FAX,INSTITUSJONSNR_GEOGR,FAKNR_GEOGR,INSTITUTTNR_GEOGR,GRUPPENR_GEOGR,BIBSYSBESTSTEDKODE,ORGNR,URL,TELEFONLANDNR_2,TELEFONRETNNR_2,TELEFONNR_2,MERKNADTEKST
        FROM fs.sted where institusjonsnr=%s and status_aktiv='J'
        """ % institusjonsnr
        
        return self.db.query(qry)



    def GetAlleOUer(self,institusjonsnr=186):
        """Henter data om aktive OU'er fra FS"""
        qry="""
        SELECT DISTINCT
        INSTITUSJONSNR,FAKNR,INSTITUTTNR,GRUPPENR,STEDAKRONYM,STEDNAVN_BOKMAL,ORGNIVAKODE,INSTITUSJONSNR_ORG_UNDER,FAKNR_ORG_UNDER,INSTITUTTNR_ORG_UNDER,GRUPPENR_ORG_UNDER,ADRLIN1,ADRLIN2,POSTNR,ADRLIN3,ADRESSELAND,STEDKORTNAVN,STEDNAVN_NYNORSK,STEDNAVN_ENGELSK,TELEFONLANDNR,TELEFONRETNNR,TELEFONNR,FAXNR,INSTITUSJONSNR_ERSTATTES_AV,FAKNR_ERSTATTES_AV,INSTITUTTNR_ERSTATTES_AV,GRUPPENR_ERSTATTES_AV,DATO_AKTIV_FRA,DATO_AKTIV_TIL,NSD_AVDKODE,EIERTYPEKODE,ADRLIN1_BESOK,ADRLIN2_BESOK,POSTNR_BESOK,ADRLIN3_BESOK,ADRESSELAND_BESOK,EMAILADRESSE,KODEVERDITYPE,NSDINSTKODE,INSTTYPEKODE,UTRSTEDKODE,LANDNR,TELEFONLANDNR_FAX,TELEFONRETNNR_FAX,TELEFONNR_FAX,INSTITUSJONSNR_GEOGR,FAKNR_GEOGR,INSTITUTTNR_GEOGR,GRUPPENR_GEOGR,BIBSYSBESTSTEDKODE,ORGNR,URL,TELEFONLANDNR_2,TELEFONRETNNR_2,TELEFONNR_2,MERKNADTEKST
        FROM fs.sted where institusjonsnr=%s
        """ % institusjonsnr
        
        return self.db.query(qry)



class UiTStudent(access_FS.Student):

    def list(self, **kwargs): # GetStudent_50
        """Hent personer med opptak til et studieprogram ved
        institusjonen og som enten har vært registrert siste året
        eller opptak efter 2003-01-01.  Henter ikke de som har
        fremtidig opptak.  Disse kommer med 14 dager før dato for
        tildelt opptak.  Alle disse skal ha affiliation med status
        kode 'opptak' til stedskoden sp.faknr_studieansv +
        sp.instituttnr_studieansv + sp.gruppenr_studieansv.
        """
        #return self._list_gyldigopptak(**kwargs) \
        #               + self._list_drgradsopptak(**kwargs) \
        #               +  self._list_gammelopptak_semreg(**kwargs)
        return self._list_drgradsopptak(**kwargs)


    def _list_gyldigopptak(self, fodselsdato=None, personnr=None):
        """Alle med gyldig opptak tildelt for 2 år eller mindre siden
        samt alle med opptak som blir gyldig om 14 dager.
        """

        extra = ""
        if fodselsdato and personnr:
            extra = "s.fodselsdato=:fodselsdato AND s.personnr=:personnr AND"

        qry = """
        SELECT DISTINCT
           s.fodselsdato, s.personnr, p.etternavn, p.fornavn,
           s.adrlin1_semadr,s.adrlin2_semadr, s.postnr_semadr,
           s.adrlin3_semadr, s.adresseland_semadr, p.adrlin1_hjemsted,
           p.adrlin2_hjemsted, p.postnr_hjemsted, p.adrlin3_hjemsted,
           p.adresseland_hjemsted, p.status_reserv_nettpubl,
           p.sprakkode_malform, sps.studieprogramkode, sps.studieretningkode,
           sps.studierettstatkode, sps.studentstatkode, sps.terminkode_kull,
           sps.arstall_kull, sp.studienivakode, p.kjonn, p.status_dod
        FROM fs.student s, fs.person p, fs.studieprogramstudent sps,
           fs.studieprogram sp
        WHERE  p.fodselsdato=s.fodselsdato AND
           p.personnr=s.personnr AND
           p.fodselsdato=sps.fodselsdato AND
           p.personnr=sps.personnr AND
           %s
           sps.studieprogramkode=sp.studieprogramkode AND
           NVL(sps.dato_studierett_gyldig_til,SYSDATE) >= sysdate AND
           sps.status_privatist = 'N' AND
           sps.dato_studierett_tildelt < SYSDATE + 14 AND           
           sps.dato_studierett_tildelt >= to_date('2003-01-01', 'yyyy-mm-dd') AND
           %s
           """ % (extra, self._is_alive())
        return self.db.query(qry, locals())

    #studentstatkode.studentstatus.status_aktiv_student=('J/N')
    # studieprogramstudent.studentstatkode('aktiv/permision')
    # studierett_gyldig_til
    def _list_drgradsopptak(self, fodselsdato=None, personnr=None):
        """Alle drgradsstudenter med ikke utgått opptak til drgrads-
        studieprogram.
        """

        extra = ""
        if fodselsdato and personnr:
            extra = "s.fodselsdato=:fodselsdato AND s.personnr=:personnr AND"

        qry = """
        SELECT DISTINCT
           s.fodselsdato, s.personnr, p.etternavn, p.fornavn,
           s.adrlin1_semadr,s.adrlin2_semadr, s.postnr_semadr,
           s.adrlin3_semadr, s.adresseland_semadr, p.adrlin1_hjemsted,
           p.adrlin2_hjemsted, p.postnr_hjemsted, p.adrlin3_hjemsted,
           p.adresseland_hjemsted, p.status_reserv_nettpubl,
           p.sprakkode_malform, sps.studieprogramkode, sps.studieretningkode,
           sps.studierettstatkode, sps.studentstatkode, sps.terminkode_kull,
           sps.arstall_kull, sp.studienivakode, p.kjonn, p.status_dod
        FROM fs.student s, fs.person p, fs.studieprogramstudent sps,
           fs.studieprogram sp
        WHERE  p.fodselsdato=s.fodselsdato AND
           p.personnr=s.personnr AND
           p.fodselsdato=sps.fodselsdato AND
           p.personnr=sps.personnr AND
           %s
           (NVL(sps.dato_beregnet_slutt, sysdate) > SYSDATE OR
           NVL(sps.dato_planlagt_slutt, sysdate) > SYSDATE) AND
           sps.status_privatist='N' AND
           sps.studieprogramkode=sp.studieprogramkode AND
           sp.studienivakode >= 900 AND
           ((sps.studentstatkode='AKTIV') or (sps.studentstatkode='PERMISJON')) AND
           %s""" % (extra, self._is_alive())
        return self.db.query(qry, locals())

    def _list_gammelopptak_semreg(self, fodselsdato=None, personnr=None):
        """Alle med gyldig opptak som har hatt en forekomst i
        registerkort i løpet av fjoråret.
        """

        extra = ""
        if fodselsdato and personnr:
            extra = "s.fodselsdato=:fodselsdato AND s.personnr=:personnr AND"

        qry = """
        SELECT DISTINCT
           s.fodselsdato, s.personnr, p.etternavn, p.fornavn,
           s.adrlin1_semadr,s.adrlin2_semadr, s.postnr_semadr,
           s.adrlin3_semadr, s.adresseland_semadr, p.adrlin1_hjemsted,
           p.adrlin2_hjemsted, p.postnr_hjemsted, p.adrlin3_hjemsted,
           p.adresseland_hjemsted, p.status_reserv_nettpubl,
           p.sprakkode_malform, sps.studieprogramkode, sps.studieretningkode,
           sps.studierettstatkode, sps.studentstatkode, sps.terminkode_kull,
           sps.arstall_kull, sp.studienivakode, p.kjonn, p.status_dod
        FROM fs.student s, fs.person p, fs.studieprogramstudent sps,
           fs.registerkort r, fs.studieprogram sp
        WHERE  p.fodselsdato=s.fodselsdato AND
           p.personnr=s.personnr AND
           p.fodselsdato=sps.fodselsdato AND
           p.personnr=sps.personnr AND
           p.fodselsdato=r.fodselsdato AND
           p.personnr=r.personnr AND
           %s
           sps.studieprogramkode=sp.studieprogramkode AND
           NVL(sps.dato_studierett_gyldig_til,SYSDATE) >= sysdate AND
           sps.status_privatist = 'N' AND
           r.arstall >= (%s - 1) AND
           %s""" % (extra, self.year, self._is_alive())
        return self.db.query(qry, locals())



    # Aktive studenter etter UiTø's definisjon
    def list_aktiv(self):
	""" Hent opplysninger om studenter definert som aktive 
	ved HiA. En aktiv student er enten med i et aktivt kull og
        har et gyldig studierett eller har en forekomst i registerkort 
        for inneværende semester og har en gyldig studierett"""

	qry = """
        SELECT DISTINCT
          s.fodselsdato, s.personnr, p.etternavn, p.fornavn,
          s.adrlin1_semadr,s.adrlin2_semadr, s.postnr_semadr,
          s.adrlin3_semadr, s.adresseland_semadr, p.adrlin1_hjemsted,
          p.adrlin2_hjemsted, p.postnr_hjemsted, p.adrlin3_hjemsted,
          p.adresseland_hjemsted, p.status_reserv_nettpubl,
          p.sprakkode_malform, sps.studieprogramkode, sps.studieretningkode,
          sps.studierettstatkode, sps.studentstatkode, sps.terminkode_kull,
          sps.arstall_kull, p.kjonn, p.status_dod, p.telefonnr_mobil,
          s.studentnr_tildelt
        FROM fs.kull k, fs.studieprogramstudent sps, fs.person p,
             fs.student s
        WHERE p.fodselsdato = sps.fodselsdato AND
          p.personnr = sps.personnr AND
          p.fodselsdato = s.fodselsdato AND
          p.personnr = s.personnr AND
          %s AND
          k.studieprogramkode = sps.studieprogramkode AND
          k.terminkode = sps.terminkode_kull AND
          k.arstall = sps.arstall_kull AND
          NVL(k.status_aktiv,'J') = 'J' AND
          NVL(sps.dato_studierett_gyldig_til,SYSDATE)>= SYSDATE
        UNION
        SELECT DISTINCT
          s.fodselsdato, s.personnr, p.etternavn, p.fornavn,
          s.adrlin1_semadr,s.adrlin2_semadr, s.postnr_semadr,
          s.adrlin3_semadr, s.adresseland_semadr, p.adrlin1_hjemsted,
          p.adrlin2_hjemsted, p.postnr_hjemsted, p.adrlin3_hjemsted,
          p.adresseland_hjemsted, p.status_reserv_nettpubl,
          p.sprakkode_malform, sps.studieprogramkode, sps.studieretningkode,
          sps.studierettstatkode, sps.studentstatkode, sps.terminkode_kull,
          sps.arstall_kull, p.kjonn, p.status_dod, p.telefonnr_mobil,
          s.studentnr_tildelt
        FROM fs.registerkort r, fs.studieprogramstudent sps, fs.person p, fs.student s
        WHERE p.fodselsdato = sps.fodselsdato AND
          p.personnr = sps.personnr AND
          p.fodselsdato = s.fodselsdato AND
          p.personnr = s.personnr AND
          %s AND
          p.fodselsdato = r.fodselsdato AND
          p.personnr = r.personnr AND
          NVL(sps.dato_studierett_gyldig_til,SYSDATE)>= SYSDATE AND
          %s """ % (self._is_alive(), self._is_alive(), self._get_termin_aar(only_current=1))
        return self.db.query(qry)


class UiTUndervisning(access_FS.Undervisning):
    def list_undervisningenheter(self, sem="current"):
	"""Metoden som henter data om undervisningsenheter
	i nåverende (current) eller neste (next) semester. Default
	vil være nåværende semester. For hver undervisningsenhet 
	henter vi institusjonsnr, emnekode, versjonskode, terminkode + årstall 
	og terminnr."""
	qry = """
        SELECT DISTINCT
          r.institusjonsnr, r.emnekode, r.versjonskode, e.emnenavnfork,
          e.emnenavn_bokmal, e.faknr_kontroll, e.instituttnr_kontroll, 
          e.gruppenr_kontroll, r.terminnr, r.terminkode, r.arstall
          FROM fs.emne e, fs.undervisningsenhet r
          WHERE r.emnekode = e.emnekode AND
          r.versjonskode = e.versjonskode AND """ 
        if (sem=="current"):
	    qry +="""%s""" % self._get_termin_aar(only_current=1)
        else: 
	    qry +="""%s""" % self._get_next_termin_aar()
	return self.db.query(qry)

    def list_studenter_underv_enhet(self, institusjonsnr, emnekode, versjonskode,
                                    terminkode, arstall, terminnr):
	"""Finn fødselsnumrene til alle studenter på et gitt 
	undervisningsenhet. Skal brukes til å generere grupper for
	adgang til CF."""
	qry = """
        SELECT DISTINCT
          fodselsdato, personnr
        FROM fs.undervisningsmelding
        WHERE
          institusjonsnr = :institusjonsnr AND
          emnekode = :emnekode AND
          versjonskode = :versjonskode AND
          terminnr = :terminnr AND
          terminkode = :terminkode AND
          arstall = :arstall """
        return self.db.query(qry, {'institusjonsnr': institusjonsnr,
                                   'emnekode': emnekode,
                                   'versjonskode': versjonskode,
                                   'terminnr': terminnr,
                                   'terminkode': terminkode,
                                   'arstall': arstall}
                             )

    def list_studenter_kull(self, studieprogramkode, terminkode, arstall):
        """Hent alle studentene som er oppført på et gitt kull."""

        query = """
        SELECT DISTINCT
            fodselsdato, personnr
        FROM
            fs.studieprogramstudent
        WHERE
            studieprogramkode = :studieprogramkode AND
            terminkode_kull = :terminkode_kull AND
            arstall_kull = :arstall_kull
        """

        return self.db.query(query, {"studieprogramkode" : studieprogramkode,
                                     "terminkode_kull"   : terminkode,
                                     "arstall_kull"      : arstall})
    # end list_studenter_kull


class UiTEVU(access_FS.EVU):
    def list_kurs(self, date=time.localtime()):  # GetEvuKurs
        d = time.strftime("%Y-%m-%d", date)
        qry = """
        SELECT DISTINCT e.etterutdkurskode, e.kurstidsangivelsekode,
          e.etterutdkursnavn, e.etterutdkursnavnkort, ee.emnekode,
          e.institusjonsnr_adm_ansvar, e.faknr_adm_ansvar,
          e.instituttnr_adm_ansvar, e.gruppenr_adm_ansvar,
          TO_CHAR(NVL(e.dato_fra, SYSDATE), 'YYYY-MM-DD') AS dato_fra,
          TO_CHAR(NVL(e.dato_til, SYSDATE), 'YYYY-MM-DD') AS dato_til,
          e.status_aktiv, e.status_nettbasert_und
        FROM fs.etterutdkurs e, fs.etterutdkursemne ee
        WHERE e.etterutdkurskode=ee.etterutdkurskode (+) AND
          e.kurstidsangivelsekode=ee.kurstidsangivelsekode (+) AND
          e.status_aktiv='J' AND
          e.status_nettbasert_und='J' AND
          NVL(TO_DATE('%s', 'YYYY-MM-DD'), SYSDATE) < (e.dato_til + 30)
        """ % d
        return self.db.query(qry)
    
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
              NVL(k.status_opptatt, 'N')='J' AND
              k.kurstidsangivelsekode = e.kurstidsangivelsekode AND
              NVL(e.dato_til, SYSDATE) >= SYSDATE - 30"""
        return self.db.query(qry)
    

class FS(access_FS.FS):

    def __init__(self, db=None, user=None, database=None):
        super(FS, self).__init__(db=db, user=user, database=database)

        t = time.localtime()[0:3]
        self.year = t[0]
        self.mndnr = t[1]
        self.dday = t[2]
        
        # Override with uit-spesific classes
        self.student = UiTStudent(self.db)
        self.undervisning = UiTUndervisning(self.db)
        self.evu = UiTEVU(self.db)
        self.ou = UiTOU(self.db)

class student_undakt_xml_parser(access_FS.non_nested_xml_parser):
    "Parserklasse for student_undakt.xml."

    elements = {'data': False,
                'undakt': True
                }

class undakt_xml_parser(access_FS.non_nested_xml_parser):
    "Parserklasse for undakt.xml."

    elements = {'data': False,
                'undakt': True
                }

class person_xml_parser(access_FS.non_nested_xml_parser):
    "Parserklasse for person.xml."
    elements = {'data': False,
                'opptak':False,
                'drgrad':True,
                'aktiv': True,
                'tilbud': True,
                'fagperson': True,
                'evu': True,
                'privatist_studieprogram': True,
                'eksamen' : True,
                }
