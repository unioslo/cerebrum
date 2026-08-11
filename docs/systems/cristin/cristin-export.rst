======================
Legacy Cristin export
======================

Overview
=========
The Cris/NVA (formerly Cristin, Frida) archive needs information about each
university hierarchies, as well as its researchers/published authors.

Cerebrum supports generating a legacy import XML file according to the `Cristin
import specification <http://www.cristin.no/institusjonsdata/>`_ and `XSD
<http://www.cristin.no/institusjonsdata/schema/Frida-import-1_0.xsd>`_.

Normally, Cerebrum would generate a new XML file each day, which is then sent to
Cristin.


Data
=====
The following data is included in the XML file:

- Organization and org units
- People (employees, emeritus, research fellows)
- Org affiliations (employments, guest roles)


Special fields
---------------
The following are descriptions of fields that are fairly unique to the Cristin
export and Cristin eco-system.

NSD-kode
    A unique ID that identifies a specific research entity.

    The entity may be a university or research institute, or a subdivision like
    a faculty, or research group.

    NSD was short for *Norsk samfunnsvitenskapelig datatjeneste*.  The code was
    primarily intended for use in the NSD archives, but is also useful in
    Cristin to connect research to specific research groups.

Institusjonsnummer
    A unique ID given to the organization.

    The identifier is typically used in both Felles Studentsystem (FS) and
    Cristin.

Stedkode
    Location code.

    A legacy org unit identifier at FS/Cristin organizations.

    The location code is a six-digit code, structured in three two-digit pairs:
    ``AABBCC``, where ``AA`` is a department id (avdeling), ``BB`` is
    a sub-department (underavdeling), and ``CC`` is a sub-sub-department
    (gruppe).

    The number groups are often referred to as organization levels, and
    could historically be used semantically (i.e. the *group* 102030 would be a child of
    the *sub-department* 102000).

    The levels are also often referred to as *faculty*, *institute*, and *group*.

Stillingskode
    Job codes or assignment codes are four digit numerical codes that refer to a
    specific wage groups in union agreement salary tables.  Each group is named
    (job name, assignement name, stillingstittel) and given this numerical id.

    The codes were also used in the Statens sentrale tjenestemannsregister
    (SST) in SSB.


File structure
===============
Note that the XML file *must* be encoded in Latin 1 (ISO-8859-1), which should
also be declared in the XMl header (``<?xml version="1.0"
encoding="ISO-8859-1"?>``).

- `beskrivelse`_ (description, metadata)
- `institusjon`_ (organizational data)
- `organisasjon`_ (organizational tree, org units)
- `personer`_ (people)

Each of the parts belongs to its own element, wrapped in a single
``fridaImport`` root element:
::

    <fridaImport>
      <beskrivelse>...</beskrivelse>
      <institusjon>...</institusjon>
      <organisasjon>...</organisasjon>
      <personer>...</personer>
    </fridaImport>


beskrivelse
-----------
This element contains import metadata:

- ``kilde`` (source) - who built the document?
- ``dato`` (date) - when was the document built?
- ``mottager`` (recipient) - who was the document built for?

Example:
::

    <beskrivelse>
      <kilde>UIO</kilde>
      <dato>2017-08-22 01:20:21</dato>
      <mottager>UiO-FRIDA</mottager>
    </beskrivelse>


institusjon
-----------
Literal: ``institution`` - basic information about the entity or organization
the document describes.

Should typically include:

- ``institusjonsnr`` (org identifier, see `Institusjonsnummer`) - e.g. ``185``
  for the University of Oslo
- ``navnBokmal`` (name, nb) - e.g. ``Universitetet i Oslo``
- ``navnEngelsk`` (name, en) - e.g. ``University of Oslo``
- ``akronym`` (acronym/short name) - e.g. ``UiO``
- ``NSDKode`` (org identifier, see `NSD-kode`) - e.g. ``1110`` for UiO

The export does *not* include the following, optional fields:

- ``lokalFridaURL`` (url) - A url to more information about Cristin at the
  organization.
