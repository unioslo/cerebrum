===
LT
===

LT was the old HR- and payroll-system used at the University of Oslo.

The LT integration read data from an XML file, containing:

- Employee data
- Employee roles
- Organizational data


Remaining use
==============
The LT xml *parser* is still supported, in order to import *org units* from an
LT compatible XML file.


XML format
-----------

Org unit example:
::

    <?xml version="1.0" encoding="utf-8"?>
    <data>
      <sted
          fakultetnr="80" instituttnr="10" gruppenr="0"
          forkstednavn="Example Org"
          stednavn="Example Organization"
          stedlangnavn_bokmal="Eksempelorganisasjon"
          akronym="EO"
          fakultetnr_for_org_sted="80"
          instituttnr_for_org_sted="0"
          gruppenr_for_org_sted="0"
          telefonnr="01234567"
          adrtypekode_besok_adr="EKST"
          adresselinje1_besok_adr="Gateveien 12"
          poststednr_besok_adr="0123"
          poststednavn_besok_adr="STED"

          adrtypekode_intern_adr="EKST"
          adresselinje1_intern_adr="Gateveien 13"
          poststednr_intern_adr="0321"
          poststednavn_intern_adr="STAD"
          stedpostboks="1012"
          dato_opprettet="20250115"
          dato_nedlagt=""

          nsd_kode="1237"
          opprettetmerke_for_oppf_i_kat="Y"
          >
        <komm kommtypekode="EPOST" kommnrverdi="postmaster@example.org"/>
        <komm kommtypekode="FAX" telefonnr="01234568"/>
        <komm kommtypekode="TLF" telefonnr="01234567"/>
        <komm kommtypekode="URL" kommnrverdi="https://example.org"/>
        <!-- an unknown komm type -->
        <komm kommtypekode="UNKNOWN" kommnrverdi="foo"/>
        <!-- an empty komm value -->
        <komm kommtypekode="EPOST" kommnrverdi=""/>
      </sted>
    </data>

