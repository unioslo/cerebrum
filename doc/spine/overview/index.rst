==============
Overview
==============
.. Quick intro to what Spine is and what it has to do with Cerebrum

What is Spine and what does it do?
-----------------
Spine has developed into a Object-/Relation-mapper (ORM) for easily interfacing
tables from a rdbms - and exported as Corba. Corba is used for communicating
between clients and server for both read- and write-operations. Corba was
chosen as the communication-protocol back in 2003 - by historic reasons.

Spine works on top of Cerebrum-Core - which is a mix of business-logics and
O/R-mapping. 

Overview of Spine components
--------------------------------
The core components of Spine, are classes for searching, dumping and working on
objects enabled through Cerebrum-Core.

In addition, Spine has a server-component - which exports these services as
a Corba-layer. This component can be replaced or enchanced to support a different
communication-layer other than Corba (e.g. Soap, Ice etc). Since the existing 
communication-layer is Corba, there's no lock-in to Python on the client-side. 
You can programme Spine-clients using any programminglanguage that supports 
Corba. Java-client(s) has been written as proof-of-concept just to see that it 
works. At the moment, the serverside of Spine is somewhat closely tied up to 
the OmniOrb-implementation of Corba.

Spine has its own set of files - which in turn are classes - that represents 
tables in the rdbms. These classes makes use of Cerebrum-Core for database-
communication and transaction-support.

One of the main differences of working with Cerebrum-Core and Spine - is that
Spine is all about objects, while Cerebrum-Core returns resultsets when
performing a search. 

Searchers
---------
FIXME!

Dumpers
-------
FIXME!

Getting started with Spine
------------------------------
* Spine for developer/programmers: See "Programming Spine"
* Spine for system administrators: See "Configuring Spine"

..

..
   arch-tag: 4052d504-af80-11da-90c9-327a180e4463
