#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
import unittest

"""Modul for å resolve CanonicalName og ProfilePath for Active
Directory ved Høyskolen i Østfold.

Alle disse verdiene utledes av en stedkode knyttet til brukeren, med
litt forskjellige regler for hvert AD-domene.

De fleste steder kan man finne avdeling/sted ved å kun se på deler av
stedkoden, men ettersom det finnes en del unntak, har vi valgt å lage
mapping-tabeller som tar utgangspunkt i hele stedkoden."""

# Ser ikke noe stort poeng i å legge mappingene i cereconf ettersom
# modulen uansett er veldig HIOF-spesifik

class MappingError(Exception):
    pass

class Adm(object):
    DOMAIN_NAME = "adm.hiof.no"
    DOMAIN_DN = "DC=adm,DC=hiof,DC=no"
    mapping = {
        '10': 'olivia',
        '20': 'tora',
        '30': 'katta',
        '35': 'katta'
        }

    def getDN(self, sko, uname):
        serv = Adm.mapping[sko[-2:]].capitalize()
        return "CN=%s,OU=Ansatte %s,%s" % (uname, serv, Adm.DOMAIN_DN)

    def getProfilePath(self, sko, uname):
        serv = Adm.mapping[sko[-2:]]
        return r"\\%s\%s\profile" % (serv, uname)

    def getHome(self, sko, uname):
        serv = Adm.mapping[sko[-2:]]
        return r"\\%s\%s" % (serv, uname)

class Fag(object):
    DOMAIN_NAME = "fag.hiof.no"
    DOMAIN_DN = "DC=fag,DC=hiof,DC=no"
    sted_mapping = {
        ('*', '*', '00'): 'Halden', # RH: Avdeling 00 er Halden i følge Trond
        ('*', '*', '10'): 'Halden',
        ('*', '*', '20'): 'Sarp',
        ('*', '*', '30'): 'Fredr',
        ('*', '*', '35'): 'Fredr',
        ('*', '*', '40'): 'Fredr',
        ('98', '10', '*'): 'Halden'
        }
    avdeling_mapping = {
        ('98', '10', '*'): {'Canon': 'SIO', 'Profile': 'HS'},
        ('24', '*', '30'): {'All': 'HS'},
        ('26', '*', '30'): {'All': 'HS'},
        ('26', '*', '35'): {'All': 'HS'},
        ('40', '*', '*'): {'All': 'HS'},
        ('24', '*', '20'): {'All': 'IR'},
        ('26', '*', '20'): {'All': 'IR'},
        ('50', '*', '*'): {'All': 'IR'},
        ('24', '*', '10'): {'All': 'LU'},
        ('26', '*', '10'): {'All': 'LU'},
        ('30', '*', '10'): {'All': 'LU'},
        ('30', '*', '00'): {'All': 'LU'}, # TODO: fake-entry lagt inn fordi tabellen ikke er komplett...
        ('55', '*', '*'): {'All': 'IT'},
        ('70', '*', '35'): {'All': 'SC'},
        ('60', '*', '*'): {'All': 'SF'},
        ('90', '*', '*'): {'All': 'SF'},
        }

    def _findBestMatch(self, sko, mapping):
        """Returner en entry der sko matcher en nøkkel i mappingen.
        Dersom flere entries matcher, returneres den som har flest
        match på en eksplisitt verdi.

        Gitt sko=123456 er ('12','34','*') en bedre match enn ('12','*','*').
        """

        key = (sko[0:2], sko[2:4], sko[4:6])
        best_match_score = -1
        best_match = None
        for k, v in mapping.items():
            matches = True
            match_score = 0
            for n in range(3):
                if(not (k[n] == key[n] or k[n] == '*')):
                    matches = False
                    break
                if k[n] == key[n]:
                    match_score += 1
            if matches and match_score > best_match_score:
                best_match_score = match_score
                best_match = v
        if best_match == None:
            raise MappingError("No map-match for sko='%s'" % sko)
        return best_match

    def _getSted(self, sko):
        return self._findBestMatch(sko, Fag.sted_mapping)
    
    def _getAvdeling(self, sko):
        return self._findBestMatch(sko, Fag.avdeling_mapping)
    
    def getDN(self, sko, uname):
        tmp = self._getAvdeling(sko)
        avdeling = tmp.get('Canon', tmp['All'])
        sted = self._getSted(sko)
        return "CN=%s,OU=%s,OU=%s,OU=Ansatte,%s" % (uname, avdeling, sted, Fag.DOMAIN_DN)

    def getProfilePath(self, sko, uname):
        tmp = self._getAvdeling(sko)
        avdeling = tmp.get('Profile', tmp['All'])
        return r"\\%s\Profile\%s\%s" % (Fag.DOMAIN_NAME, avdeling, uname)

    def getHome(self, sko, uname):
        tmp = self._getAvdeling(sko)
        avdeling = tmp.get('Profile', tmp['All'])
        return r"\\%s\Home\%s\%s" % (Fag.DOMAIN_NAME, avdeling, uname)

class Student(Fag):
    DOMAIN_NAME = "stud.hiof.no"
    DOMAIN_DN = "DC=stud,DC=hiof,DC=no"
    def getDN(self, sko, studieprogram, uname):
        tmp = self._getAvdeling(sko)
        avdeling = tmp.get('Profile', tmp['All'])
        return "CN=%s,OU=%s,OU=%s,OU=Studenter,%s" % (uname, studieprogram, avdeling, Student.DOMAIN_DN)

    def getProfilePath(self, sko, uname):
        tmp = self._getAvdeling(sko)
        avdeling = tmp.get('Profile', tmp['All'])
        return r"\\%s\Profile\%s\%s" % (Student.DOMAIN_NAME, avdeling, uname)

    def getHome(self, sko, uname):
        tmp = self._getAvdeling(sko)
        avdeling = tmp.get('Profile', tmp['All'])
        return r"\\%s\Home\%s\%s" % (Student.DOMAIN_NAME, avdeling, uname)

class MappingTests(unittest.TestCase, object):
    def testFag(self):
        fag = Fag()
        self.assertEqual(fag.getDN("260020", "uname"),
                         'CN=uname,CN=IR,CN=Sarp,CN=Ansatte,DC=fag,DC=hiof,DC=no')
        self.assertEqual(fag.getProfilePath("260020", "uname"),
                         r'\\fag.hiof.no\Profile\IR\uname')
        self.assertEqual(fag.getHome("260020", "uname"),
                         r'\\fag.hiof.no\Home\IR\uname')

    def testStudent(self):
        s = Student()
        self.assertEqual(s.getDN("260020", "stprog", "uname"),
                         'CN=uname,OU=stprog,OU=IR,OU=Studenter,DC=stud,DC=hiof,DC=no')
        self.assertEqual(s.getProfilePath("260020", "uname"),
                         r'\\stud.hiof.no\Profile\IR\uname')
        self.assertEqual(s.getHome("260020", "uname"),
                         r'\\stud.hiof.no\Home\IR\uname')

    def testAdm(self):
        adm = Adm()
        self.assertEqual(adm.getDN("983020", "uname"),
                         'CN=uname,CN=Ansatte Tora,DC=adm,DC=hiof,DC=no')
        self.assertEqual(adm.getProfilePath("983020", "uname"),
                         r'\\tora\uname\profile')
        self.assertEqual(adm.getHome("983020", "uname"),
                         r'\\tora\uname')

if __name__ == '__main__':
    unittest.main()
