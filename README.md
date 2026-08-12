Cerebrum
========
Cerebrum is a Python/RDBMS framework upon which user administration systems can be built.

Requirements
------------
* Python 2.7+ / Python 3.6+
* PostgreSQL Database


Dependencies
-------------
* psycopg2 (yum install python-psycopg2 / pip install psycopg2)
* passlib (pip install passlib)
* ldap (yum install python-ldap / pip install python-ldap)
* lxml (yum install python-lxml / pip install lxml)
* ssl (backport)

### Optional dependencies

Some dependencies are optional, depending on what features you want to use:

* pika - for publishing events to an external broker with EventPublisher, via AMQP 0-9-1


License
-------
Cerebrum is licensed using GNU Public License version 2 and later.


Fetching the source
-------------------
The latest source is available from
[github.uio.no](https://github.uio.no/IT-CEREBRUM/cerebrum) (access restricted)
and [github.com](https://github.com/unioslo/cerebrum) (sporadically updated).


Documentation
-------------
This is a brief summary of the currently existing documentation for Cerebrum:

* `README.md` - this document
* `docs/` - up-to-date documentation on Cerebrum
* Individual modules are (mostly) documented in their module docstrings
* `docs/admin/install.rst` - describes the installation procedure
* `design/adminprotocol.html` - describes communication between the administration server and its clients
* `design/cerebrum-core.dia` - diagram showing the core databasetables in cerebrum. Can be displayed with [Dia](https://wiki.gnome.org/Apps/Dia/)
* `design/entity_usage.txt` - describes how to modify data in the database

The `docs/` can be read as-is, but is best read through a browser.  Install
`sphinx` + `sphinx-rtd-theme`, and:
::

    cd docs/
    make html
    python -m http.server -d build/html/
