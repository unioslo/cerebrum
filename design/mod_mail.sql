CREATE TABLE mail_domain
(
  domain_name	CHAR VARYING(128),

/* TBD: Ønsker å kunne legge inn innslag her om domener uten at det
	nødvendigvis eksporteres noe data om dem til epostsystemet.
	Er det nødvendig med muligheter for registrering av flere
	opplysninger rundt dette, så som "starttidspunkt som lokalt
	domene", "tidspunkt for når domenet sluttet/vil slutte å være
	lokalt domene", etc.? */
  local		BOOLEAN
		NOT NULL,
  description	CHAR VARYING(512),
  PRIMARY KEY domain_name
);

/* TBD: Flere tabeller om mail. */
