category:main;
CREATE TABLE ad_entity
(
  entity_type   NUMERIC(6,0)
                NOT NULL,
  entity_id     NUMERIC(12,0)
                CONSTRAINT ad_entity_pk PRIMARY KEY,
  ou_id         NUMERIC(12,0)
                NOT NULL
		CONSTRAINT ad_entity_ou_id REFERENCES ou_info(ou_id),
  CONSTRAINT ad_entity_entity_id FOREIGN KEY (entity_type, entity_id)
    REFERENCES entity_info(entity_type, entity_id),
  CONSTRAINT ad_entity_entity_type_chk
    CHECK (entity_type IN ([:get_constant name=entity_account],
			   [:get_constant name=entity_group]))
);


/*

  'login_script'   NULL => Don't run any login script for this user;
		   deal with things through policies etc.

  'home_dir'	   NULL => Don't connect any home directory when
		   this user logs in.

*/
category:main;
CREATE TABLE ad_account
(
  account_id    NUMERIC(12,0)
                CONSTRAINT ad_account_pk PRIMARY KEY
		CONSTRAINT ad_account_account_id
		  REFERENCES account_info(account_id)
		CONSTRAINT ad_account_account_id2
		  REFERENCES ad_entity(entity_id),
  login_script  CHAR VARYING(128),
  home_dir      CHAR VARYING(128)
);

/*

Ekstra-informasjon som ikke finnes i Cerebrum:

 * OU:
   - Ønsker mer finmasket oppdeling av OU-strukturen.
        OU=Hovedfag,OU=Ifi,OU=MNF,dc=uio,dc=no
        OU=Laveregrad,OU=Ifi,OU=MNF,dc=uio,dc=no
        OU=Labkurs,OU=Laveregrad,OU=KI,OU=MNF,dc=uio,dc=no
*/