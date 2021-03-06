Installation of Cerebrum
========================

1. Prerequisities
2. Get the sources
3. testing the distribution
4. Installing the software
5. Post installation steps
6. Links

Prerequisities
--------------

Install python >= 2.2.1, and a PostgreSQL or Oracle database.  Install
pyPgSQL >= 2.2 or DCOracle2.

* Debian packages: python2.2 python2.2-dev python2.2-xmlbase postgresql python2.2-pgsql
* RedHat packages: ???

Create a database instance where cerebrum should be ran, as well as a
user which cerebrum should connect as.

Instructions for creating the Oracle users:

~~~ sql
CREATE USER cerebrum IDENTIFIED BY somepassword;
GRANT connect, resource, create role TO cerebrum;
CREATE USER cerebrum_user identified BY somepassword;
GRANT connect, resource TO cerebrum_user;
~~~

Instructions for creating the PostgreSQL database and user:

    createuser cerebrum
    createdb -E unicode cerebrum

Make sure that the database user 'cerebrum' has proper access to the
new database.

Get the sources
---------------

    git clone https://utv.uio.no/stash/scm/crb/cerebrum.git


Testing the distribution
------------------------

Set PYTHONPATH to point to the directory where you extracted the
sources.  Edit cereconf.py and set DB_AUTH_DIR,
CEREBRUM_DATABASE_CONNECT_DATA['user'], CEREBRUM_DATABASE_NAME and
CLASS_DBDRIVER.

Warning: the target datbases cerebrum tables will be dropped and
recreated when running this script!

Run `make fullcheck`.

If any of the tests fail on your system, you chould investigate the
error before proceeding with the installation.


Installing the software
-----------------------

Enter the directory where you installed the sources, and run:

~~~ bash
./configure --prefix=/cerebrum
make
make install
~~~

This will install the Cerebrum python modules into your site-packages
directory.  A number of other files are placed as documented in the
top of setup.py.  To install to an alternative location, use the
--prefix option to install.  If you use --prefix, remember to set
PYTHONPATH when running scripts.

Run `make bootstrap` to create the required tables.


Post installation steps
-----------------------

* cronjobs
* auto starting bofhd
* ?


Links
-----

* [pyPgSQL](http://sourceforge.net/projects/pypgsql/)

