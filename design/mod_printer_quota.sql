/*
 * Copyright 2004 University of Oslo, Norway
 *
 * This file is part of Cerebrum.
 *
 * Cerebrum is free software; you can redistribute it and/or modify it
 * under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * Cerebrum is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with Cerebrum; if not, write to the Free Software Foundation,
 * Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.
 */

/* tables used by Cerebrum.modules.no.uio.printer_quota.PaidPrinterQuotas.

  Stores current and history data for users printjobs and payments. */
category:metainfo;
name=printer_quota;
category:metainfo;
version=1.0;
category:drop;
DROP TABLE paid_quota_printjob;
category:drop;
DROP TABLE paid_quota_transaction;
category:drop;
DROP TABLE paid_quota_history;
category:drop;
DROP TABLE paid_quota_transaction_type_code;
category:drop;
DROP TABLE paid_quota_status;
category:drop;
DROP SEQUENCE printer_log_id_seq;

/*  paid_quota_status

   person_id
       Identifiserer personen kvoten gjelder for
   has_quota
       Bolsk verdi. Hvis false kan personen skrive ut ubegrenset.
   has_blocked_quota
       Bolsk verdi. Hvis sann nektes utskrift selv om paid_quota >
       0. Brukes typisk hvis kopipenger til kopinor ikke er betalt.
   total_pages
       Totalt antall sider personen har skrevet ut
   paid_quota
       Antal gjenstående pageunits på kvoten som personen har betalt for
   free_quota
       Antal gjenstående pageunits på kvoten som personen har fått gratis


  Trenger:

   - weekly_quota : ukentlig gratis kvote
   - max_quota    : weekly kan ikke akumulere over denne
   - this_term : en eller annen representasjon som holder rede på
                 hvilke gratis kvoter vi allerede har fått i løpet av
                 dette semesteret.

  TODO/TBD: m/person_id her blir det kun personer som kan ha kvote.
*/

category:main;
CREATE TABLE paid_quota_status (
 person_id           NUMERIC(12,0)
                       CONSTRAINT paid_quota_status_pk PRIMARY KEY
                       CONSTRAINT paid_quota_status_person_id
                       REFERENCES person_info(person_id),
 has_quota           CHAR(1)
                        NOT NULL
                        CONSTRAINT paid_quota_has_pq_bool
                          CHECK (has_quota IN ('T', 'F')),
 has_blocked_quota   CHAR(1)
                       NOT NULL
                       CONSTRAINT paid_quota_blocked_bool
                         CHECK (has_blocked_quota IN ('T', 'F')),
 weekly_quota        NUMERIC(8),
 max_quota           NUMERIC(8),
 total_pages         NUMERIC(8) NOT NULL,
 paid_quota          NUMERIC(8) NOT NULL,
 free_quota          NUMERIC(8) NOT NULL
);

category:main;
CREATE SEQUENCE printer_log_id_seq;

category:code;
CREATE TABLE paid_quota_transaction_type_code (
  code          NUMERIC(6,0)
                CONSTRAINT paid_quota_transaction_code_pk PRIMARY KEY,
  code_str      CHAR VARYING(16)
                NOT NULL
                CONSTRAINT paid_quota_transaction_codestr_u UNIQUE,
  description   CHAR VARYING(512)
                NOT NULL
);

/* paid_quota_history lagrer de enkelte transaksjoner for en utskrift.
   Ekstra detaljer er lagret i paid_quota_printjob eller
   paid_quota_transaction.  Det benyttes ikke fremmednøkler mot øvrige
   cerebrum tabeller for å unngå problemer når data slettes fra disse.

   job_id
       Intern Cerebrum-id for historikk-innslaget (primærnøkkel)
   transaction_type (NUMERIC NOT NULL)
       Typen transaksjon (betaling, justering, utskrift, etc.). Kun
       definerte kodeverdier tillatt.
   person_id
     Personen hvis kvote berøres av historikk-innslaget.  For
     ikke-personlige er denne NULL.
   tstamp
       Tidspunkt for transaksjonen
   update_by
       Account_id for brukeren som har "bestilt" transaksjonen. Skal
       ikke være satt dersom update_program er satt.
   update_program
       Navn på programmet som har foretatt transaksjonen. Skal ikke
       være satt dersom update_by er satt.
   pageunit_free / page_units_paid
       betydningen beskrevet i tabellene nedenfor.  Har negativt
       fortegn ved utskrift.
   pageunits_total
       totalt antall sider for entryen.  Merk at for utskrifter
       foretatt av personer som har has_quota='F', vil free/paid=0,
       mens denne inneholder utskriftens størrelse.
*/
category:main;
CREATE TABLE paid_quota_history (
  job_id              NUMERIC(12,0)
                        CONSTRAINT paid_quota_history_pk PRIMARY KEY,
  transaction_type    NUMERIC(6,0)
                        NOT NULL
                        CONSTRAINT paid_quota_history_transaction_type
                          REFERENCES paid_quota_transaction_type_code(code),
  person_id           NUMERIC(12,0),
  tstamp              TIMESTAMP
                        DEFAULT [:now]
                        NOT NULL,
  update_by           NUMERIC(12,0),
  update_program      CHAR VARYING(16),
  pageunits_free      NUMERIC(6,0) NOT NULL,
  pageunits_paid      NUMERIC(6,0) NOT NULL,
  pageunits_total     NUMERIC(6,0) NOT NULL
);
category:main;
CREATE INDEX paid_quota_history_person_id_idx ON paid_quota_history(person_id);

