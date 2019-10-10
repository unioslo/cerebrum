Cerebrum
========

Cerebrum is a Python/RDBMS framework upon which user administration systems can be built.

Requirements
------------

* Python 2.7
* PostgreSQL Database


Dependencies
-------------

* M2Crypto (yum install m2crypto / pip install M2Crypto)
* psycopg2 (yum install python-psycopg2 / pip install psycopg2)
* passlib (pip install passlib)
* ldap (yum install python-ldap / pip install python-ldap)
* lxml (yum install python-lxml / pip install lxml)
* processing (? / pip install processing)
* mx (egenix-mx-base) (yum install python-egenix-mx-base / pip install egenix-mx-base)
* ssl (backport)

Optional dependencies
^^^^^^^^^^^^^^^^^^^^^

Some dependencies are optional, depending on what features you want to use:

* twisted - for the webservice daemon CIS
* soaplib - for webservice communication
* rpclib - for webservice communication
* pika - for publishing events to an external broker with EventPublisher, via AMQP 0-9-1

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

The latest source is available from [Stash](https://bitbucket.usit.uio.no/projects/CRB/repos/cerebrum/).

Documentation
-------------

This is a brief summary of the currently existing documentation for Cerebrum:

* README.md - this document
* INSTALL.md - describes the installation procedure
* design/adminprotocol.html - describes communication between the administration server and its clients
* design/cerebrum-core.dia - diagram showing the core databasetables in cerebrum. Can be displayed with [Dia](https://wiki.gnome.org/Apps/Dia/)
* design/entity_usage.txt - describes how to modify data in the database

The documentation for the core api can be read using pydoc.
