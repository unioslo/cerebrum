# -*- coding: utf-8 -*-
#
# Copyright 2019 University of Oslo, Norway
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
Implementation of mod_mailq.

This module provides automatic mail template processing, mail queues and
scheduled mass-sending of e-mail.
"""
import logging
import pickle
import warnings

import mx.DateTime
from exceptions import Exception

import cereconf

from Cerebrum import Errors
from Cerebrum import Utils
from Cerebrum.Utils import Factory

logger = logging.getLogger(__name__)


class MailQ(object):
    """
    The mailer class that implements the mailer system
    """

    # possible mailq status values
    NEW = 0
    ERR = 1

    def __init__(self, db, logger_name=None):
        self.db = db
        if logger_name:
            warnings.warn("Passing logger_name is deprecated",
                          DeprecationWarning,
                          stacklevel=2)

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
        add_val = {
            'entity_id': entity_id,
            'template': template,
            'parameters': pickle.dumps(parameters),
            'scheduled': scheduled,
            'status': self.NEW,
        }

        # Prepare update query
        upd_sql = """
          UPDATE mailq SET
            parameters = :parameters,
            scheduled = :scheduled,
            status = :status,
            status_time = now()
          WHERE
            entity_id = :entity_id AND template = :template
        """
        upd_val = {
            'entity_id': entity_id,
            'template': template,
            'parameters': pickle.dumps(parameters),
            'scheduled': scheduled,
            'status': self.NEW,
        }

        try:
            res = self.db.query_1(sel_query, sel_binds)
            if scheduled < mx.DateTime.DateFrom(res):
                res = self.db.execute(upd_sql, upd_val)
                logger.info("Updated message in mailq")
                return True
            else:
                logger.info("Template %s is already scheduled at %s for "
                            "entity %s", template, res, entity_id)
                return True
        except Errors.NotFoundError:
            res = self.db.execute(add_sql, add_val)
            logger.info("Added message to mailq")
            return True
        except Errors.DatabaseException as e:
            logger.error("Adding message to mailq failed: %s" % e)
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
            logger.info("Deleted message from mailq")
            return True
        except Errors.DatabaseException, e:
            logger.error("Deleting message from mailq failed %s" % e)
            return False

    # updating msg in mailq
    def update(self, entity_id, template, parameters=None, scheduled=None,
               status=None):

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
                logger.error("Illegal status (%s) given for mailq update for "
                             "entity_id %s with template %s", status,
                             entity_id, template)
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
                logger.info("Updated message in mailq")
                return True
            except Errors.DatabaseException, e:
                logger.error("Updating message in mailq failed: %s" % e)
                return False

        else:
            logger.error("Update with no content attempted for entity_id %s "
                         "on template %s. Update ignored.", entity_id,
                         template)
            return False

    # search the mailq table with a variety of filters
    def search(self, entity_id=None, template=None, scheduled=None,
               status=None, status_time=None):
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
                logger.error("Illegal status (%s) given for mailq search",
                             status)
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
            logger.error("Searching mailq failed: %s" % e)
            raise Errors.DatabaseException, e

    # process the mailq table with a variety of filters
    def process(self, entity_id=None, template=None,
                scheduled=mx.DateTime.now(), status=None, status_time=None,
                master_template="Master_Default", dryrun=False):

        template_path = cereconf.CB_SOURCEDATA_PATH + '/templates/MailQ/'
        sender = cereconf.USER_NOTIFICATION_SENDER
        cc = None
        charset = 'utf-8'
        debug = dryrun

        languages = ['no', 'en']

        ac = Factory.get('Account')(self.db)
        en = Factory.get('Entity')(self.db)
        co = Factory.get('Constants')(self.db)

        valid_entity_types = [co.entity_account, ]
        list = self.search(entity_id, template, scheduled, status, status_time)

        current_entity_id = None
        for tmp in list:

            # Aggregating on entity_id - each entity_id will pass here only
            # once because of order by clause in search function
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
                        logger.error("Error retrieving information on entity "
                                     "with entity_id %s", current_entity_id)
                        continue

                    _en_type = en.const.EntityType(en.entity_type)
                    if _en_type not in valid_entity_types:
                        logger.error("Invalid entity_type (%s) placed in "
                                     "mailq. entity_id: %s",
                                     str(en.const.EntityType(en.entity_type)),
                                     current_entity_id)
                        continue

                    ac.clear()
                    try:
                        ac.find(current_entity_id)
                    except Exception, e:
                        logger.error("Error retrieving information on account"
                                     " with entity_id %s", current_entity_id)
                        continue

                    try:
                        recipient = ac.get_primary_mailaddress()
                    except Exception, e:
                        self.delete(current_entity_id)
                        logger.error("Error retrieving primary e-mailaddress "
                                     "for entity_id %s. Removing from queue!",
                                     current_entity_id)
                        continue

                except Exception as e:
                    logger.error("Failed on entity_id: %s", current_entity_id)
                    continue

                # Aggregating pending sub-templates into a message body in
                # scheduling order because of order by clause in search
                # function
                for msg in list:
                    if msg['entity_id'] == current_entity_id:
                        try:
                            substitute = {}
                            substitute['brukernavn'] = ac.account_name
                            substitute['epost'] = recipient
                            substitute.update(pickle.loads(msg['parameters']))

                            logger.info("Preparing sub-template %s for user "
                                        "%s (%s)", msg['template'],
                                        ac.account_name,
                                        msg['entity_id'])

                            template = template_path + msg['template']
                            sub_message = {}
                            for lang in languages:
                                f = open(template + '.' + lang)
                                sub_message[lang] = "".join(f.readlines())
                                f.close()

                                for key in substitute:
                                    v = sub_message[lang]
                                    sub_message[lang] = v.replace(
                                        "${%s}" % key,
                                        substitute[key])

                            for lang in languages:
                                if msg_body[lang] != "":
                                    msg_body[lang] = msg_body[lang] + "\n"
                                msg_body[lang] = ''.join((
                                    msg_body[lang],
                                    sub_message[lang]))
                                empty_mail = False

                            # Delete sub-template from db
                            self.delete(msg['entity_id'], msg['template'])

                        except Exception as e:
                            logger.error(
                                "Error processing sub-template. "
                                "entity_id: %s template: %s error: %s",
                                msg['entity_id'], msg['template'], e)
                            # Update status to error
                            self.update(msg['entity_id'], msg['template'],
                                        parameters=None, scheduled=None,
                                        status=self.ERR)

                # Send aggregated mail
                if not empty_mail:
                    logger.info("Sending template %s to user %s (%s)",
                                master_template, ac.account_name,
                                current_entity_id)

                    substitute = {
                        'brukernavn': ac.account_name,
                        'epost': recipient,
                    }
                    for lang in languages:
                        substitute['body_'+lang] = msg_body[lang]

                    debug_msg = Utils.mail_template(
                        recipient,
                        template_path + master_template,
                        sender=sender,
                        cc=cc,
                        substitute=substitute,
                        charset=charset,
                        debug=debug)

                    if (dryrun):
                        logger.info(debug_msg)
