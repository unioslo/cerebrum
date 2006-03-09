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
database. Our examples are prefixed mydummy_

In our example, we want to extend our installation to support rooms and
buildings - and connecting rooms to buildings.

The first thing we need to do is to design a table-layout and write or
generate the sql for `room and building<mod_room.sql>`_ 
These sql-files, are written in Cerebrum sql-standard, so its compatible
with the cerebrum-util makedb.py - which we are going to use to create the 
new tables in the database.

Now we need to load the sql into the database using ''makedb.py''
In our case - we issue this command:
  makedb.py mod_room.sql

Step 2. Adding method(s)
========================
Ok - by this point, a successfull end of part 1 is required.
TODO: write more

Step 3. Adding attribute(s)
===========================
   As with part 2 - this part requires a successfull end of part 2.
TODO: write more
