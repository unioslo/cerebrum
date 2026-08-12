===============
ABC Enterprise
===============

The ABC Enterprise is (or was?) a standard by Uninett (now Sikt) to exchange data
between user management systems (BAS) and student management systems (SAS).

The standard consists of a data model and XML schema definition (XSD).  The
schema includes objects to represent persons, groups, and org units.

The XML description and schema used to be available at
`<http://uninettabc.no/?p=publikasjoner&sub=abc-enterprise>`_.


Data format
============
A typical ABC XML file includes:

#. A header (properties) with ID and relationship types
#. Organization object and org units
#. Person objects with ids and other personal data (names, email addresses)
#. Group objects to represent e.g. courses.
#. Relationships between objects, e.g.:

   - Course participation - i.e. a relation from a group representing an
     educational course/unit, to a list of participants/persons.

   - Affiliation - i.e. a relation from an ou (org unit) to a list of e.g.
     persons/employees
   - Semester fee payment

The format is fairly flexible, as it allows for custom relationship types to be
defined.  Object types are restricted through the schema.

Types
------
Object id types and relationship types must be defined in the properties/types
section.


Objects
-------
Objects in the XML file includes:

``organization``, ``ou``
    A single ``organization`` object along with ids (``orgidtype``), names
    (``orgnametype``), and domain (``realm``).

    One ``ou`` object per org unit, with ids (``ouidtype``), and names
    (``ounametype``).

``person``
    One person object for each person to include in the file.  Person objects
    typically includes:

    - ``personid`` (unique identifiers, one for each ``personidtype``
      available).
    - ``birthdate``
    - ``name`` - a ``fullname`` + individual name components and other, custom names/titles
    - ``contactinfo`` (one for each ``contacttype``)

``group``
    Abstract objects, typically to represent access groups, educational units,
    etc...

    Typically includes identifiers (``groupidtype``) and a human readable ``description``.


Relations
---------
Each relation type must be *defined* in the properties as a ``relationtype``.
This definition restricts a relation to a specific *subject* type to a specific
*object* type.

A single relation binds *one* subject to one or more *objects*.


Minimal example file
====================
This is a fictional example file, with fictional relationship types, id types,
etc...  It is only meant to illustrate the general format.  A real XML file
would typically follow a standardized set of types.

::

    <document>
      <properties>
        <datasource>source-system</datasource>
        <target>target-system</target>
        <timestamp>2026-05-12T11:05:00</timestamp>
        <types>
          <orgidtype>org-id</orgidtype>
          <orgnametype>org-name</orgnametype>
          <ouidtype>ou-id</ouidtype>
          <ounametype>ou-name</ounametype>
          <personidtype>employee-id</personidtype>
          <personidtype>student-id</personidtype>
          <personidtype>username</personidtype>
          <groupidtype>group-name</groupidtype>
          <contacttype subject="person">email</contacttype>
          <partnametype>work title</partnametype>
          <relationtype subject="group" object="person">group-members</relationtype>
        </types>
      </properties>
      <organization>
        <orgid orgidtype="org-id">123</orgid>
        <orgname lang="en" orgnametype="org-name">Example</orgname>
        <realm>example.org</realm>
        <ou>
          <ouid ouidtype="ou-id">000000</ouid>
          <ouname lang="en" ounametype="ou-name">Example</ouname>
        </ou>
        <ou>
          <ouid ouidtype="ou-id">010000</ouid>
          <ouname lang="en" ounametype="ou-name">Example department</ouname>
        </ou>
      </organization>
      <person>
        <personid personidtype="employee-id">123</personid>
        <personid personidtype="username">olanord</personid>
        <name>
          <fn>Ola Nordmann</fn>
          <n>
            <given>Ola</given>
            <family>Nordmann</family>
            <partname partnametype="work title">Example employee</partname>
          </n>
        </name>
        <birthdate>1996-06-28</birthdate>
        <contactinfo contacttype="email">olanord@example.org</contactinfo>
      </person>
      <group>
        <groupid groupidtype="group-name">foo</groupid>
        <description>Example group foo</description>
      </group>
      <relation relationtype="group-members">
        <subject>
          <groupid groupidtype="group-name">foo</groupid>
        </subject>
        <object>
          <personid personidtype="username">olanord</personid>
        </object>
      </relation>
    </document>


ABC import
===========
Cerebrum used to include import scripts to support *source systems* using the
ABC Enterprise format.  This functionality has been removed.


ABC export
===========
Cerebrum supports a basic ABC enterprise *export*.

Note that the export *combines* data from FS and Cerebrum, and needs direct
access to the FS database to generate an abc export file.

The ABC export includes:

#. All organization object and org units.  This is a fairly minimal list, and
   only includes location code (stedkode) and a single name for each org unit.

#. All (active) persons, with personal data (most external ids, names, primary
   username, primary email addresses)

#. Educational unit relationships:

   - Educational courses/units, and course participation
   - Affiliation - person roles at org units
   - Semester fee payment


Relationships
-------------

Class/cohort (kull)
    Each cohort is represented as a *group*, with an id generated from its
    ``<study-program>:<term>:<year>``, e.g. ``ALU:HØST:2003``.

    The cohort group is bound to an org unit with a ``kull-ou`` relationship,
    and contains a list of participants, using a ``kull-people`` relationship.

Educational unit/course
    Each course is represented as a *group*, with an id generated from its
    ``<institution-number>:<subject>:<version>:<term>:<year>:<term-number>``,
    e.g. ``185:INF-1000:1:HØST:2006:1``.

    As with cohorts, the group is bound to an org unit with a ``ue-ou``
    relationship, and contains a list of students in a ``ue-people``
    relationship.

Semester payment
    To convey information about active enrollment, a single ``paid-group`` group
    exists.  This group lists all students with a semester fee payment in a
    ``paid-people`` relationship.


Affiliations
    Each affiliation type is its own relationship type.

    For each org unit, there is a relationship of the given role, which then
    lists all persons with the given role at the given org unit.
