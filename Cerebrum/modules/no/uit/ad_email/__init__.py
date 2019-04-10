# TODO: insert license text
from Cerebrum.DatabaseAccessor import DatabaseAccessor
from Cerebrum.Utils import Factory


class AdEmail(DatabaseAccessor):
    def __init__(self, database):
        super(AdEmail, self).__init__(database)
        self.const = Factory.get('Constants')(database)
        self.clconst = Factory.get('CLConstants')(database)
    # UIT Extension to manipulate AD EMAIL table (sets/overrides primary emails)

    # Add or update email entry for user
    def set_ad_email(self, local_part, domain_part):

        uname = self.get_account_name()

        # Query to check if update is necessary 
        sel_query = """
        SELECT account_name, local_part, domain_part from [:table schema=cerebrum name=ad_email]
        WHERE account_name=:account_name
        """
        sel_binds = {'account_name': uname}

        # Insert query
        ins_query = """
        INSERT INTO [:table schema=cerebrum name=ad_email]
        (account_name, local_part, domain_part, create_date, update_date)
        VALUES (:account_name, :local_part, :domain_part, [:now], [:now])
        """
        ins_binds = {'account_name':uname,
                     'local_part': local_part,
                     'domain_part': domain_part}
        
        # Update query
        upd_query = """
        UPDATE [:table schema=cerebrum name=ad_email]
        SET local_part=:local_part, domain_part=:domain_part, update_date=[:now]
        WHERE account_name=:account_name
        """
        upd_binds = { 'local_part' : local_part,
                      'domain_part' : domain_part,
                      'account_name': uname}

        try:
            res = self.query_1(sel_query, sel_binds)
            if res['local_part'] != local_part or res['domain_part'] != domain_part:
                res = self.execute(upd_query, upd_binds)
                self.logger.info("Updated ad_email table: %s to %s@%s" % (uname, local_part, domain_part))
            else:
                self.logger.info("ad_email table already up to date: %s had %s@%s"  % (uname, local_part, domain_part))
        except Errors.NotFoundError:
            res = self.execute(ins_query, ins_binds)
            self.logger.info("Inserted into ad_email table: %s to %s@%s" % (uname, local_part, domain_part))


    # Deletes ad email entry for user
    def delete_ad_email(self):

        uname = self.get_account_name()

        # Delete query
        sql = """
        DELETE from [:table schema=cerebrum name=ad_email]
        WHERE account_name=:account_name
        """
        binds = {'account_name': uname }
        self.execute(sql, binds)
        self.logger.info("Deleted %s from ad_email table" % (uname))


    # Searches ad email table
    def search_ad_email(self,account_name=None,local_part=None,domain_part=None):

        tables = list()
        where = list()
        binds = dict()
        if account_name:
            where.append('account_name=:account_name')
            binds['account_name']=account_name

        if local_part:
            where.append('local_part=:local_part')
            binds['local_part']=local_part
        
        if domain_part:
            where.append('domain_part=:domain_part')
            binds['domain_part']=domain_part

        where_str=""
        if where:
            where_str = "WHERE " + " AND ".join(where)
        sql = """
        SELECT account_name, local_part, domain_part
        FROM [:table schema=cerebrum name=ad_email]
        %s""" % (where_str)
        return self.query(sql,binds)
