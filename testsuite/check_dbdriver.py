import sys
import getopt

def create_tables():
    csr.execute("""CREATE TABLE foo (id NUMERIC(2)
    CONSTRAINT foo_pk PRIMARY KEY)""")
    csr.execute("""CREATE TABLE ref_foo (id NUMERIC(2)
    CONSTRAINT ref_foo_fk REFERENCES foo(id))""")

def check_insert_too_big_rollback():
    csr.execute("INSERT INTO foo values(1)")
    try:
        csr.execute("INSERT INTO foo values(111)")
    except:  # Known to fail, unfortunately DB-API don't specify exception to catch
        pass
    ok = "FAIL"
    try:
        csr.execute("SELECT id FROM foo WHERE id=1")
        for r in csr.fetchall():
            ok = "OK"
    except:
        pass
    print "check_insert_too_big_rollback: %s" % ok

def check_fk_failure_rollback():
    csr.execute("INSERT INTO foo values(2)")
    try:
        csr.execute("INSERT INTO ref_foo values(3)")
    except:  # Known to fail, unfortunately DB-API don't specify exception to catch
        pass
    ok = "FAIL"
    try:
        csr.execute("SELECT id FROM foo WHERE id=2")
        for r in csr.fetchall():
            ok = "OK"
    except:
        pass
    print "check_fk_failure_rollback: %s" % ok

def usage():
    print """Usage: $0 --connect-params arg --db-driver driver [--too-big-check | --fk-check]

    This script verifies if you database driver is broken in that it
    rollbacks transactions for you on an SQL error.  pyPgSQL.PgSQL is
    known to have this problem.
    
    Example: $0 --connect-params 'user="cerebrum", database="cerebrum"' --db-driver pyPgSQL.PgSQL --too-big-check
    Only one check may be ran pr try"""
    sys.exit(0)

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], '', ['db-driver=', 'too-big-check',
                                                      'fk-check', 'connect-params='])
        if len(opts) == 0:
            usage()
    except getopt.GetoptError:
        usage()
    global csr
    for opt, val in opts:
        if opt in ('--db-driver',):
            exec("import %s as db_api" % val)
            db = eval("db_api.connect(%s)" % connect_params)
            csr = db.cursor()
            create_tables()
        elif opt in ('--connect-params',):
            connect_params = val
        elif opt in ('--too-big-check',):
            check_insert_too_big_rollback()
        elif opt in ('--fk-check',):
            check_fk_failure_rollback()

if __name__ == '__main__':
    main()
