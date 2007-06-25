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

The Spine Server
----------------

The core of the spine server is Builder.py.  This class provides the
functionality to build methods from attributes and for registering methods and
attributes for the classes.  If you for example want to make a class that maps
against the Host table in the database, this class should inherit from Builder.
The class then defines the slots (or attributes) that it wants to read from the
Host table in the database.  Now it's possible to run Host.build_methods() and
Builder will create set_ and get_ methods for the slots we defined.

Another important part of Builder is the function get_builder_classes (defined
in Builder.py).  When this function is called, it checks Builder.__subclasses__
and recursively finds all the loaded classes that have Builder functionality.

When the Spine Server starts, the SpineModel module is loaded.  This module
should import all the modules we want to use.  Then we call
Builder.get_builder_classes and use the result to generate the Corba IDL.

Now, this only covers the get_ and set_ methods.  We also need other methods.
These we define in the respective modules and use the register_methods-method
to tell Builder to add it to the interface.  Getting back to our Host-example,
we can define a create_host method.  Since this method would return a Host
object, we define the method _after_ the end of the Host class.  We then add it
to the Host class by calling Host.register_methods([create_host]).  But before
we can do this, we need to set some "signatures" on the method we created.


Signatures
~~~~~~~~~~

An important concept in Builder is signatures.  These are used to add metadata
to the methods.  In the Host.create_host method, we would add a couple of
signatures to tell Builder what the return type of the method is, and what types
the arguments are.  Here's the full definition of create_host:

  def create_host(name, description):
    new_host = ...
    ...
    return new_host
  create_host.signature = Host
  create_host.signature_args = [str, str]
  Host.register_methods([create_host])

The signatures we've mentioned so far are the only required signatures.  Beyond
this, there are some optional signatures that you might be interested in.

signature_public
^^^^^^^^^^^^^^^^



