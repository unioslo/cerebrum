================================
Cerebrum installation procedure
================================

.. TODO: Dette er grov-porting av det gamle dokumentet til RST.  Må
   gjennomgås

This document describes installation of Cerebrum from a source code
distribution. It also describes the installation procedure when
installing Cerebrum from a CVS tree. Cerebrum can be downloaded from
the repository at `SourceForge.net
<http://cerebrum.sourceforge.net/>`_

Preliminary document, expected to change.

Short version
================

* python setup.py install ...

* Edit the installed ``cereconf.py`` file
* python makedb.py ...
* setup.py test -check

The rest of this document contains a more explanatory installation
guide.


Requirements and pre-requisites 
===================================

The recommended platform for current Cerebrum distribution is Linux,
as that is where most development has been done. RedHat 8.0, RedHat 9
and Debian sarge has been (lightly) tested, but any modern Unix should
in theory work.

You will also need a few software packages in order to build and
successfully install Cerebrum. These are:

* gzip/gunzip
* tar
* Python
* An relational database management system (PostgreSQL or Oracle)
* A Python database API (pyPgSQL or DCOracle2)
* OpenSSL
* M2Crypto, a Python interface to OpenSSL

Descriptions:

* gzip is a compression utility which produces files with the
  extension ``.gz`` which can be uncompressed by the ``gunzip``. More
  information about gzip is available from <http://www.gzip.org/>
* tar is an archiving tool for storing and extracting files from
  tarfiles. More information on tar is available from
  <http://www.gnu.org/software/tar/>.
* Python is an interpreted, interactive, extensible object-oriented
  programming language. You will need Python 2.2.1 or later in order to
  install Cerebrum. More information about Python is available from
  <http://www.python.org/>.
* PostgreSQL is an open-source object-relational database managment
  system. It is recommended to use version 7.2 or later. For more
  information about PostgreSQL see <http://www.postgresql.org>.
* Oracle is a common proprietary database management system. To be
  usable as a Cerebrum backend, Oracle 9i is needed. More informastion
  about Oracle is available from <http://www.oracle.com/>.
* OpenSSL is a cryptography toolkit implementing the Secure Sockets
  Layer and Transport Layer Security network protocols and related
  cryptography standards required by them. The software and the
  documentation made by the developers is available for download from
  <http://www.openssl.org/>.
* M2Crypto is a python interface to OpenSSL. For more information and
  download check <http://www.post1.com/home/ngps/m2/>.

Whether you will need to obtain pyPgSQL or DCOracle depends on the
choice of the database managment system.

* pyPgSQL provides an interface to PostgreSQL databases. More
  information is available from <http://pypgsql.sourceforge.net/>
  where you also can download the software package. You will need
  version 2.2 or later in order to install and run Cerebrum on
  PostgreSQL.
* DCOracle2is a python interface for Oracle available from
  <http://www.zope.org/Members/matt/dco2>. Running
  Cerebrum on Oracle requires DCOracle2.

Obtaining Cerebrum
===================

Cerebrum is open-source software released under GNU General Public
License. New releases will be made available from Cerebrum's
SourceForge pages. On these pages one can also find the instructions
on how to retrieve fresh, bleeding-edge development version from the
project's CVS repository. To get the latest release download the
tarfile Cerebrum-X.Y.Z.tar.gz from <http://cerebrum.sourceforge.net/>
and unpack the source code into an empty directory::

  gunzip Cerebrum-X.Y.Z.tar.gz
  tar xf Cerebrum-X.Y.Z.tar

This will create a directory Cerebrum-X.Y.Z under the current
directory with the Cerebrum sources. Change into that directory for
the rest of the installation procedure. If you prefer downloading the
CVS-version execute the following commands::

  cvs -d:pserver:anonymous@cvs.cerebrum.sourceforge.net:cvsrootcerebrum login
  cvs -z3 -d:pserver:anonymous@cvs.cerebrum.sourceforge.net:cvsrootcerebrum co cerebrum

You will probably be asked to provide a password during the first step
but it is not required - just press Enter to continue. A directory
``cerebrum/`` containing the CVS tree will be created. The additional
installation steps when installing from a CVS tree are described in
XXX


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
your PostgreSQL configuration) do the trick::

  createuser cerebrum
  createdb -E unicode cerebrum


If you are using Oracle you need to execute the following statements::

  CREATE USER cerebrum IDENTIFYED BY somepassword;
  GRANT connect, resource, create role TO cerebrum;
  CREATE USER cerebrum_user IDENTIFIED BY somepassword;
  GRANT connect, resource TO cerebrum_user;

Installing the Python code
---------------------------

Execute the command::

  python setup.py install [options]

All files will by default be installed under ``/usr/local/``. You can
change this installation prefix by supplying the following command
line options to ``python setup.py install``::

  --prefix=PREFIX

All the files will then be installed under the directory PREFIX
instead ``/usr/local``.  Note that no files will ever be installed
into the PREFIX directory, only in various subdirectories

There are a few other options you can set by using ``setup.py``. To
get the full list of options enter::

  python setup.py --help


Tailoring the system to your needs
-------------------------------------

