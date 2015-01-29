Cerebrum
========

Cerebrum is a Python/RDBMS framework upon which user administration systems can be built.

Requirements
------------

* Python 2.2.1
* SQL Database (PostgreSQL, Oracle)


Dependencies
-------------

* M2Crypto
* twisted
* soaplib
* rpclib
* lxml
* psycopg2
* smbpasswd
* ldap
* processing
* mx (egenix-mx-base)
* ssl (backport)


Mailing lists
-------------

* `cerebrum-commits@usit.uio.no` - all commit logs
* `cerebrum-developers@usit.uio.no` - the Cerebrum developers

Report bugs and misfeatures to `cerebrum-developers@usit.uio.no`.

License
-------

Cerebrum is licensed using GNU Public License version 2 and later.

Fetching the source
-------------------

The latest source is available from (Stash)[https://utv.uio.no/stash/projects/CRB/repos/cerebrum/browse].

Documentation
-------------

This is a brief summary of the currently existing documentation for Cerebrum:

* README.md - this document
* INSTALL.md - describes the installation procedure
* design/adminprotocol.html - describes communication between the administration server and its clients
* design/cerebrum-core.dia - diagram showing the core databasetables in cerebrum. Can be displayed with (Dia)[http://www.lysator.liu.se/~alla/dia/]
* design/entity_usage.txt - describes how to modify data in the database

The documentation for the core api can be read using pydoc.
