#!/usr/bin/env python2.2

import unittest

from Cerebrum.Utils import Factory

class SQLDriverTestCase(unittest.TestCase):
    def setUp(self):
        self.db = Factory.get('Database')()
        try:
            self.db.execute("CREATE TABLE test_db_dict (value NUMERIC(6,0))")
            self.db.execute("INSERT INTO test_db_dict (value) VALUES (1)")
        except:
            pass

        try:
            self.db.execute("CREATE TABLE test_db_utf8 (value CHAR VARYING(128))")
        except:
            pass

        # Calling commit() to make sure it is possible to continue
        # testing even if the SQL call fails.
        self.db.commit()

    def testSQLIntHashable(self):
        "Check if SQL NUMERIC is hashable"
        # This test fails with Debian package python2.2-pgsql version
        # 2.2-1, but works with version 2.0-3.1
        value = self.db.query_1("SELECT max(value) FROM test_db_dict")
        hash = {}
        hash[value] = 1 # This one fails
        assert(1 == hash[value], 'Unable to compare Integer to SQL NUMERIC')

    def testUTF8TextParam(self):
        "Check if CHAR VARYING() can store Unicode/UTF8 text"
        self.db.execute("INSERT INTO test_db_utf8 (value) VALUES (:text)",
                        {'text': u"unicodeTest"})
        self.db.commit()

    def testUTF8TextStatement(self):
        "Check if SQL driver accept Unicode/UTF8 statements"
        self.db.execute(u"INSERT INTO test_db_utf8 (value) VALUES ('foobar')")
        self.db.commit()

    def testBrokenDateBefore1901(self):
        "Check if the Date class handle dates before 1901 (1900-01-01)"
        date = self.db.Date(1900, 1, 1)
        date = None

    def testBrokenDateBefore1970(self):
        "Check if the Date class handle dates before 1970 (1969-01-01)"
        date = self.db.Date(1969, 1, 1)
        date = None

    def testRepeatedParam(self):
        "Check driver support for repeated bind params"
        self.db.query("""
        SELECT value
        FROM test_db_dict
        WHERE value = :key1 AND
              value = :key1 AND
              value = :key2""", {'key1': 100, 'key2': 200})

    def tearDown(self):
        try:
            self.db.execute("DROP TABLE test_db_utf8")
        except:
            pass
        try:
            self.db.execute("DROP TABLE test_db_dict");
        except:
            pass
        self.db.commit()
        self.db.close()

    def suite():
        suite = unittest.TestSuite()
        suite.addTest(SQLDriverTestCase("testSQLIntHashable"))
        suite.addTest(SQLDriverTestCase("testBrokenDateBefore1901"))
        suite.addTest(SQLDriverTestCase("testBrokenDateBefore1970"))
        suite.addTest(SQLDriverTestCase("testUTF8TextParam"))
        suite.addTest(SQLDriverTestCase("testUTF8TextStatement"))
        suite.addTest(SQLDriverTestCase("testRepeatedParam"))
        return suite
    suite=staticmethod(suite)

def suite():
    return SQLDriverTestCase.suite()

if __name__ == "__main__":
    unittest.main()
