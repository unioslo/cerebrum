================================
Cerebrum installation procedure
================================

.. contents:: Contents
.. section-numbering::


Short version
================
Using and installing Cerebrum can be a bit daunting, and instructions will vary
a lot depending on which modules and functionality you want.

This document gives a broad idea of what's involved for a very simple
installation.  For more complex features, please refer to the documentation
given by the various modules.

In short steps, a from-the-ground installation involves:

* running ``python setup.py install [...]``
* editing the installed ``cereconf.py`` file
* running ``python makedb.py [...]``

The rest of this document contains a more explanatory installation
guide.


Installation procedure
========================
Cerebrum installation procedure consist of several steps:

* Preliminary tasks
* Installing the Python code
* Tailoring the system to your needs
* Bootstrapping your database
* Testing the distribution (optional)

As some of these tasks are fairly complex they are described in
separate subsections.


Preliminary tasks
-------------------
You will need to create a database instance on your system where
Cerebrum should be run. Furthermore, you will need to create a user
which cerebrum will connect to the database as. If you are using a
PostgreSQL database system the following commands might (depending on
your PostgreSQL configuration) do the trick:
::

  createuser cerebrum
  createdb -E unicode cerebrum


Installing the Python code
---------------------------
Execute the command:
::

  python setup.py install [options]

All files will by default be installed under ``sys.prefix``.  You can
change this installation prefix by using a virtualenv (reccommended).

There are a few other options you can set by using ``setup.py``. To
get the full list of options enter:
::

  python setup.py --help


Tailoring the system to your needs
-------------------------------------
You now need to edit the file ``cereconf.py``.  ``cereconf.py``
inherits all its settings from ``Cerebrum/default_config.py`` and
basically defines a set of options. Since the file actually is a
python script it may do other things as well (if you tell it to). You
may set quite a few options in the ``cereconf.py``. For a full list of
options that can be modified check ``Cerebrum/default_config.py``.

In order to make testing procedures work you should add something
like:
::

    CEREBRUM_DATABASE_CONNECT_DATA['user'] = "cerebrum"
    CLASS_DB_DRIVER = ("Cerebrum.database.postgres/PsycoPG2",)
    CEREBRUM_DATABASE_NAME = "cerebrum"
    DB_AUTH_DIR = "/etc/cerebrum"
    CLASS_CONSTANTS = (
        "Cerebrum.modules.no.uio.Constants/Constants",
        "Cerebrum.modules.no.Constants/Constants",
        "Cerebrum.modules.PosixUser/Constants",
        "Cerebrum.modules.CLConstants/CLConstants",
    )
    CLASS_OU = ("Cerebrum.modules.no.Stedkode/Stedkode",)

to ``cereconf.py``

Cerebrum also expects to find an authentication file for the database
user named"
::

    <DB_AUTH_DIR>/passwd-<username>@<DATABASE_NAME>

which contains the users database password. the format of the
authentication file should be"
::

  username<tab>password

For the configuration example above a file named
``passwd-cerebrum@cerebrum``, containing the line:
::

    cerebrum	somepassword

should be placed in the directory specified in ``cereconf.DB_AUTH_DIR``


Bootstrapping your database
----------------------------
You are now ready to bootstrap the database. This is done by running
the ``makedb.py`` script with appropriate parameters.

First, you'll need to find out which database components you want. The
various components are to be found in the files matching
``design/*.sql``. Pick the ones you want, and be sure to at least
include the components that corresponds to the classes in your
``cereconf.CLASS_*`` variables.

If you want just the basic Cerebrum core (even though this really
isn't very useful by itself), give the simple command:
::

    makedb.py

To create both the Cerebrum core components and the components found
in ``design/mod_stedkode.sql``, the following command should be
enough:
::

  makedb.py --extra-file=design/mod_stedkode.sql

The ``--extra-file`` argument can be repeated, if you want to install
more than one optional module:
::

  makedb.py \
    --extra-file=design/mod_stedkode.sql \
    --extra-file=mod_posix_user.sql


Upgrading a Cerebrum installation
======================================
Due to the fact that each installation of Cerebrum may differ
considerably from the original Cerebrum distribution upgrading Cerebrum
is a complicated affair. Some general rules to upgrading will apply:

* Backup your data
* If you are installing in the same place as the old version move the
  old installation out of the way

There are, at the present time, no automatic mechanisms for Cerebrum
upgrading. Any upgrade will have to be done as a from-the-scratch
installation. Also note that the flexibility and extensibility
features of Cerebrum is in fact paramount to producing a fully general
and complete automatic upgrade procedure. The main reason for this is
the intended use of Cerebrum - any installation may and should be
customized in order to accommodate local needs.

It is in fact expected of the Cerebrum users to customize their
installation.
