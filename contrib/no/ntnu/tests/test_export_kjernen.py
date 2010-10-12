# -*- encoding: UTF-8 -*-
from contrib.no.ntnu.export_kjernen import Export2Kjernen
import unittest

class ExportKjernenTests(unittest.TestCase):
    """ Tests for export_kjernen.py using monkey patching.
    Would be nicer to use mocking instead, but that's taking too long
    to implement.
    """
    def setUp(self):
        self.export_kjernen = Export2Kjernen(
            "output.txt", True, True)
        self.personid = 1234
        
        self.export_kjernen.get_birthdates = \
            lambda: {self.personid: "1950.01.01"}
        
        self.export_kjernen.get_nins = \
            lambda: {self.personid: "01015012345"}
        
        self.export_kjernen.get_emails = \
            lambda: {self.personid: "testing@email.com"}
        
        self.export_kjernen.get_lastnames = \
            lambda: {self.personid: "Testulfsen"}
        
        self.export_kjernen.get_firstnames = \
            lambda: {self.personid: "Testulf"}
        
        self.export_kjernen.get_entities = lambda:None
        self.export_kjernen.get_traits = lambda:None
        self.export_kjernen.get_accounts = \
            lambda: {self.personid: "testulfsen"}
        
        self.export_kjernen.get_stedkoder = \
            lambda: {51168: "194672500", 316590: "194999901"}
            
    def run_test(self, exp_lines, affiliations):
        self.export_kjernen.get_affiliations = \
            lambda: {self.personid: affiliations}
        self.export_kjernen.export_persons()
        res = open("output.txt").readlines()
        
        self.assertEqual(len(exp_lines), len(res))
        for i, line in enumerate(res):
            self.assertEqual(exp_lines[i], line)
    
    def test_guest_and_guest(self):
        """ Given guest and guest. Expect both exported. """
        
        affiliations = [('tilknyttet', 51168, 'gjest', '2008.05.09'),
                        ('tilknyttet', 316590, 'gjest', '2010.08.10')]
        
        exp_res = ["1234;010150;12345;1950.01.01;Testulf;Testulfsen;testing@email.com;tilknyttet;gjest;194672500;testulfsen;2008.05.09;\n",
                   "1234;010150;12345;1950.01.01;Testulf;Testulfsen;testing@email.com;tilknyttet;gjest;194999901;testulfsen;2010.08.10;\n"]
        
        self.run_test(exp_res, affiliations)

    def test_guest_and_alumni(self):
        """ Should export 'gjest' affiliation """
        
        affiliations = [('tilknyttet', 51168, 'gjest', '2008.05.09'),
                        ('alumni', 316590, 'aktiv', '2010.08.10')]
        
        exp_res = ["1234;010150;12345;1950.01.01;Testulf;Testulfsen;testing@email.com;tilknyttet;gjest;194672500;testulfsen;2008.05.09;\n"]
        
        self.run_test(exp_res, affiliations)
    
    def test_student_and_alumni(self):
        """ Should export 'student' affiliation, and ignore 'alumni' """
        
        affiliations = [('student', 51168, 'student', '2009.08.20'),
                        ('alumni', 316590, 'aktiv', '2010.08.10')]
        
        exp_res = ["1234;010150;12345;1950.01.01;Testulf;Testulfsen;testing@email.com;student;student;194672500;testulfsen;2009.08.20;\n"]
        
        self.run_test(exp_res, affiliations)
            
            
    def test_only_alumni(self):
        """ Should export nothing """
        affiliations = [('alumni', 316590, 'aktiv', '2010.08.10')]
        exp_res = []
        
        self.run_test([], affiliations)
    
    def test_only_student(self):
        
        affiliations = [('student', 51168, 'student', '2009.08.20')]
        
        exp_res = ["1234;010150;12345;1950.01.01;Testulf;Testulfsen;testing@email.com;student;student;194672500;testulfsen;2009.08.20;\n"]
        
        self.run_test(exp_res, affiliations)
    
    def test_only_ansatt(self):
        affiliations = [('ansatt', 51168, 'ansatt', '2009.08.20')]
        
        exp_res = ["1234;010150;12345;1950.01.01;Testulf;Testulfsen;testing@email.com;ansatt;ansatt;194672500;testulfsen;2009.08.20;\n"]
        
        self.run_test(exp_res, affiliations)
    
    
    def test_ansatt_and_student(self):
        """ Should export only one of them """
        #hipp som happ hvem av dem jeg exporterer
        affiliations = [('ansatt', 51168, 'ansatt', '2009.08.20'),
                        ('student', 51168, 'student', '2009.08.20')]
        
        exp_res = ["1234;010150;12345;1950.01.01;Testulf;Testulfsen;testing@email.com;ansatt;ansatt;194672500;testulfsen;2009.08.20;\n"]
        
        self.run_test(exp_res, affiliations)

    def test_ansatt_og_gjest_likt_sted(self):
        #hipp som happ hvem av dem jeg exporterer
        
        affiliations = [('tilknyttet', 51168, 'gjest', '2009.08.20'),
                        ('ansatt', 51168, 'ansatt', '2009.08.20')]
        
        exp_res = ["1234;010150;12345;1950.01.01;Testulf;Testulfsen;testing@email.com;tilknyttet;gjest;194672500;testulfsen;2009.08.20;\n"]
        
        self.run_test(exp_res, affiliations)
        
        

    def test_ansatt_og_gjest_ulikt_sted(self):
        affiliations = [('tilknyttet', 51168, 'gjest', '2009.08.20'),
                        ('ansatt', 316590, 'ansatt', '2009.08.20')]
        
        exp_res = ["1234;010150;12345;1950.01.01;Testulf;Testulfsen;testing@email.com;tilknyttet;gjest;194672500;testulfsen;2009.08.20;\n"]
        
        self.run_test(exp_res, affiliations)
    
    def test_gjest_og_gjest_og_annet_snacks(self):
        affiliations = [('alumni', 316590, 'aktiv', '2010.08.10'),
                        ('tilknyttet', 51168, 'gjest', '2009.08.20'),
                        ('ansatt', 316590, 'ansatt', '2009.08.20'),
                        ('student', 51168, 'student', '2009.08.20')]
        
        exp_res = ["1234;010150;12345;1950.01.01;Testulf;Testulfsen;testing@email.com;tilknyttet;gjest;194672500;testulfsen;2009.08.20;\n"]
        
        self.run_test(exp_res, affiliations)
        
        
if __name__ == '__main__':
    unittest.main()