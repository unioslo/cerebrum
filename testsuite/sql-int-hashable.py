#!/usr/bin/env python2.2

from Cerebrum import Database;

def main():
    db = Database.connect()
    print "Checking if SQL integers are usable as dictionary keys (hashable):",
    try:
        db.execute("CREATE TABLE test_db_dict (value NUMERIC(6,0))")
        db.execute("INSERT INTO test_db_dict (value) VALUES (1)")
        value = db.query_1("SELECT max(value) FROM test_db_dict")
        hash = {}
        # A broken SQL implementation throws 'TypeError: unhashable
        # instance' here
        hash[value] = 1
        print "ok"
    except:
        print "failed"
    db.execute("DROP TABLE test_db_dict");

if __name__ == '__main__':
    main()
