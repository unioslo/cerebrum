=================================
Spine - ServerSide programming
=================================

Introduction
============
TODO: write more.
Spine is the communicationserver used for remote
administration in Cerebrum. 

Programming with Spine on the serverside, usually includes one or all
steps described below.

Step 1. Extending the database
==============================
First step in making new objecttypes is extending the
database. Our examples are prefixed ``mydummy_``

In our example, we want to extend our installation to support rooms and
buildings - and connecting rooms to buildings.

The first thing we need to do is to design a table-layout and write or
generate the sql for `room and building<mod_room.sql>`_ 
These sql-files, are written in Cerebrum sql-standard, so its compatible
with the cerebrum-util makedb.py - which we are going to use to create the 
new tables in the database.

Now we need to load the sql into the database using ``makedb.py``
In our case - we issue this command::

  makedb.py mod_room.sql

Step 2. Pythonize your new tables.
==================================
In our dummy-sample, we have written a python-module
named ``dummy_room.py``. Further documentation and comments
on how to write such modules is found in this named file.

Step 3. Configuring Spine to load new module.
=============================================
All that is needed here, is to make shure the module is
imported by Spine. After installation, you should have
``SpineModel.py`` installed - default in ``/etc/cerebrum``.
Remember to put your new module to the path of SpineModel.
We suggest either in ``$PREFIX/Cerebrum/spine/`` or 
``$PREFIX/Cerebrum/spine/local`` to store all your local
modules.

Finally - add an import-line for new module - and restart Spine.

At this stage, you have completed every step needed for 
the serverside programming. The following steps are optional,
and serve only as example of how to expand Spine-objects on
the serverside. Now you can either start working on step 4
and/or 5 - or move onto clientside programming.

FIXME: link til clientside.rst elns

Step 4. Adding method(s)
========================
Ok - by this point, a successfull end of part 1 is required.
TODO: write more

Step 5. Adding attribute(s)
===========================
As with part 2 - this part requires a successfull end of part 2.
TODO: write more

..
   arch-tag: 4430d04a-af80-11da-9e35-eae9d3051128
