======================
Mreg - design
======================

.. contents:: Contents
.. section-numbering::

.. setup extraction of documentation from sql/python files:

.. sysinclude::
  :vardef: ext_sqldoc scripts/ext_sqldoc.py --file ,ceresrc/design/mod_dns.sql 

.. sysinclude::
  :vardef: ext_pydoc scripts/ext_doc.py --module ,ceresrc/Cerebrum/modules/dns/

.. sysinclude::
  :vardef: template --func_template scripts/func_doc.template

Introduction
==============

The DNS API consists of two groups of classes, the ones that are tied
closely to the database, and a number of helper classes.  The helper
classes should normaly be used when updating the database, as they
perform some sanity checks on what is legal to do in the database.

Overview of the database
--------------------------
Details about each table is listed in the API section along with its
corresponding class.

Important consepts:

- the name of a host/cname/a-record... is stored in dns_owner.  A
  rename will affect all entries, even targets for mx/cnames etc.
- ip_numbers is stored in ip_number.  An update will affect all
  a-records that point to this ip
- mx_set is a collection of MX records.  It is tied to dns_owner.


.. _fig_data_model :

Figure: The database schema

.. image:: ../figures/dns.png


Validation etc.
---------------------------------

Mreg tries to maintain a set of rules to preserve the integrity of the
zone file.  The database schema preserves some constraints, such as
preventing deletion of data that other data poins to, or having
duplicate entries.  Other constraints are, however too complex to be
expressed in SQL.  Updating of such data is done through helper classes.


API
======

What follows is a brief description of the various classes and their
responsibility.

You can also get a rough overview of the design by looking at the
figure below.  Note however that methods may not be 100% up to date.

.. _fig_api :

Figure: UML class diagram of the API

.. image:: ../figures/dns_api.png

This temporary diagram illustrates how methods are divided between
bofhd_dns_cmds.py and bofhd_dns_utils.py

.. _fig_bofh_code :

Figure: UML class diagram of the bofh code

.. image:: ../figures/dns_bofh_code.png



Database-tied classes
-----------------------

These classes are thightly related to the underlying database-schema,
which is described in the same context.

API-users should be careful about updating the database using these
classes, as they do not perform much sanity checking on the changes
performed.  The ``Helper`` class provides methods the perform
consistency checks.

As a convinience many of these classes will set self.name in
``find()``.  It is, however a read-only value as updating should be
done through the ``Helper`` class.


ARecord
~~~~~~~~~~~~
.. sysinclude:: %(ext_pydoc)sARecord.py %(template)s --class_doc ARecord

Associated table:

   .. sysinclude:: %(ext_sqldoc)s --table dns_a_record


CNameRecord
~~~~~~~~~~~~
.. sysinclude:: %(ext_pydoc)sCNameRecord.py %(template)s --class_doc CNameRecord

Associated table:

  .. sysinclude:: %(ext_sqldoc)s --table dns_cname_record


DnsOwner.MXSet
~~~~~~~~~~~~~~~
.. sysinclude:: %(ext_pydoc)sDnsOwner.py %(template)s --class_doc MXSet

Associated tables:

  .. sysinclude:: %(ext_sqldoc)s --table dns_mx_set

  .. sysinclude:: %(ext_sqldoc)s --table dns_mx_set_member



DnsOwner.GeneralDnsRecord
~~~~~~~~~~~~~~~~~~~~~~~~~~~
.. sysinclude:: %(ext_pydoc)sDnsOwner.py %(template)s --class_doc GeneralDnsRecord

Associated table:

  .. sysinclude:: %(ext_sqldoc)s --table dns_general_dns_record

Code values are stored in ``dns_field_type_code``

DnsOwner.DnsOwner
~~~~~~~~~~~~~~~~~~
.. sysinclude:: %(ext_pydoc)sDnsOwner.py %(template)s --class_doc DnsOwner

Associated tables:

  .. sysinclude:: %(ext_sqldoc)s --table dns_owner

  .. sysinclude:: %(ext_sqldoc)s --table dns_srv_record



EntityNote.EntityNote
~~~~~~~~~~~~~~~~~~~~~~~
.. sysinclude:: %(ext_pydoc)sEntityNote.py %(template)s --class_doc EntityNote

Associated table:

  .. sysinclude:: %(ext_sqldoc)s --table dns_entity_note

Code values are stored in ``dns_entity_note_code``

HostInfo.HostInfo
~~~~~~~~~~~~~~~~~~
.. sysinclude:: %(ext_pydoc)sHostInfo.py %(template)s --class_doc HostInfo

Associated table:

  .. sysinclude:: %(ext_sqldoc)s --table dns_host_info

Code values are stored in ``hinfo_code``


IPNumber.IPNumber
~~~~~~~~~~~~~~~~~~~
.. sysinclude:: %(ext_pydoc)sIPNumber.py %(template)s --class_doc IPNumber

