# Uncomment whichever suits you 
#
# setup = "DCOracle2"
# setup = "cx_Oracle"
# setup = "psycopg"
# setup = "psycopg2"
# setup = "SQLite"


########################################################################
# Oracle backends setup (DCOracle2, cx_Oracle)
########################################################################
if setup in ("DCOracle2", "cx_Oracle"):
    DB_AUTH_DIR = "<directory is mandatory>"
    CEREBRUM_DATABASE_NAME = "<database name is mandatory>"
    CEREBRUM_DATABASE_CONNECT_DATA = {"user": "<uname is mandatory>"}


########################################################################
# Postgres backends setup (psycopg, psycopg2)
########################################################################
elif setup in ("psycopg", "psycopg2"):
    DB_AUTH_DIR = "<directory is mandatory>"
    CEREBRUM_DATABASE_NAME = "<database name is mandatory>"
    CEREBRUM_DATABASE_CONNECT_DATA = {"user": "<uname is mandatory>",
                                      "host": "<host is mandatory>",}
 

########################################################################
# SQLite backends setup (pysqlite2)
########################################################################
elif setup in ("SQLite",):
    CEREBRUM_DATABASE_NAME=":memory:"

else:
    import sys
    sys.exit("Unknown db-backend specified: %s" % setup)