- ``lokalFridaEpost`` (email address) - An email address to use for questions
  about Cristin at the organization.

Example:
::

    <institusjon>
      <institusjonsnr>185</institusjonsnr>
      <navnBokmal>Universitetet i Oslo</navnBokmal>
      <navnEngelsk>University of Oslo</navnEngelsk>
      <akronym>UiO</akronym>
      <NSDKode>1110</NSDKode>
    </institusjon>


organisasjon
------------
The full organizational tree, as it should be known to Cristin.

The org tree should contain one root org unit.  The root org unit parent points
back to itself.


Requirements:

- The export only includes active org units that are active and present within
  the selected org tree (perspective).  This excludes certain org units - see
  the org unit import for more details.

- Included org units *must* have a location code (stedkode)

- Included org units *must* have a proper name (long name/full name)


Each org unit (``enhet``) contains the following fields:

- ``institusjonsnr`` - the same value as `institusjon`_.
- ``avdnr`` (department number) - first two digits of the org unit location code
  (`stedkode`).
- ``undavdnr`` (sub-department number) - middle two digits of the org unit
  location code (`stedkode`).
- ``gruppenr`` (group number) - last two digits of the org unit location code
  (`stedkode`).
- ``institusjonsnrUnder`` ``institusjonsnr`` of *parent* org unit
- ``avdnrUnder`` ``avdnr`` of *parent* org unit
- ``undavdnrUnder`` ``undavdnr`` of *parent* org unit
- ``gruppenrUnder`` ``gruppenr`` of *parent* org unit
- ``datoAktivFra`` (org unit start date) - format ``YYYY-MM-DD``, may be empty
- ``datoAktivTil`` (org unit end date) - format ``YYYY-MM-DD``, may be empty,
  defaults to ``9999-12-31``.
- ``navnBokmal`` (name, nb) - full name of the org unit
- ``navnEngelsk`` (name, en) - full name of the org unit
- ``akronym`` (acronym/short name)
- ``postadresse`` (postal address) - street address
- ``postnrOgPoststed`` (zip-code and city) - space-separated norwegian zip-code and city
- ``land`` (country)
- ``telefonnr`` (phone number)
- ``telefaxnr`` (fax number)
- ``epost`` (email address)
- ``URLBokmal`` (url)

The following optional fields are not included:

- ``NSDKode`` - Cerebrum originally didn't support having different NSD
  identifiers for individual org units.
- ``enhetErstattesAv`` (unit replaced by ...)

Example:
::

    <organisasjon>
      <enhet>
        <institusjonsnr>185</institusjonsnr>
        <avdnr>15</avdnr>
        <undavdnr>0</undavdnr>
        <gruppenr>0</gruppenr>
        <institusjonsnrUnder>185</institusjonsnrUnder>
        <avdnrUnder>90</avdnrUnder>
        <undavdnrUnder>0</undavdnrUnder>
        <gruppenrUnder>0</gruppenrUnder>
        <datoAktivFra>1900-01-01</datoAktivFra>
        <datoAktivTil>9999-12-31</datoAktivTil>
        <navnBokmal>Det matematisk-naturvitenskapelige fakultet</navnBokmal>
        <navnEngelsk>Faculty of Mathematics and Natural Sciences</navnEngelsk>
        <akronym>MATNAT</akronym>
        <postadresse>Sem S<E6>lands vei 24, Fysikkbygningen</postadresse>
        <postnrOgPoststed>0371 OSLO</postnrOgPoststed>
        <land>NO</land>
        <telefonnr>22855200</telefonnr>
        <telefaxnr>22856339</telefaxnr>
        <URLBokmal>https://www.matnat.uio.no/</URLBokmal>
      </enhet>
      ...
    </organisasjon>


personer
--------
A list of people affiliated with the organization.

Note that only certain people would typically be included.  The requirements
are:

- *mandatory* - must have an active employment in the HR system
- *mandatory* - must have a norwegian national id in the HR system
- must *either* be faculty staff (``ANSATT/vitenskapelig``) *or* consent to
  publication
