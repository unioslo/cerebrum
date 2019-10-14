==============================
Automated tests for Cerebrum
==============================

This is a README explaining how Cerebrum's test functionality works.

Dependencies
============


File structure
===============

testsuite/tests
---------------
Contains groups of tests. E.g. test_Cerebrum, which are tests for the core
functionality of Cerebrum.


testsuite/testtools
-------------------
Contains reuseable test code. This includes common code for setting up tests and
cleaning up after tests.


testsuite/scripts
-----------------
Common helper scripts. This includes the generic cerebrum setup.


testsuite/configs
-----------------
Contains a folder for each test setup. The folder should always contain the
following files:

* ``run.sh``

  The main test script. This script should call the neccessary setup scripts and
  run the tests.

* cereconf.py.in

  Template cereconf.py file. The string ``@test_base@`` is replaced by
  ``/path/to/virtenv`` by the setup function. Other text replacements can be
  configured as well

* ``logging.ini.in``

  Template logging.ini file.

* ``extras.txt``

  This file contains a list of "mod_*.sql" files to supply as extra-file
  arguments to ``makedb.py``. Each of the files must exist in the
  "cerebrum/design/" directory.

* ``pip.txt``

  A ``pip`` requirements file. Each line contains a PIP package to install and
  version requirement for that package. In essence, this is the format that
  ``pip freeze`` produces. See
  `<http://www.pip-installer.org/en/latest/cookbook.html>`_ for more info on
  requirement files.

  Note that this file should include any test packages used by the tests. It
  should always contain:

   * ``coverage>=3.7.1``
   * ``nose>=1.3.0``
   * ``nosexcover>=1.0.8``
   * ``unittest2>=0.5.1``

  In addition, Cerebrum depends on at least:

   * ``egenix-mx-base``
   * ``psycopg2``
   * ``passlib``


In addition, the config folder for the job should also contain other config
files, e.g. config files for the test tools.


Unit tests
============

TODO

Setup
=====

TODO: Move this to its own file?

If you want to setup the test environment for yourself, you need to:

- Install some dependencies:

    - Cerebrum's own dependencies, see the README file in the top directory

    - python-virtualenv

    - python-pip

    - postgres-server

- Setup postgres-server:

  - Give local access in `pg_hba.conf`.

  - Create a user mapping in `pg_ident.conf`.

  - Create a ceretest user in postgres' db::

        # su postgres
        $ createuser -d ceretest

  - Reload postgres-server::

        sudo service postgresql reload

- TODO: more setup

postgres
--------

Some tips for the postresql setup:

- On RHEL, the file `/var/lib/pgsql/data/pg_hba.conf` contains settings for how
  to get access to postgres. Here you would probably like to have the line::

    local   all         all                               ident map=usermap

  which gives local access.

- On RHEL, the file `/var/lib/pgsql/data/pg_ident.conf` contains a user name
  mapping for granting access to postgres. You would probably like::

    usermap  ceretest  ceretest
    usermap  YOURUSERNAME  ceretest

  to give you and the test user direct access to local test databases.

When doing changes, don't forget to run::

    sudo service postgresql restart

