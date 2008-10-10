#!/usr/bin/env python
# -*- encoding: utf-8 -*-

"""Check that basic operations against a db works"""

def test_create_db_connection():
    """Make sure that we can actually establish a conn to the db."""

    import cerebrum_path, cereconf
    from Cerebrum.Utils import Factory

    print "\nDB: %s" % cereconf.CEREBRUM_DATABASE_NAME
    db = Factory.get("Database")()
    db.ping()
# end test_create_db_connection

def test_read_from_db():
    """Make sure that we can actually read from db."""

    import cerebrum_path, cereconf
    from Cerebrum.Utils import Factory

    db = Factory.get("Database")()
    ac = Factory.get("Account")(db)
    ac.clear()
    ac.find(8744)
    print "Account %s, expire_date: %s" % (ac.account_name, ac.expire_date)

def test_write_to_db():
    """Make sure that we can even write to db."""

    import cerebrum_path, cereconf
    from Cerebrum.Utils import Factory
    from mx import DateTime
    import random

    print "Try writing to db"
    db = Factory.get("Database")()
    db.cl_init(change_program="test_write")
    ac = Factory.get("Account")(db)
    
    today = DateTime.today()
    start_date = today - 365
    new_date = today - 1
    x = ac.search(expire_start=start_date, expire_stop=today)
    tmp = random.choice(x)
    ac.clear()
    ac.find(tmp['account_id'])
    print "Account %s, expire_date: %s" % (ac.account_name, ac.expire_date)
    ac.expire_date = new_date
    ac.write_db()
    db.commit()
    print "New expire_date fo account %s is %s" % (ac.account_name, new_date.date)

if __name__ == '__main__':
    test_create_db_connection()
    test_read_from_db()
    test_write_to_db()
