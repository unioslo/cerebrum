-- TODO: Insert license text

category:metainfo;
name=ad_email;
category:metainfo;
version=1.0;


category:main;
CREATE TABLE ad_email
(
  account_name  CHAR VARYING (20)
                NOT NULL,
  local_part    CHAR VARYING (64)
                NOT NULL,
  domain_part   CHAR VARYING (64)
                NOT NULL,
  create_date   DATE,
  update_date   DATE,
	CONSTRAINT ad_email_pkey PRIMARY KEY (account_name, local_pary, domain_part)
);


category:drop;
DROP TABLE ad_email;