/* paid_quota_transaction har kolonner for manuelle og automatiske
   oppdateringer av kvote som ikke skyldes utskrift. 

     target_job_id
         For "undo" av (del av) utskrift. Må referere en job_id der
         transaction_type er "utskrift", og ha unique-constraint. Er
         NULL for andre typer justeringer.
     description (NOT NULL)
         Beskrivelse av grunnlaget for justeringen.
     bank_id
         For innbetalinger hvor bankens transaksjonsid er kjent, vil
         denne (evt. i kombinasjon med nødvendig Cerebrum-spesifikk
         kvalifisering) lagres i denne kolonnen. Kolonnen kan være NULL,
         men har UNIQUE-constraint, slik at duplikate registreringer av
         samme innbetaling unngås.
     payment_tstamp
         Klokkeslett for betalingen iflg. FS/e-pay
     kroner
         Innbetalt sum i kroner.  NULL dersom transaksjonen ikke er en
         betaling.

     Kolonnene pageunits_free og pageunits_paid har forskjellig betydning
     avhengig av transaction_type:

     Ved innbetalinger
       (Positiv) justering av pageunits_paid
     Ved tildeling av gratis kvote
       (Positiv) justering av pageunits_free
     Ved "saldo overført fra"
       Gjænværende pageunits_free og pageunits_paid ved saldo-tidspunktet
     Ved undo
       (Positiv) justering av pageunits_paid og evt pageunits_free
*/

category:main;
CREATE TABLE paid_quota_transaction (
  job_id              NUMERIC(12,0)
                        CONSTRAINT paid_quota_transaction_fk
                        REFERENCES paid_quota_history(job_id),
  target_job_id       NUMERIC(12,0) NULL
                        CONSTRAINT paid_quota_transaction_tgt_job_fk
                        REFERENCES paid_quota_history(job_id)
	               	CONSTRAINT paid_quota_transaction_target_u UNIQUE,
  description         CHAR VARYING(128) NOT NULL,
  bank_id             CHAR VARYING(128)
	               	CONSTRAINT paid_quota_transaction_bank_id_u UNIQUE,
  payment_tstamp      TIMESTAMP,
  kroner              NUMERIC(6,2)
);
category:main;
CREATE INDEX paid_quota_transaction_job_id_idx ON paid_quota_transaction(job_id);
category:main;
CREATE INDEX paid_quota_trans_target_job_id_idx ON paid_quota_transaction(target_job_id);


/* paid_quota_printjob har kolonner for oppdateringer som skyldes
   utskrift.

     account_id
         Brukeren PRISS hevdet foretok utskriften.
     job_name
         Navnet på utskriften
     printer_queue
         Navnet på skriverkøen
     stedkode
         Stedkoden skriveren hørte hjemme ved da utskriften ble foretatt
     spool_trace
         client.timestamp, spool_server1.timestamp, priss_server.timestamp,
         printer_queue.timestamp, printer_queue.finished
     priss_queue_id
         Kø-id for jobben i PRISS
     paper_type
         Papirtype (NULL hvis ukjent)
     pages
         Antall sider i utskriften

     Fra history tabellen:

     pageunits_free
         Justering av gratis kvote som følge av utskriften
     pageunits_paid
         Justering av betalt kvote som følge av utskriften.
*/
category:main;
CREATE TABLE paid_quota_printjob (
  account_id           NUMERIC(12,0),
  job_id              NUMERIC(12,0)
                        CONSTRAINT paid_quota_printjob_fk 
                        REFERENCES paid_quota_history(job_id),
  job_name            CHAR VARYING(128),
  printer_queue       CHAR VARYING(128),
  stedkode            CHAR VARYING(9),
  spool_trace         CHAR VARYING(128),
  priss_queue_id      CHAR VARYING(128),
  paper_type          CHAR VARYING(128),
  pages               NUMERIC(6,0)
);
category:main;
CREATE INDEX paid_quota_printjob_job_id_idx ON paid_quota_printjob(job_id);

/* arch-tag: 48922078-61f1-4374-a6b1-d16d4f8d9cd1
   (do not change this comment) */
