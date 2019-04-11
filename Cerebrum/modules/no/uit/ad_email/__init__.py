# TODO: insert license text
import logging

from Cerebrum import Errors
from Cerebrum.DatabaseAccessor import DatabaseAccessor
from Cerebrum.Utils import Factory, argument_to_sql

__version__ = '1.0'

logger = logging.getLogger(__name__)


class AdEmail(DatabaseAccessor):
    def __init__(self, database):
        super(AdEmail, self).__init__(database)
        self.const = Factory.get('Constants')(database)
        self.clconst = Factory.get('CLConstants')(database)

    def _update_ad_email(self, account_name, local_part, domain_part):
        query = """
        UPDATE [:table schema=cerebrum name=ad_email]
        SET local_part=:local_part, domain_part=:domain_part,
            update_date=[:now]
        WHERE account_name=:account_name
        """
        binds = {'local_part': local_part,
                 'domain_part': domain_part,
                 'account_name': account_name}
        self.execute(query, binds)

    def _insert_ad_email(self, account_name, local_part, domain_part):
        query = """
        INSERT INTO [:table schema=cerebrum name=ad_email]
        (account_name, local_part, domain_part, create_date, update_date)
        VALUES (:account_name, :local_part, :domain_part, [:now], [:now])
        """
        binds = {'local_part': local_part,
                 'domain_part': domain_part,
                 'account_name': account_name}
        self.execute(query, binds)

    def search_ad_email(self, account_name=None, local_part=None,
                        domain_part=None):
        """Search ad email table"""
        binds = dict()
        conditions = []

        if account_name:
            cond = argument_to_sql(account_name, 'account_name', binds)
            conditions.append(cond)
        if local_part:
            cond = argument_to_sql(local_part, 'local_part', binds)
            conditions.append(cond)
        if domain_part:
            cond = argument_to_sql(domain_part, 'domain_part', binds)
            conditions.append(cond)

        where = ('WHERE ' + ' AND '.join(conditions)) if conditions else ''
        query = """
        SELECT account_name, local_part, domain_part
        FROM [:table schema=cerebrum name=ad_email]
        """ + where
        return self.query(query, binds)

    def set_ad_email(self, account_name, local_part, domain_part):
        """Set/update ad_email for an account."""
        try:
            res = self.search_ad_email(account_name=account_name)[0]
            if not (res['local_part'] == local_part and
                    res['domain_part'] == domain_part):
                self._update_ad_email(account_name, local_part, domain_part)
                logger.debug("updated ad_email for account:%s", account_name)
        except Errors.NotFounderror:
            self._insert_ad_email(account_name, local_part, domain_part)
            logger.debug("inserted ad_email for account:%s", account_name)

    def delete_ad_email(self, account_name):
        """Delete ad email entry for the account"""
        query = """
        DELETE from [:table schema=cerebrum name=ad_email]
        WHERE account_name=:account_name
        """
        binds = {'account_name': account_name}
        self.execute(query, binds)
        logger.debug("deleted ad_email for account:%s", account_name)
