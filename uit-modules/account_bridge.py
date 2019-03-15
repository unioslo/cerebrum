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
# Cerebrum database on Caesar. For use when adding accounts to the new Cerebrum
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
            logger.error("Couldn't get uname. No connection to %s database on %s." % (database, host))
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
                    logger.debug("%s is legal sito username" % (row['entity_name']))
                else:
                    #
                    # Do not collect usernames on the form aaa99(8,9). these are admin accounts and not to be included
                    # (they are soon to be deleted from all systems)
                    #
                    if((len(row["entity_name"]) == 6) and ((row["entity_name"][3:5] == '99') and (row["entity_name"][5] in ('8','9')))):
                        logger.debug("%s is admin username. do not process" % (row['entity_name']))
                    else:
                        uit_uname = row["entity_name"]
                        logger.debug("%s is legal uit username" % (row['entity_name']))

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
            logger.error("Couldn't get password. No connection to %s database on %s." % (database, host))
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
            logger.error("Couldn't get email address. No connection to %s database on %s." % (database, host))

        return email

    # get_domains(self)
    # 
    # Returns a dict of all domain ids with their value.
    # Returns an empty dict if something goes wrong.
    # 
    # Used by get_all_primary_emails() and get_all_email_aliases()
    # 
    def get_domains(self, db_cursor):
        domains = dict()

        query = "SELECT domain_id, domain FROM email_domain;"
        db_cursor.execute(query)
        rows = db_cursor.fetchall()

        if rows != None:
            for row in rows:
                domains[row["domain_id"]] = row["domain"]
        else:
            logger.error("Found no domains in database.")

        return domains

    # get_username_from_target_id(self, target_id, db_cursor)
    # 
    # Returns username connected to a given target_id
    # Returns None if something goes wrong
    # 
    # Used by get_all_primary_emails() and get_all_email_aliases()
    # 
    def get_username_from_target_id(self, target_id, db_cursor):
        username = None

        query = "SELECT entity_name FROM entity_name \
                 WHERE entity_id = \
                    (SELECT target_entity_id FROM email_target \
                     WHERE target_id = '%s');" % target_id
        db_cursor.execute(query)
        result = db_cursor.fetchone()

        if result != None:
            username = result['entity_name']

        return username

    # get_all_primary_emails(self)
    # 
    # Returns a dict of all primary email addresses with username as key
    # (format: {<username> : {'email' : <EMAIL ADDRESS>, 'expire_date' : <EXPIRE DATE>}})
    # Returns an empty dict if something goes wrong.
    # 
    def get_all_primary_emails(self):
        logger.info("Getting all primary emails.")
        emails = dict()
        if self._db_conn:
            cur = self._db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            
            # get data about all primary email addresses
            query = "SELECT target_id, local_part, domain_id, expire_date FROM email_address \
                     WHERE address_id IN \
                        (SELECT address_id FROM email_primary_address);"
            cur.execute(query)
            rows = cur.fetchall()

            # get all domains
            domains = self.get_domains(cur)

            if (rows != None) and len(domains) > 0:
                for row in rows:
                    email_info = dict()
                    target_id = row['target_id']
                    local_part = row['local_part']
                    domain_id = row['domain_id']
                    expire_date = row['expire_date']
                    if expire_date != None:
                        expire_date = expire_date.strftime("%Y-%m-%d")

                    # get username that has this email address
                    uname = self.get_username_from_target_id(target_id, cur)
                    if uname == None:
                        logger.error("Couldn't find username for email with target_id %s. Ignoring it." 
                                    % target_id)
                        continue

                    # build email address
                    email = local_part + "@" + domains[domain_id]

                    email_info['email'] = email
                    email_info['expire_date'] = expire_date

                    # add email info to emails dict
                    emails[uname] = email_info
            logger.info("Finished getting %s primary emails." % len(emails))
        else:
            logger.error("Couldn't get primary emails. No connection to %s database on %s." % (database, host))

        return emails

    # get_email_aliases(self, username)
    # 
    # Gets email aliases for account with the given username and returns them as a list.
    # Returns an empty list if something goes wrong, or no aliases are found.
    # 
    # Note: the returned list will not contain primary email address.
    # 
    def get_email_aliases(self, username):
        aliases = list()
        if self._db_conn:
            cur = self._db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            query = "SELECT address_id, local_part, domain_id FROM email_address \
                     WHERE target_id = \
                        (SELECT target_id FROM email_target \
                         WHERE target_entity_id = \
                            (SELECT entity_id FROM entity_name \
                             WHERE entity_name = '%s'));" % username
            cur.execute(query)
            rows = cur.fetchall()

            if len(rows) > 0:
                # get address_id of primary email address
                query = "SELECT address_id FROM email_primary_address \
                         WHERE target_id = \
                            (SELECT target_id FROM email_target \
                             WHERE target_entity_id = \
                                (SELECT entity_id FROM entity_name \
                                 WHERE entity_name = '%s'));" % username
                cur.execute(query)
                primary_row = cur.fetchone()
                primary_id = primary_row['address_id']

                for row in rows:
                    if row['address_id'] != primary_id: # Don't add primary address
                        # get domain for this email address from Caesar database
                        query = "SELECT domain FROM email_domain WHERE domain_id = %s;" % row["domain_id"]
                        cur.execute(query)
                        dom_row = cur.fetchone()

                        if dom_row != None:
                            email = row['local_part'] + "@" + dom_row["domain"]
                            aliases.append(email)
            else:
                logger.warn("Email information not found for %s" % username)

            cur.close()
        else:
            logger.error("Couldn't get email aliases. No connection to %s database on %s." % (database, host))

        return aliases


    # get_all_email_aliases(self)
    # 
    # Returns a dict of all email aliases with username as key
    # (format: {<username> : list of {'email' : <EMAIL ADDRESS>, 'expire_date' : <EXPIRE DATE>}})
    # Returns an empty dict if something goes wrong.
    # 
    def get_all_email_aliases(self):
        logger.info("Getting all email aliases.")
        aliases = dict()

        if self._db_conn:
            cur = self._db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            query = "SELECT ea.target_id, ea.local_part, ea.domain_id, ea.expire_date FROM email_address ea \
                     LEFT JOIN email_primary_address epa ON epa.address_id = ea.address_id \
                     WHERE epa.address_id is NULL ORDER BY ea.target_id;"
            cur.execute(query)
            rows = cur.fetchall()

            # get all domains
            domains = self.get_domains(cur)

            if (rows != None) and (len(domains) > 0):
                current_target_id = -1
                uname = ''
                for row in rows:
                    email_info = dict()
                    target_id = row['target_id']
                    local_part = row['local_part']
                    domain_id = row['domain_id']
                    expire_date = row['expire_date']
                    if expire_date != None:
                        expire_date = expire_date.strftime("%Y-%m-%d")

                    # build email address
                    email = local_part + "@" + domains[domain_id]

                    email_info['email'] = email
                    email_info['expire_date'] = expire_date

                    if target_id != current_target_id:
                        current_target_id = target_id
                        # get username that has this email alias
                        uname = self.get_username_from_target_id(target_id, cur)
                        if uname == None:
                            logger.error("Couldn't find username for alias with target_id %s. Ignoring all aliases with this target_id." 
                                        % target_id)
                            continue

                        # add username to the aliases dict
                        aliases[uname] = list()
                    else:
                        if uname == None:
                            # uname for this target_id could not be found, ignore this alias
                            continue

                    # add this email alias to aliases[uname]'s list of aliases
                    aliases[uname].append(email_info)
            logger.info("Finished getting email aliases for %s accounts." % len(aliases))
        else:
            logger.error("Couldn't get email aliases. No connection to %s database on %s." % (database, host))
        return aliases
