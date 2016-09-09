#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

import psycopg2
import psycopg2.extras

import cereconf
from Cerebrum.Utils import Factory
logger = Factory.get_logger(cereconf.DEFAULT_LOGGER_TARGET)

database = "cerebrum"
user = "cerebrum"
host = "caesar.uit.no"

# class AccountBridge
# 
# Class to use for getting information about accounts from the existing 
# Cerebrum database on Caesar for use when adding accounts to the new Cerebrum
# database on Clavius.
#
# Use 'with' to instantiate the class, thus avoiding the need to close the database connection explicitly.
# E.g.:
#   with AccountBridge() as bridge:
#       <do stuff here...>
#       # when finished the database connection will be closed automatically
# 
class AccountBridge:

    def __init__(self):
        self._db_conn = None
        try:
            # connect to Cerebrum database on Caesar
            self._db_conn = psycopg2.connect(database = database, user = user, host = host)
            logger.info("Connected to database %s@%s" % (database, host))
        except psycopg2.DatabaseError as e:
            logger.error("DatabaseError: %s", e)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close_db()

    def close_db(self):
        if self._db_conn:
            self._db_conn.close()
            logger.info("Closed connection to database %s@%s" % (database, host))

    #############################################
    # 
    # Unames
    # 
    #############################################

    # NOTE that a person can have more than one account: 
    # Sito employees can have two accounts if they are also students/employees at uit.
    # Sito usernames are longer than 6 characters and end with 's'

    # list_unames(self, ssn)
    # 
    # Gets username(s) for person with the given ssn from the Caesar database and returns a list with the result.
    # Returns empty list if person isn't found in the database.
    # Returns None if database connection is down.
    # 
    def list_unames(self, ssn):
        if self._db_conn:
            cur = self._db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            # get username from Caesar database
            query = "SELECT entity_name FROM entity_name \
                     WHERE entity_id IN \
                        (SELECT account_id FROM account_info \
                         WHERE owner_id IN \
                            (SELECT entity_id FROM entity_external_id \
                             WHERE external_id = '%s'));" % ssn
            cur.execute(query)
            rows = cur.fetchall()
            cur.close()
            return rows
        else:
            logger.error("Couldn't get uname, no connection to %s database on %s." % (database, host))
            return None

    # get_uname(self, ssn, sito=False)
    # 
    # Gets username for person with the given ssn from the Caesar database and returns it.
    # If sito=True sito username is returned, otherwise uit username is returned
    # Returns 'None' if requested username isn't found for this person.
    # 
    def get_uname(self, ssn, sito=False):
        uit_uname = None
        sito_uname = None
        rows = self.list_unames(ssn)
        if rows != None:
            for row in rows:
                if (len(row["entity_name"]) > 6) and row["entity_name"].endswith('s'): 
                    sito_uname = row["entity_name"]
                else:
                    uit_uname = row["entity_name"]

        if sito:
            return sito_uname
        else:
            return uit_uname

    # get_uit_uname(self, ssn)
    # 
    # Gets uit username for person with the given ssn from the Caesar database and returns it.
    # Returns 'None' if no valid username is found for this person.
    # 
    def get_uit_uname(self, ssn):
        return self.get_uname(ssn)

    # get_sito_uname(self, ssn)
    # 
    # Gets sito username for person with the given ssn from the Caesar database and returns it.
    # Returns 'None' if no valid sito username is found for this person.
    # 
    def get_sito_uname(self, ssn):
        return self.get_uname(ssn, sito=True)

    #############################################
    # 
    # Passwords
    # 
    #############################################

    # get_auth_data(self, username)
    # 
    # Gets authentication data for the account with the given username.
    # 
    # Returns a list of rows of authentication data.
    # The data in each row can be referred to by their column names, method and auth_data.
    # Returns 'None' if no authentication data was found for the given username.
    # 
    def get_auth_data(self, username):
        rows = None
        if self._db_conn:
            cur = self._db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            #  get authentication data for this account
            query = "SELECT method, auth_data FROM account_authentication \
                     WHERE account_id = \
                        (SELECT entity_id FROM entity_name \
                         WHERE entity_name = '%s');" %  username
            cur.execute(query)
            rows = cur.fetchall()
            if len(rows) < 1:
                rows = None

            cur.close()
        else:
            logger.error("Couldn't get password, no connection to %s database on %s." % (database, host))
        return rows

    #############################################
    # 
    # Email addresses
    # 
    #############################################

    # get_email(self, username)
    # 
    # Gets email address for account with the given username and returns it.
    # Returns None if something goes wrong.
    # 
    def get_email(self, username):
        email = None
        if self._db_conn:
            cur = self._db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            # get local part and domain id of users primary email address from Caesar database
            query = "SELECT local_part, domain_id FROM email_address \
                     WHERE address_id = \
                        (SELECT address_id FROM email_primary_address \
                         WHERE target_id = \
                            (SELECT target_id FROM email_target \
                             WHERE target_entity_id = \
                                (SELECT entity_id FROM entity_name \
                                 WHERE entity_name = '%s')));" % username
            cur.execute(query)
            row = cur.fetchone()
            if row != None:
                local_part = row["local_part"] 
                domain_id  = row["domain_id"]

                # get domain for this email address from Caesar database
                query = "SELECT domain FROM email_domain WHERE domain_id = %s;" % domain_id
                cur.execute(query)
                row = cur.fetchone()
                if row != None:
                    domain = row["domain"]
                    email = local_part + "@" + domain
                else:
                    logger.warn("Email information not found for %s" % username)
            else:
                logger.warn("Email information not found for %s" % username)

            cur.close()
        else:
            logger.error("Couldn't get email address, no connection to %s database on %s." % (database, host))

        return email