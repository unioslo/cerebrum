====================================================================
Design documentation for revamped LMS-export being developed in 2007
====================================================================

:Date: Last update $Date$
:Author: Last updated by $Author$

.. sectnum:: 
.. contents:: Contents

Overview
--------

In a very general sense, any LMS will be populating groups with
people, with the groups belonging to a certain structure, e.g. within
departments and courses/classes. Hence it should be possible to
implement some generic handling of the LMS exports, regardless of
which system(s) the data comes from, and which system(s) the data is
delivered to and in which manner.


Datagathering
-------------

For the time being, FS and Cerebrum itself are the only data-sources
for the LMS-export. At first we'll be accessing FS directly for the
information we need, but in the future we might want to be able to use
locally stored/cached files for this (e.g. in cases where FS might be
offline for some reason). It is also thinkable that we might be using
other systems than FS as sources for informationin the future.

Therefore, we'll use a "pluggable" interface to handle data retrieval
where any given method/plug-in will be responsible for delivering data
based on a generic data-model, but where the exact way of delivering
said data is left entirely up to the plug-in, based on given
configuration.

To simplify things a bit, the information that any given import method
should provide should be the union of information needed for a basic
export to any potential export system. If a particular site needs more
information, a need that is site-specific and not LMS-specific, the
site should extend the basic import through mix-ins/suchlike.

Since the various institutions probably will have diverging criterea
for data selection, the basics should be fairly general and
uncomplicated, then leave it to the institutions-sepcific code to
refines and narrow down tghe data as needed.


Internal datamodel
------------------

In the interim datamodel (the end-state for all imports/start-state
for all exports), we'll register the following information:

General information
~~~~~~~~~~~~~~~~~~~

 * Datasource(s)?
 * Properties
   * Intended destination?
   * Date for data retrieval/export?

 The latter two can most likely be designated by the export itself.

People/users
~~~~~~~~~~~~

 * Username
 * Password information (needs to be specified)
 * Name
 * Source for information
 * Email, including some settings (need to be detailed)
 * "Systemrole"

Groups
~~~~~~

 * Name/Description (short/long)
 * Id
 * Source for information
 * Grouptype (Fronter-specific?)
 * "Relationship"?


Relationships
~~~~~~~~~~~~~

 * Each group needs to know who are members of that group, and the
   nature of their membership.
 * Each group needs a list of sub-groups.


Data export
-----------

Given that the export should handle target systems such as Fronter,
Blackboard and It's Learning and that two different institutions might
have different requirements even though they use the same LMS system,
we'll use plug-ins/mix-ins to handle the conversion of the generalized
data into the format suitable for the recipient system.


Glassary er terminology
-----------------------

Differnces in terminology between LMS'es
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+---------------+--------------+--------------+---------------+----------------------------------------------+
|               | Fronter      | Blackboard   | It's Learning | Description                                  |
+===============+==============+==============+===============+==============================================+
|               | Rom          |              |               |                                              |
| General       +--------------+--------------+---------------+----------------------------------------------+
|               | Korridor     |              |               | A group of (related) rooms and/or sub-groups |
+---------------+--------------+--------------+---------------+----------------------------------------------+
|               |              |              |               |                                              |
| Authorization/|              |              |               |                                              |
|  roles        |              |              |               |                                              |
|               |              |              |               |                                              |
|               |              |              |               |                                              |
|               |              |              |               |                                              |
|               |              |              |               |                                              |
|               |              |              |               |                                              |
+---------------+--------------+--------------+---------------+----------------------------------------------+