Associated tables:

  .. sysinclude:: %(ext_sqldoc)s --table dns_ip_number

  .. sysinclude:: %(ext_sqldoc)s --table dns_override_reversemap

Helper classes
---------------

DnsConstants
~~~~~~~~~~~~~~~
.. sysinclude:: %(ext_pydoc)sDnsConstants.py %(template)s --class_doc Constants


Helper.DNSError
~~~~~~~~~~~~~~~
.. sysinclude:: %(ext_pydoc)sHelper.py %(template)s --class_doc DNSError


Helper.Helper
~~~~~~~~~~~~~~~
.. sysinclude:: %(ext_pydoc)sHelper.py %(template)s --class_doc Helper


Distributed files
==================

User interface:

  Cerebrum/modules/bofhd_dns_cmds.py
    BofhdExtension for the bofhd module
  Cerebrum/modules/bofhd_dns_utils.py
    The business-logic for the bofhd module

API:

  Cerebrum/modules/DnsConstants.py
    Defines various constants
  Cerebrum/modules/dns/ARecord.py
    Handles the a_record table
  Cerebrum/modules/dns/CNameRecord.py
    Handles the cname_record table
  Cerebrum/modules/dns/DnsOwner.py
    handles dns_owner, mx_set, mx_set_members, general_ttl_record, srv_record
  Cerebrum/modules/dns/EntityNote.py
    handles entity_note.  Should perhaps be moved into Cerebrum-core
  Cerebrum/modules/dns/Helper.py
    various helper methods used by the API and bofhd to assert that we
    don't violate DNS schema etc.
  Cerebrum/modules/dns/HostInfo.py
    handles dns_host_info
  Cerebrum/modules/dns/IPNumber.py
    handles ip_number and override_reversemap
  Cerebrum/modules/dns/__init__.py
    defines some API constants

Support files:

  contrib/build_zone.py
    builds forward, reverse maps and hosts file
  contrib/import_dns.py
    migrates existing forward+reverse zone files, hosts file and
    netgroup files into the database
  contrib/strip4cmp.py
    converts forward/reverse map into a format that is usable for
    comparing zone files with "diff -u"

TODO
==========

TBD: We currently allow contact-info and comments for a-records,
cnames and hosts.  Should we move the comment+contact to dns_owner?
Do we need comments/contact info other places?


.. ---

  TODO: Her beskrives en del om hvilke sjekker vi gjør o.l.  Dette må
  lagres en plass, trolig som komentarer på relevante steder i koden?

  Some of the things The following extra things must be checked:

  - Avoid ending up with entries in ip_number that has no FKs pointing
    to it
  - That dns_owner entries contain legal characters
  - That dns_owner entries added does not contain reserved names.  TODO:
    What are "reserved names"?  Usernames?
  - nothing can have something that is a CNAME as a target, and if
    something is a CNAME, it cannot be anything else.
  - an entry in mreg_host_info must have atleast one corresponding
    a_record entry.


  When removing data, we encounter some problems that must be handled:

  - some of UiOs MX-records have no additional data, and are thus
    represented by a single entry in dns_owner.
  - we have some reverse-map ip-numbers that are not in our ip-range.

  TBD/TODO: How can we assert that deletion of data does not delete
  unintentional data, while avoiding junk left-over from partial
  deletion?


  Foreign data
  #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
  The zone suffix (.uio.no.) is not registered for each row in
  dns_owner.

  Deletion/update of dns_owner/ip_number
  #---------------------------------------
  The following commands are relevant here:

  1. ip rename  NAME
  2. ip rename  IP
  3. ip free    NAME
  4. ip free    IP
  5. ip a_rem   NAME
  6. ip a_rem   IP

  ip rename/free is interpreted as operating on dns_owner or ip_number
  depending on wheter a NAME or IP was entered.

  ip rename
  #~~~~~~~~~~~~~~
  Will update dns_owner or ip_number directly.  If target already
  exists: 

  - Force must be set
  - existing tables with FK to this dns_owner/ip_number will be
    updated to new id.
  - the old entry in ip_number/dns_owner will be deleted.
  - must check if new dns_owner is a CNAME or something else that
    violates the zone-file.

  ip free
  #~~~~~~~~~~~~~~
  If argument is an ip_number, this ip_number will be removed from the
  ip_number table (provided that it won't break any FK constraints).

  If argument is a dns_owner, it will remove data with indicated
  dns_owner_id from:

  - a_record
  - mreg_host_info
  - cname_record
  - general_ttl_record
  - entity_note
  - srv_record
  - override_reversemap

  Force must be used if "ip info" would return anything more than one
  HINFO record + one A record.

  Will throw an exception if the deleted entry is a target of any of
  the above mentioned records, or used in a mx_set.

  ip a_rem
  #~~~~~~~~~~~~~~

  Will delete the a_record + corresponding ip_number and/or dns_owner
  entry.  Will throw an exception if:

  - it is the only a_record for a mreg_host_info entry
  - if the a_record was used as a target (see 'ip free')

  
