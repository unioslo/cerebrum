==============
Design
==============

In this document I will try to describe the design I've observed while working
with Spine this last year.  I can't really claim that I understood everything,
but hopefully I can transfer some of it to those who come after me.


The Big Picture
---------------

At the lowest layer, there is a database schema.  Then we have the layer called
Cerebrum Core, or just Core.  This is an ORM with business logic included.  The
design of the database and Cerebrum Core is explained elsewhere, so I won't
cover it here.

Spine is a server that makes the Cerebrum database available to network clients
using the Corba ORB.  In short, when the spine server starts, it imports the
spine modules and generates an IDL file with the structs, classes and methods
that are defined in them.  This IDL file is compiled by clients and the
resulting API is then used to interact with Cerebrum.

In addition to this generated IDL, the spine server supports a minimal interface
that lets clients connect and download the generated IDL.  Since this
mini-interface doesn't change very often, it's safe to include that IDL with the
clients source code.

Since Corba is available for most programming languages, it's possible to create
clients in whatever language you should wish.  However, the clients that are
being used today are all written in Python, so this portability isn't really in
use as of 2007-06-20.


Broken Layers
~~~~~~~~~~~~~~

We define four layers with the database as Layer 1, Cerebrum Core as Layer 2,
the Spine Server as Layer 3 and the Spine Client as Layer 4.

The rule is that a layer can only access functionality in it's closest
neighbours.  That is, Layer 3 can only access functionality in Layer 2 and 4.
Unfortunately, this rule is not followed as the Spine Server contains code that
is run directly against the database (Layer 1).

A future goal is to replace the offending code with code that is more in line
with our architecture.


Spine Modules
~~~~~~~~~~~~~~


