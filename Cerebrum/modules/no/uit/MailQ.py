#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

"""This module provides automatic mail template processing, mail queues and scheduled mass-sending of e-mail"""


import sys
import pickle

import mx.DateTime
from exceptions import Exception

import cerebrum_path
import cereconf

from Cerebrum import Errors
from Cerebrum import Utils
from Cerebrum.Utils import Factory

class MailQ(object):
    """
    The mailer class that implements the mailer system
    """


    # possible mailq status values
    NEW = 0
    ERR = 1


    def __init__(self, db, logger_name=None):
        self.db = db
        if True or logger_name is None:
            self._logger = Factory.get_logger("cronjob")
        else:
            self._logger = Factory.get_logger(logger_name)



    # adding msg to mailq
    def add(self, entity_id, template, parameters, scheduled=None):

        if scheduled is None:
            scheduled = mx.DateTime.now()
        else:
            scheduled = mx.DateTime.DateFrom(scheduled)

        # Prepare query to check if adding is necessary
        sel_query = """
        SELECT scheduled FROM mailq
        WHERE entity_id=:entity_id AND template=:template
        """
        sel_binds = {'entity_id': entity_id,
                     'template': template}

        # Prepare add query
        add_sql = """
              INSERT INTO mailq
              (entity_id, template, parameters, scheduled, status, status_time)
              VALUES
              (:entity_id, :template, :parameters, :scheduled, :status, now())
              """
        add_val = {'entity_id': entity_id,
               'template': template,
               'parameters': pickle.dumps(parameters),
               'scheduled': scheduled,
               'status': self.NEW}

        # Prepare update query
        upd_sql = """
              UPDATE mailq SET
                  parameters = :parameters, scheduled = :scheduled, status = :status, status_time = now()
              WHERE
                  entity_id = :entity_id AND template = :template
              """
        upd_val = {'entity_id': entity_id,
               'template': template,
               'parameters': pickle.dumps(parameters),
               'scheduled': scheduled,
               'status': self.NEW}


        try:
            res = self.db.query_1(sel_query, sel_binds)
            if scheduled < mx.DateTime.DateFrom(res):
                res = self.db.execute(upd_sql, upd_val)
                self._logger.info("Updated message in mailq")
                return True
            else:
                self._logger.info("Template %s is already scheduled at %s for entity %s" % (template, res, entity_id))
                return True
        except Errors.NotFoundError:
            res = self.db.execute(add_sql, add_val)
            self._logger.info("Added message to mailq")
            return True
        except Errors.DatabaseException, e:
            self._logger.error("Adding message to mailq failed: %s" % e)
            return False
        


    # deleting msg from mailq
    def delete(self, entity_id, template=None):

        tpl_sql = ""
        if template is not None:
            tpl_sql = " AND template=:template"

        sql = """
              DELETE FROM mailq
              WHERE entity_id=:entity_id %s
              """ % (tpl_sql)
        val = {'entity_id': entity_id,
               'template': template}

        try:
            self.db.execute(sql, val)
            self._logger.info("Deleted message from mailq")
            return True
        except Errors.DatabaseException, e:
            self._logger.error("Deleting message from mailq failed %s" % e)
            return False



    # updating msg in mailq
    def update(self, entity_id, template, parameters=None, scheduled=None, status=None):

        set_sql = []
        set_val = {}
        if parameters is not None:
            set_sql.append("parameters=:parameters")
            set_val['parameters'] = pickle.dumps(parameters)
        if scheduled is not None:
            set_sql.append("scheduled=:scheduled")
            set_val['scheduled'] = mx.DateTime.DateFrom(scheduled)
        if status is not None:
            if status == self.NEW or status == self.ERR:
                set_sql.append("status=:status")
                set_val['status'] = status
            else:
                self._logger.error("Illegal status (%s) given for mailq update for entity_id %s with template %s" % (status, entity_id, template))
                return False

        if len(set_sql) > 0:
            set_sql = "SET " + ", ".join(set_sql)

            sql = """
                  UPDATE mailq
                  %s
                  WHERE entity_id=:entity_id AND template=:template
                  """ % set_sql
            val = {'entity_id': entity_id,
                   'template': template}
            val.update(set_val)

            try:
                self.db.execute(sql, val)
                self._logger.info("Updated message in mailq")
                return True
            except Errors.DatabaseException, e:
                self._logger.error("Updating message in mailq failed: %s" % e)
                return False

        else:
            self._logger.error("Update with no content attempted for entity_id %s on template %s. Update ignored." % (entity_id, template))
            return False



    # search the mailq table with a variety of filters
    def search(self, entity_id=None, template=None, scheduled=None, status=None, status_time=None):
        where_sql = []
        where_val = {}
        if entity_id is not None:
            where_sql.append("entity_id=:entity_id")
            where_val['entity_id'] = entity_id
        if template is not None:
            where_sql.append("template=:template")
            where_val['template'] = template
        if scheduled is not None:
            where_sql.append("scheduled<=:scheduled")
            where_val['scheduled'] = mx.DateTime.DateFrom(scheduled)
        if status is not None:
            if status == self.NEW or status == self.ERR:
                where_sql.append("status=:status")
                where_val['status'] = status
            else:
                self._logger.error("Illegal status (%s) given for mailq search" % (status))
                return False
        if status_time is not None:
            where_sql.append("status_time<=:status_time")
            where_val['status_time'] = mx.DateTime.DateFrom(status_time)



        if len(where_sql) > 0:
            where_sql = "WHERE " + " AND ".join(where_sql)
        else:
            where_sql = ""

        sql = """
              SELECT *
              FROM mailq
              %s
              ORDER BY entity_id, scheduled
              """ % where_sql

        try:
            res = self.db.query(sql, where_val)
            return res
        except Errors.DatabaseException, e:
            self._logger.error("Searching mailq failed: %s" % e)
            raise Errors.DatabaseException, e


    # process the mailq table with a variety of filters
    def process(self, entity_id=None, template=None, scheduled=mx.DateTime.now(), status=None, status_time=None, master_template="Master_Default", dryrun=False):

        template_path = cereconf.CB_SOURCEDATA_PATH + '/templates/MailQ/'
        sender = cereconf.USER_NOTIFICATION_SENDER
        cc = None
        charset='utf-8'
        debug=dryrun

        languages = ['no', 'en']


        ac = Factory.get('Account')(self.db)
        en = Factory.get('Entity')(self.db)
        co = Factory.get('Constants')(self.db)

        valid_entity_types = [co.entity_account, ]
        list = self.search(entity_id, template, scheduled, status, status_time)

        current_entity_id = None
        for tmp in list:

            # Aggregating on entity_id - each entity_id will pass here only once because of order by clause in search function
            if tmp['entity_id'] != current_entity_id:

                current_entity_id = tmp['entity_id']
                msg_body = {}
                for lang in languages:
                   msg_body[lang] = ""
                empty_mail = True

                # Validade entity_id
                try:
                    en.clear()
                    try:
                        en.find(current_entity_id)
                    except Exception, e:
                        self._logger.error("Error retrieving information on entity with entity_id %s" % (current_entity_id))
                        continue

                    if en.const.EntityType(en.entity_type) not in valid_entity_types:
                        self._logger.error("Invalid entity_type (%s) placed in mailq. entity_id: %s" % (str(en.const.EntityType(en.entity_type)), current_entity_id))
                        continue

                    ac.clear()
                    try:
                        ac.find(current_entity_id)
                    except Exception, e:
                        self._logger.error("Error retrieving information on account with entity_id %s" % (current_entity_id))
                        continue


                    try:
                        recipient = ac.get_primary_mailaddress()
                    except Exception, e:
                        self.delete(current_entity_id)
                        self._logger.error("Error retrieving primary e-mailaddress for entity_id %s. Removing from queue!" % (current_entity_id))
                        
                        continue

                except Exception, e:
                    self._logger.error("Failed on entity_id: %s" % (current_entity_id))
                    continue

                # Aggregating pending sub-templates into a message body in scheduling order because of order by clause in search function
                for msg in list:
                    if msg['entity_id'] == current_entity_id:

                        try:

                            substitute = {}
                            substitute['brukernavn'] = ac.account_name
                            substitute['epost'] = recipient
                            substitute.update(pickle.loads(msg['parameters']))

                            self._logger.info("Preparing sub-template %s for user %s (%s)" % (msg['template'], ac.account_name, msg['entity_id']))

                            template = template_path + msg['template']
                            sub_message = {}
                            for lang in languages:
                                f = open(template + '.' + lang)
                                sub_message[lang] = "".join(f.readlines())
                                f.close()

                                for key in substitute:
                                    sub_message[lang] = sub_message[lang].replace("${%s}" % key, substitute[key])

                            for lang in languages:
                                if msg_body[lang] != "":
                                    msg_body[lang] = msg_body[lang] + "\n"
                                msg_body[lang] = msg_body[lang] + sub_message[lang]
                                empty_mail = False

                            # Delete sub-template from db
                            self.delete(msg['entity_id'], msg['template'])

                        except Exception, e:
                            self._logger.error("Error processing sub-template. entity_id: %s template: %s error: %s" % (msg['entity_id'],
                                                                                                               msg['template'],
                                                                                                               e))
                            # Update status to error
                            self.update(msg['entity_id'], msg['template'], parameters=None, scheduled=None, status=self.ERR)


                # Send aggregated mail
                if not empty_mail:
                    self._logger.info("Sending template %s to user %s (%s)" % (master_template, ac.account_name, current_entity_id))

                    substitute = {'brukernavn': ac.account_name, 'epost': recipient}
                    for lang in languages:
                        substitute['body_'+lang] = msg_body[lang]

                    debug_msg = Utils.mail_template(recipient,
                                                    template_path + master_template,
                                                    sender=sender,
                                                    cc=cc,
                                                    substitute=substitute,
                                                    charset=charset,
                                                    debug=debug)

                    if (dryrun):
                        self._logger.info(debug_msg)