You now need to edit the file ``cereconf.py``.  ``cereconf.py``
inherits all its settings from ``Cerebrum/default_config.py`` and
basically defines a set of options. Since the file actually is a
python script it may do other things as well (if you tell it to). You
may set quite a few options in the ``cereconf.py``. For a full list of
options that can be modified check ``Cerebrum/default_config.p``.

In order to make testing procedures work you should add something
like::

  CEREBRUM_DATABASE_CONNECT_DATA['user'] = 'cerebrum' 
  DATABASE_DRIVER = 'PostgreSQL'
  CEREBRUM_DATABASE_NAME = "cerebrum" 
  DB_AUTH_DIR = '/etc/cerebrum' 
  CLASS_CONSTANTS = (
    'Cerebrum.modules.no.uio.Constants/Constants',
    'Cerebrum.modules.no.Constants/Constants',
    'Cerebrum.modules.PosixUser/Constants',
    'Cerebrum.modules.CLConstants/CLConstants' )
  CLASS_OU = ('Cerebrum.modules.no.Stedkode/Stedkode')

to ``cereconf.py``

Cerebrum also expects to find an authentication file for the database
user named::

  DB_AUTH_DIR/passwd-DATABASE_CONNECT_DATA['user']@DATABASE_NAME

which contains the users database password. the format of the
authentication file should be::

  user<tab>databasepassword

For the configuration example above a file named
``passwd-cerebrum@cerebrum``, containing the line::

  cerebrum	somepassword

should be placed in the directory specified in ``DB_AUTH_DIR``

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
isn't very useful by itself), give the simple command::

  makedb.py

To create both the Cerebrum core components and the components found
in ``design/mod_stedkode.sql``, the following command should be
enough::

  makedb.py --extra-file=design/mod_stedkode.sql

The ``--extra-file`` argument can be repeated, if you want to install
more than one non-Core module::

  makedb.py --extra-file=design/mod_stedkode.sql \
    --extra-file=mod_posix_user.sql

Testing the distribution (optional)
-------------------------------------

Now that the database has been created, you might want to run some of
the self-tests included in the distribution. This is not required,
though, but it will give you a (rather naive) sanity check on your
system.

The tests are started with the command::

  python setup.py test --check

Building Cerebrum from a CVS tree
===================================

If you are building Cerebrum from a CVS tree or you want to do
development you will need some additional software:

* Apache ant
* Java

* ant is a Java-based build tool. For more information and download
  check <http://ant.apache.org/>. It is recommended to use version
  1.5 or later.
* Java is an object-oriented programming language developed by
  Sun. More information about Java is available from
  <http://java.sun.com/>.

The installation procedure here is basically the same as described
above. However, for some tasks you might have to convince Python to
use the Cerebrum modules directly in the CVS tree, rather than any
similar modules already installed elsewhere on your system.

For such tasks the environment variable PYTHONPATH comes in handy.  By
setting the variable to a colon-separated list of directories, you're
effectively telling Python "Look for modules in these directories
before you start searching in the familiar places".  Hence, with a
command along the lines of::

  PYTHONPATH='pwd'; export PYTHONPATH

executed after changing to the directory where setup.py lives, you
should be well on your way.

Building the client requires that you install Java and Apache Ant.
You will also need to set ``JAVA_HOME`` to point to
your Java installation.


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
installation. More information about upgrading is available at
<http://cerebrum.sourceforge.net>

Using Cerebrum
====================

Cerebrum core classes are used to update the information about the
entities registered. You may update any attributes of a given entity
by accessing the data trough a python program. A file which you would
use to add or update information about name, address and fax number to
an Organizational Unit should look something like this::

  #!/usr/bin/env python2.2
  import cerebrum_path

  from Cerebrum import Errors
  from Cerebrum.Utils import Factory

  OU_class = Factory.get('OU')

  k = {  # Define some imaginary place
      'fakultetnr':    15,
      'instituttnr':   14,
      'gruppenr':      14,
      'stednavn':      'some place',
      'forkstednavn':  'some place'
      }

  def main():
      db = Factory.get('Database')()
      co = Factory.get('Constants')(db)
      ou = OU_class(db)

      ou.clear()
      try:
          ou.find_stedkode(k['fakultetnr'],
                           k['instituttnr'],
                           k['gruppenr'])
      except Errors.NotFoundError:
          pass
      ou.populate(k['stednavn'], k['fakultetnr'],
                  k['instituttnr'], k['gruppenr'],
                  acronym=k.get('akronym', None),
                  short_name=k['forkstednavn'],
                  display_name=k['stednavn'],
                  sort_name=k['stednavn'])
      if k.has_key('adresselinje1_besok_adr'):
          ou.populate_address(
              co.system_lt, co.address_street,
              address_text="%s\n%s" %
              (k['adresselinje1_besok_adr'],
               k.get('adresselinje2_besok_adr', '')),
              postal_number=k.get('poststednr_besok_adr',
                                  None),
              city=k.get('poststednavn_besok_adr', None))
      if t['kommtypekode'] == 'FAX':
          ou.populate_contact_info(
              co.system_lt, co.contact_fax,
              t['telefonnr'], contact_pref=n)
      op = ou.write_db()
      if op is None:
          print "**** EQUAL ****"
      elif op:
          print "**** NEW ****"
      else:
          print "**** UPDATE ****"
      db.commit()

  if __name__ == '__main__':
      main()

