/***** Account som er laget av seg selv: */

INSERT INTO [:table schema=cerebrum name=entity_info]
    ( entity_id, entity_type )
  VALUES
    ( 888888, 2003 );
INSERT INTO [:table schema=cerebrum name=account_info]
    ( entity_type, account_id, owner_type, owner_id,
      np_type, create_date, creator_id, expire_date )
  VALUES
    ( 2003, 888888, 2002, (SELECT MIN(person_id) FROM person_info),
      NULL, [:now], 888888, [:now] );

/***** En filgruppe i påvente av at det kommer på plass: */

INSERT INTO [:table schema=cerebrum name=entity_info] (entity_id, entity_type)
  VALUES (999999, 2004);
INSERT INTO [:table schema=cerebrum name=group_info]
    ( entity_type, group_id, description,
      visibility,
      creator_id, create_date, expire_date ) 
  VALUES
    ( 2004, 999999, 'test da vi ikke har gruppe ting enda',
      ( SELECT code FROM group_visibility_code where code_str = 'A'),
      888888, [:now], [:now] );

INSERT INTO [:table schema=cerebrum name=posix_group]
    ( group_id, gid )
  VALUES
    ( 999999, 0 );
