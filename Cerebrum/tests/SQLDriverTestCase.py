#!/usr/bin/env python2.2

import unittest

from Cerebrum import Database

class SQLDriverTestCase(unittest.TestCase):
    def setUp(self):
        self.db = Database.connect()
        self.db.execute("CREATE TABLE test_db_dict (value NUMERIC(6,0))")
        self.db.execute("INSERT INTO test_db_dict (value) VALUES (1)")
        
    def testSQLIntComparable1(self):
        "Check if SQL Integer is comparable to Python Integer"
        value = self.db.query_1("SELECT max(value) FROM test_db_dict")
        assert(value == 1, 'Unable to compare SQL Integer to Integer')

    def testSQLIntComparable2(self):
        "Check if Python Integer is comparable to SQL Integer"
        value = self.db.query_1("SELECT max(value) FROM test_db_dict")
        assert(1 == value, 'Unable to compare Integer to SQL Integer')

    def testSQLIntHashable(self):
        "Check if SQL Integer is hashable"
        value = self.db.query_1("SELECT max(value) FROM test_db_dict")
        hash = {}
        hash[value] = 1
        assert(1 == hash[value], 'Unable to compare Integer to SQL Integer')

    def testBrokenDateBefore1901(self):
        "Check if the Date class handle dates before 1901 (1900-01-01)"
        date = self.db.Date(1900, 1, 1)
        date = None

    def testBrokenDateBefore1970(self):
        "Check if the Date class handle dates before 1970 (1969-01-01)"
        date = self.db.Date(1969, 1, 1)
        date = None

    def tearDown(self):
        self.db.execute("DROP TABLE test_db_dict");
        self.db.close()

    def suite():
        suite = unittest.TestSuite()
        suite.addTest(SQLDriverTestCase("testSQLIntComparable1"))
        suite.addTest(SQLDriverTestCase("testSQLIntComparable2"))
        suite.addTest(SQLDriverTestCase("testSQLIntHashable"))
        suite.addTest(SQLDriverTestCase("testBrokenDateBefore1901"))
        suite.addTest(SQLDriverTestCase("testBrokenDateBefore1970"))
        return suite
    suite=staticmethod(suite)

def suite():
    return SQLDriverTestCase.suite()

if __name__ == "__main__":
    unittest.main()