- must *either* be a regular employee (MG 4, MUG 4) *or* consent to publication


Each included person (``person``) contains the following fields:

- ``fnr`` (norwegian national id) - 11 digits
- ``reservert`` (reserved) - Settes til ``J`` (yes) or ``N`` (no) to indicate if
  the person can be listed in public registers.
- ``etternavn`` (surname, last name)
- ``fornavn`` (given name, first name)
- ``brukernavn`` (username) - primary account in Cerebrum.  May be empty if no
  appropriate account exists.

- ``telefonnr`` (phone number) - work phone number
- ``telefaxnr`` (fax number) - work fax number
- ``epost`` (email address) - Primary e-mail address in Cerebrum, if a user
  account exists, and is also an active email account.

- ``URL`` (url) - personal url - always empty
- ``personligTittel`` - personal title from the HR system (if available)
- ``ansettelser`` (employments) - employment roles
- ``gjester`` (guests) - guest roles

The following optional fields are never included:

- ``fnrErstatter`` - previous ``fnr`` values
- ``adresseinfo`` - addresses

Example:
::

  <person reservert="N" fnr="12345678902">
    <etternavn>Nordmann</etternavn>
    <fornavn>Kari</fornavn>
    <brukernavn>karinord</brukernavn>
    <epost>kari.nordmann@admin.uio.no</epost>
    <telefonnr>23075000</telefonnr>
    <personligTittel>Professor</personligTittel>
    <ansettelser>
      <!-- employment roles -->
    </ansettelser>
    <gjester>
      <!-- guest roles -->
    </gjester>
  </person>


ansettelser
------------
A list of employment roles.

Note that a custom module has been created for Cerebrum to hold this
information.

Employment consists of one or more roles (``ansettelse``) that
connects the person to an org unit, and contains the following fields:

- ``institusjonsnr`` - reference to a given org unit
- ``avdnr`` - reference to a given org unit
- ``undavdnr`` - reference to a given org unit
- ``gruppenr`` - reference to a given org unit
- ``stillingskode`` (assignment code) - see `Stillingskode`
- ``datoFra`` (role start date)
- ``datoTil`` (role end date)
- ``stillingsbetegnelse`` (assignment name) - e.g. ``Professor``
- ``stillingsandel`` (assignment percentage) - from 0-100%

Assignments are omitted if its org unit/location code is not included in the
export.


Example:
::

  <person reservert="N" fnr="12345678902">
    <!-- Personinformasjon -->
    <ansettelser>
      <ansettelse>
        <institusjonsnr>185</institusjonsnr>
        <avdnr>53</avdnr>
        <undavdnr>18</undavdnr>
        <gruppenr>13</gruppenr>
        <stillingskode>1013</stillingskode>
        <datoTil>9999-12-31</datoTil>
        <stillingsbetegnelse>Professor</stillingsbetegnelse>
        <datoFra>2016-07-01</datoFra>
        <stillingsandel>100.0</stillingsandel>
      </ansettelse>
    </ansettelser>
  </person>


gjester
-------
People who are not employees, will typically have *guest* roles rather than
employment roles.

Each guest role (``gjest``) is bound to an org unit, and includes the following
fields:

- ``institusjonsnr`` - reference to a given org unit
- ``avdnr`` - reference to a given org unit
- ``undavdnr`` - reference to a given org unit
- ``gruppenr`` - reference to a given org unit
- ``datoFra`` (guest role start date)
- ``datoTil`` (guest role end date)
- ``gjestebetegnelse`` (guest role name) - e.g. ``EMERITUS``

Example:
::

  <person reservert="N" fnr="12345678901">
    <!-- Personinformasjon -->
    <gjester>
      <gjest>
        <institusjonsnr>185</institusjonsnr>
        <avdnr>28</avdnr>
        <undavdnr>8</undavdnr>
        <gruppenr>2</gruppenr>
        <datoFra>2017-05-31</datoFra>
        <gjestebetegnelse>EMERITUS</gjestebetegnelse>
        <datoTil>2020-05-31</datoTil>
      </gjest>
    </gjester>
  </person>
