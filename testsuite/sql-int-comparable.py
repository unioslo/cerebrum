#!/usr/bin/env python2.2

from Cerebrum import Database;

def main():
    db = Database.connect()
    try:
        db.execute("CREATE TABLE test_db_dict (value NUMERIC(6,0))")
        db.execute("INSERT INTO test_db_dict (value) VALUES (1)")
        value = db.query_1("SELECT max(value) FROM test_db_dict")

        try:
            print "Checking if comparing SQL integer to int works:",
            if value == 1:
                print "ok"
        except:
            print "failed"

        try:
            print "Checking if comparing int to SQL integer works:",
            if 1 == value:
                print "ok"
        except:
            print "failed"
    except:
        print "error in test"
    db.execute("DROP TABLE test_db_dict");

if __name__ == '__main__':
    main()
