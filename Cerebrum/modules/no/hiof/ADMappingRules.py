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


class MappingError(Exception):
    pass


class Adm(object):
    DOMAIN_NAME = "adm.hiof.no"
    DOMAIN_DN = ""
    sted_mapping = {
        '00': 'olivia',
        '10': 'olivia',
        '20': 'katta',   # tidligere tana, enda tidligere tora
        '30': 'katta',
        '35': 'katta'
        }
    # Server for non personal accounts
    non_personal_serv = 'olivia'

    def getDN(self, uname, sko):
        serv = Adm.sted_mapping[sko[-2:]]
        return "CN=%s,OU=Ansatte %s%s" % (uname, serv.capitalize(), Adm.DOMAIN_DN)

    def getProfilePath(self, uname, sko=None):
        if sko:
            serv = Adm.sted_mapping[sko[-2:]]
        else:
            serv = Adm.non_personal_serv
        return r"\\%s\home\%s\profile" % (serv, uname)

    def getHome(self, uname, sko=None):
        if sko:
            serv = Adm.sted_mapping[sko[-2:]]
        else:
            serv = Adm.non_personal_serv
        return r"\\%s\home\%s" % (serv, uname)


class Fag(object):
    DOMAIN_NAME = "fag.hiof.no"
    DOMAIN_DN = ""
    non_personal_avdeling = 'LU'
    sted_mapping = {
        ('*', '*', '00'): 'Halden',
        ('*', '*', '10'): 'Halden',
        ('*', '*', '20'): 'Sarp',
        ('*', '*', '30'): 'Fredr',
        ('*', '*', '35'): 'Fredr',
        ('*', '*', '40'): 'Fredr',
        ('98', '10', '*'): 'Halden'
        }
    avdeling_mapping = {
        # New: very special employees at Fellestjeneste :-)
        ('00', '*', '00'): {'All': 'LU'},
        ('00', '*', '10'): {'All': 'LU'},
        ('00', '*', '20'): {'All': 'IR'},
        ('00', '*', '30'): {'All': 'HS'},
        # New: very special employees at Fellestjeneste :-)
        ('20', '*', '00'): {'All': 'FT'},
        ('20', '*', '10'): {'All': 'LU'},
        ('20', '*', '20'): {'All': 'IR'},
        ('20', '*', '30'): {'All': 'HS'},
        ('22', '*', '00'): {'All': 'IT'},
        ('22', '*', '10'): {'All': 'IT'},
        ('22', '*', '20'): {'All': 'IR'},
        ('22', '*', '30'): {'All': 'HS'},
        ('24', '*', '10'): {'All': 'LU'},
        ('24', '*', '20'): {'All': 'IR'},
        ('24', '*', '30'): {'All': 'HS'},
        ('26', '*', '10'): {'All': 'LU'},
        ('26', '*', '20'): {'All': 'IR'},
        ('26', '*', '30'): {'All': 'HS'},
        ('26', '*', '35'): {'All': 'HS'},
        ('29', '99', '10'): {'All': 'LU',
                             'Profile': None} 
        ('30', '*', '00'): {'All': 'LU'},
        ('30', '*', '10'): {'All': 'LU'},
        ('30', '*', '20'): {'All': 'IR'},        
        ('40', '*', '*'): {'All': 'HS'},
        ('50', '*', '*'): {'All': 'IR'},
        ('55', '*', '*'): {'All': 'IT'},
        ('60', '*', '*'): {'All': 'SF'},
        ('70', '*', '*'): {'All': 'SCE'},
        ('80', '*', '*'): {'All': 'SKUT'},
        ('90', '*', '*'): {'All': 'SF'},
        ('98', '00', '10'): {'All': 'LU'},
        ('98', '00', '20'): {'All': 'IR'},
        ('98', '00', '30'): {'All': 'HS'},
        ('98', '00', '35'): {'All': 'SCE'},
        ('98', '10', '*'): {'All': 'SIO'},
        ('98', '15', '20'): {'All': 'IR'},
        ('98', '20', '10'): {'All': 'LU'},
        ('98', '20', '20'): {'All': 'IR'},
        ('98', '20', '30'): {'All': 'HS'}
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
    
    def getDN(self, uname, sko):
        tmp = self._getAvdeling(sko)
        avdeling = tmp.get('Canon', tmp['All'])
        sted = self._getSted(sko)
        return "CN=%s,OU=%s,OU=%s,OU=Ansatte%s" % (uname, avdeling, sted, Fag.DOMAIN_DN)

    def getProfilePath(self, uname, sko=None):
        avdeling = Fag.non_personal_avdeling
        if sko:
            tmp = self._getAvdeling(sko)
            avdeling = tmp.get('Profile', tmp['All'])
        # Some sko implies no profile path
        if avdeling is None:
            return ""  # Must return empty string, not None
        else:
            return r"\\%s\Profile\%s\%s" % (Fag.DOMAIN_NAME, avdeling, uname)

    def getHome(self, uname, sko=None):
        avdeling = Fag.non_personal_avdeling
        if sko:
            tmp = self._getAvdeling(sko)
            avdeling = tmp.get('Home', tmp['All'])
        return r"\\%s\Home\%s\%s" % (Fag.DOMAIN_NAME, avdeling, uname)


class Student(Fag):
    DOMAIN_NAME = "stud.hiof.no"
    DOMAIN_DN = ""
    non_personal_avdeling = 'LU'    

    def getDN(self, uname, sko, studieprogram):
        tmp = self._getAvdeling(sko)
        avdeling = tmp.get('Profile', tmp['All'])
        return "CN=%s,OU=%s,OU=%s,OU=Studenter%s" % (uname, studieprogram, avdeling, Student.DOMAIN_DN)

    def getProfilePath(self, uname, sko=None):
        avdeling = Student.non_personal_avdeling
        if sko:
            tmp = self._getAvdeling(sko)
            avdeling = tmp.get('Profile', tmp['All'])
        return r"\\%s\Profile\%s\%s" % (Student.DOMAIN_NAME, avdeling, uname)

    def getHome(self, uname, sko=None):
        avdeling = Student.non_personal_avdeling
        if sko:
            tmp = self._getAvdeling(sko)
            avdeling = tmp.get('Profile', tmp['All'])
        return r"\\%s\Home\%s\%s" % (Student.DOMAIN_NAME, avdeling, uname)

class MappingTests(unittest.TestCase, object):
    def testFag(self):
        fag = Fag()
        self.assertEqual(fag.getDN("uname", "260020"),
                         'CN=uname,CN=IR,CN=Sarp,CN=Ansatte,DC=fag,DC=hiof,DC=no')
        self.assertEqual(fag.getProfilePath("uname", "260020"),
                         r'\\fag.hiof.no\Profile\IR\uname')
        self.assertEqual(fag.getHome("uname", "260020"),
                         r'\\fag.hiof.no\Home\IR\uname')

    def testStudent(self):
        s = Student()
        self.assertEqual(s.getDN("uname", "stprog", "260020"),
                         'CN=uname,OU=stprog,OU=IR,OU=Studenter,DC=stud,DC=hiof,DC=no')
        self.assertEqual(s.getProfilePath("uname", "260020"),
                         r'\\stud.hiof.no\Profile\IR\uname')
        self.assertEqual(s.getHome("uname", "260020"),
                         r'\\stud.hiof.no\Home\IR\uname')

    def testAdm(self):
        adm = Adm()
        self.assertEqual(adm.getDN("uname", "983020"),
                         'CN=uname,CN=Ansatte Tora,DC=adm,DC=hiof,DC=no')
        self.assertEqual(adm.getProfilePath("uname", "983020"),
                         r'\\tora\uname\profile')
        self.assertEqual(adm.getHome("uname", "983020"),
                         r'\\tora\uname')

if __name__ == '__main__':
    unittest.main()
