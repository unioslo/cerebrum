category:metainfo;
name=printerquotas;
category:metainfo;
version=1.0;
category:drop;
DROP TABLE printerquotas;

category:main;
CREATE TABLE printerquotas (
 account_id           NUMERIC(12,0)
                      CONSTRAINT printerquotas_pk PRIMARY KEY
                      CONSTRAINT printerquotas_account_id
                      REFERENCES account_info(account_id),
 printer_quota        NUMERIC(8),
 pages_printed        NUMERIC(8),
 pages_this_semester  NUMERIC(8),
 termin_quota         NUMERIC(8),
 has_printerquota     CHAR(1)
		NOT NULL
		CONSTRAINT printerquotas_has_pq_bool
		  CHECK (has_printerquota IN ('T', 'F')),
 weekly_quota         NUMERIC(8),
 max_quota            NUMERIC(8)
);
