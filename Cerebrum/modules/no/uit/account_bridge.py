# -*- coding: utf-8 -*-
#
# Copyright 2016-2019 University of Tromso, Norway
#
# This file is part of Cerebrum.
#
# Cerebrum is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Cerebrum is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Cerebrum; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.
"""
Access data from another Cerebrum database.
"""
import logging

import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)
default_database = "cerebrum"
default_user = "cerebrum"
default_host = "caesar.uit.no"


def connect(database=default_database, user=default_user, host=default_host):
    conn = psycopg2.connect(database=database, user=user, host=host)
    conn.cursor_factory = psycopg2.extras.DictCursor
    logger.info("Connected to database %r", conn.dsn)
    return conn


class AccountBridge(object):
    """
    Class to use for getting information about accounts from the existing
    Cerebrum database on Caesar.  For use when adding accounts to the new
    Cerebrum database on Clavius.

    Use 'with' to instantiate the class, thus avoiding the need to close the
    database connection explicitly.  E.g.:

    .. code:: python

        with AccountBridge() as bridge:
            <do stuff here...>
            # when finished the database connection will be closed
    """

    def __init__(self, **kwargs):
        self._db_conn = connect(**kwargs)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close_db()

    def close_db(self):
        if self._db_conn:
            self._db_conn.close()
            logger.info("Closed connection to %r", self._db_conn.dsn)

    #############################################
    #
    # Unames
    #
    #############################################

    # NOTE that a person can have more than one account:
    # Sito employees can have two accounts if they are also students/employees
    # at uit.
    # Sito usernames are longer than 6 characters and end with 's'

    # list_unames(self, ssn)
    #
    #
    def list_unames(self, ssn):
        """
        List usernames.

        Gets username(s) for a person with the given ssn from the database.

        :param ssn: A ssn to get usernames for.

        :return:
            Returns empty list if person isn't found in the database.
            Returns None if database connection is down.
        """
        try:
            cur = self._db_conn.cursor()
            # get username from Caesar database
            query = """
            SELECT entity_name FROM entity_name
            WHERE entity_id IN
              (SELECT account_id FROM account_info
               WHERE owner_id IN
                (SELECT entity_id FROM entity_external_id
                 WHERE external_id = %(ssn)s));
            """
            cur.execute(query, {'ssn': ssn})
            rows = cur.fetchall()
            cur.close()
            return rows
        except Exception as e:
            logger.error("Unable to get uname: %s", e)
            return None

    def get_uname(self, ssn, sito=False):
        """
        Get username for a person with the given ssn.

        :param ssn: The ssn to get a username for
        :param sito: Gets SITO usernames if True.
        """
        uit_uname = None
        sito_uname = None
        for row in (self.list_unames(ssn) or ()):
            if (len(row["entity_name"]) > 6 and
                    row["entity_name"].endswith('s')):
                sito_uname = row["entity_name"]
                logger.debug("Found sito username=%r", row['entity_name'])
            elif (len(row["entity_name"]) == 6 and
                  row["entity_name"][3:5] == '99' and
                  row["entity_name"][5] in ('8', '9')):
                # Do not collect usernames on the form aaa99(8,9). these are
                # admin accounts and not to be included (they are soon to be
                # deleted from all systems)
                logger.debug("Found admin username=%r, ignoring",
                             row['entity_name'])
            else:
                uit_uname = row["entity_name"]
                logger.debug("Found uit username=%r", row['entity_name'])

        if sito:
            return sito_uname
        else:
            return uit_uname

    def get_uit_uname(self, ssn):
        """
        Get uit username for a person.

        :return: The username, or None if no valid username is found.
        """
        return self.get_uname(ssn, sito=False)

    def get_sito_uname(self, ssn):
        """
        Get sito username for a person.

        :return: The username, or None if no valid username is found.
        """
        return self.get_uname(ssn, sito=True)

    #############################################
    #
    # Passwords
    #
    #############################################

    def get_auth_data(self, username):
        """
        Gets authentication data for the account with the given username.

        :return:
            Returns a list of rows of authentication data.  The data in each
            row can be referred to by their column names, method and auth_data.
            Returns 'None' if no authentication data was found for the given
            username.
        """
        stmt = """
        SELECT method, auth_data FROM account_authentication
        WHERE account_id = (
            SELECT entity_id FROM entity_name
            WHERE entity_name = %(username)s);
        """
        binds = {'username': username}
        try:
            cur = self._db_conn.cursor()
            cur.execute(stmt, binds)
            rows = cur.fetchall()
            cur.close()
            return rows or None
        except Exception as e:
            logger.error("Unable to get password for username=%r: %s",
                         username, e)
            return None

    #############################################
    #
    # Email addresses
    #
    #############################################

    def get_email(self, username):
        """
        Gets email address for account with the given username and returns it.

        :return:
            An email address, or None if something goes wrong.
        """
        stmt = """
        SELECT e.local_part, d.domain FROM email_address e
        JOIN email_domain d ON e.domain_id = d.domain_id
        WHERE e.address_id = (
          SELECT address_id FROM email_primary_address
          WHERE target_id = (
            SELECT target_id FROM email_target
            WHERE target_entity_id = (
              SELECT entity_id FROM entity_name
              WHERE entity_name = %(username)s)));
        """
        binds = {'username': username}
        try:
            cur = self._db_conn.cursor()
            cur.execute(stmt, binds)
            row = cur.fetchone()
            if row:
                local_part = row["local_part"]
                domain = row["domain"]
                email = local_part + "@" + domain
            else:
                logger.warn("Email information not found for %s", username)
                email = None
            cur.close()
            return email
        except Exception as e:
            logger.error("Unable to get email address for username=%r: %s",
                         username, e)
            return None

    def get_domains(self, db_cursor):
        """
        Get a mapping from domain_id to domain.

        :return:
            Returns a dict of all domain ids with their value.
            Returns an empty dict if something goes wrong.

        Used by get_all_primary_emails() and get_all_email_aliases()
        """
        stmt = "SELECT domain_id, domain FROM email_domain;"
        db_cursor.execute(stmt)

        domains = dict(
            (r['domain_id'], r['domain'])
            for r in (db_cursor.fetchall() or ()))

        if not domains:
            logger.error("Found no domains in database.")

        return domains

    def get_username_from_target_id(self, target_id, db_cursor):
        """
        Get username from email target.

        :return:
            Returns username connected to a given target_id
            Returns None if something goes wrong

        Used by get_all_primary_emails() and get_all_email_aliases()
        """
        stmt = """
        SELECT entity_name FROM entity_name
        WHERE entity_id = (
          SELECT target_entity_id FROM email_target \
          WHERE target_id = %(target_id)s);
        """
        binds = {'target_id': target_id}
        db_cursor.execute(stmt, binds)
        result = db_cursor.fetchone()
        if result:
            return result['entity_name']
        else:
            return None

    def get_all_primary_emails(self):
        """
        Get all primary email addresses.

        :rtype: dict
        :return:
            A mapping from username to primary email address and expire date:
            (format: {<username> : {'email' : <EMAIL ADDRESS>,
                                    'expire_date' : <EXPIRE DATE>}})
            Returns an empty dict if something goes wrong.
        """
        logger.info("Getting all primary emails.")
        emails = dict()

        stmt = """
        SELECT a.target_id, a.local_part, a.domain_id, a.expire_date
        FROM email_address a
        WHERE EXISTS (
          SELECT * from email_primary_address p
          WHERE a.address_id = p.address_id);
        """
        try:
            cur = self._db_conn.cursor()
            cur.execute(stmt)
            rows = cur.fetchall()
            if not rows:
                raise ValueError("no email addresses")

            # get all domains
            domains = self.get_domains(cur)
            if not domains:
                raise ValueError("no email domains")

            for row in rows:
                target_id = row['target_id']
                local_part = row['local_part']
                domain_id = row['domain_id']
                expire_date = row['expire_date']
                if expire_date:
                    expire_date = expire_date.strftime("%Y-%m-%d")

                # get username that has this email address
                uname = self.get_username_from_target_id(target_id, cur)
                if not uname:
                    logger.error("No username for target_id=%r, ignoring",
                                 target_id)
                    continue

                # add email info to emails dict
                emails[uname] = {
                    'email': local_part + "@" + domains[domain_id],
                    'expire_date': expire_date,
                }
            logger.info("Finished getting %s primary email addresses",
                        len(emails))
        except Exception as e:
            logger.error("Unable to fetch primary email addresses: %s", e)

        return emails

    def get_email_aliases(self, username):
        """
        Gets email aliases for a given account.

        :rtype: list
        :return:
            A list of email aliases.
            Note: the returned list will not contain primary email address.
            Returns an empty list if something goes wrong, or no aliases are
            found.
        """
        stmt = """
        SELECT a.address_id, a.local_part, d.domain FROM email_address a
        JOIN email_domain d ON a.domain_id = d.domain_id
        WHERE a.target_id = (
            SELECT target_id FROM email_target
            WHERE target_entity_id = (
              SELECT entity_id FROM entity_name
              WHERE entity_name = %(username)s))
        AND NOT EXISTS (
          SELECT * from email_primary_address
          WHERE address_id=a.address_id);
        """
        binds = {'username': username}
        try:
            cur = self._db_conn.cursor()
            cur.execute(stmt, binds)

            aliases = [
                row['local_part'] + "@" + row["domain"]
                for row in cur.fetchall()]
            cur.close()

            if not aliases:
                logger.warning("No email aliases for username=%r", username)
            return aliases

        except Exception as e:
            logger.error("Unable to get email aliases for username=%r: %e",
                         username, e)
            return []

    def get_all_email_aliases(self):
        """
        Get a mapping from username to email aliases.

        :rtype: dict
        :return:
             Returns a dict of all email aliases with username as key
             (format: {<username>: list of {'email': <EMAIL ADDRESS>,
                                            'expire_date' : <EXPIRE DATE>}})
            Returns an empty dict if something goes wrong.
        """
        logger.info("Getting all email aliases.")
        aliases = dict()
        stmt = """
        SELECT ea.target_id, ea.local_part, d.domain, ea.expire_date
        FROM email_address ea
        JOIN email_domain d on ea.domain_id = d.domain_id
        LEFT JOIN email_primary_address epa
        ON epa.address_id = ea.address_id
        WHERE epa.address_id is NULL
        ORDER BY ea.target_id;
        """
        try:
            cur = self._db_conn.cursor()
            cur.execute(stmt)
            rows = cur.fetchall()
            current_target_id = -1
            uname = ''
            for row in (rows or ()):
                target_id = row['target_id']
                local_part = row['local_part']
                domain = row['domain']
                expire_date = row['expire_date']
                if expire_date:
                    expire_date = expire_date.strftime("%Y-%m-%d")

                if target_id != current_target_id:
                    current_target_id = target_id
                    # get username that has this email alias
                    uname = self.get_username_from_target_id(target_id,
                                                             cur)
                    if uname is None:
                        logger.error("Couldn't find username for alias "
                                     "with target_id %s. Ignoring all "
                                     "aliases with this target_id.",
                                     target_id)
                        continue

                    # add username to the aliases dict
                    aliases[uname] = list()
                elif not uname:
                    # uname for this target_id could not be found, ignore
                    # this alias
                    continue

                # add this email alias to aliases[uname]'s list of aliases
                aliases[uname].append({
                    'email': local_part + "@" + domain,
                    'expire_date': expire_date,
                })
            logger.info("Finished getting email aliases for %s accounts.",
                        len(aliases))
        except Exception as e:
            logger.error("Unable to fetch email aliases: %s", e)
        return aliases
