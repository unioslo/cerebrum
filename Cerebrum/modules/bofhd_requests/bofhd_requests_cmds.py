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
import six
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommandBase
from Cerebrum.modules.bofhd_requests.request import BofhdRequests
from Cerebrum.modules.bofhd_requests.auth import RequestsAuth
from Cerebrum.modules.no.uio.bofhd_uio_cmds import format_time
from Cerebrum.modules.bofhd.errors import CerebrumError
from Cerebrum.modules import Email
from Cerebrum import Errors
from Cerebrum.modules.bofhd.cmd_param import (
    Command,
    DateTimeString,
    FormatSuggestion,
    Id,
    SimpleString,
)


class BofhdExtension(BofhdCommandBase):

    all_commands = {}
    hidden_commands = {}
    authz = RequestsAuth

    #
    # misc change_request <request-id> <datetime>
    #
    all_commands['misc_change_request'] = Command(
        ("misc", "change_request"),
        Id(help_ref="id:request_id"),
        DateTimeString())

    def misc_change_request(self, operator, request_id, datetime):
        if not request_id:
            raise CerebrumError('Request id required')
        if not datetime:
            raise CerebrumError('Date required')
        datetime = self._parse_date(datetime)
        br = BofhdRequests(self.db, self.const)
        old_req = br.get_requests(request_id=request_id)
        if not old_req:
            raise CerebrumError("There is no request with id=%r" % request_id)
        else:
            # If there is anything, it's at most one
            old_req = old_req[0]
        # If you are allowed to cancel a request, you can change it :)
        self.ba.can_cancel_request(operator.get_entity_id(), request_id)
        br.delete_request(request_id=request_id)
        br.add_request(operator.get_entity_id(),
                       datetime,
                       old_req['operation'],
                       old_req['entity_id'],
                       old_req['destination_id'],
                       old_req['state_data'])
        return "OK, altered request %s" % request_id

    #
    # misc list_bofhd_request_types
    #
    all_commands['misc_list_bofhd_request_types'] = Command(
        ("misc", "list_bofhd_request_types"),
        fs=FormatSuggestion(
            "%-20s %s", ("code_str", "description"),
            hdr="%-20s %s" % ("Code", "Description")
        ))

    def misc_list_bofhd_request_types(self, operator):
        br = BofhdRequests(self.db, self.const)
        result = []
        for row in br.get_operations():
            br_code = self.const.BofhdRequestOp(row['code_str'])
            result.append({
                'code_str': six.text_type(br_code).lstrip('br_'),
                'description': br_code.description,
            })
        return result

    #
    # misc cancel_request
    #
    all_commands['misc_cancel_request'] = Command(
        ("misc", "cancel_request"),
        SimpleString(help_ref='id:request_id'))

    def misc_cancel_request(self, operator, req):
        if req.isdigit():
            req_id = int(req)
        else:
            raise CerebrumError("Request-ID must be a number")
        br = BofhdRequests(self.db, self.const)
        if not br.get_requests(request_id=req_id):
            raise CerebrumError("Request ID %d not found" % req_id)
        self.ba.can_cancel_request(operator.get_entity_id(), req_id)
        br.delete_request(request_id=req_id)
        return "OK, %d canceled" % req_id

    #
    # misc list_requests
    #
    all_commands['misc_list_requests'] = Command(
        ("misc", "list_requests"),
        SimpleString(help_ref='string_bofh_request_search_by',
                     default='requestee'),
        SimpleString(help_ref='string_bofh_request_target',
                     default='<me>'),
        fs=FormatSuggestion(
            "%-7i %-10s %-16s %-16s %-10s %-20s %s",
            ("id", "requestee", format_time("when"), "op", "entity",
             "destination", "args"),
            hdr="%-7s %-10s %-16s %-16s %-10s %-20s %s" % (
                "Id", "Requestee", "When", "Op", "Entity", "Destination",
                "Arguments")
        ))

    def misc_list_requests(self, operator, search_by, destination):
        br = BofhdRequests(self.db, self.const)
        ret = []

        if destination == '<me>':
            destination = self._get_account(operator.get_entity_id(),
                                            idtype='id')
            destination = destination.account_name
        if search_by == 'requestee':
            account = self._get_account(destination)
            rows = br.get_requests(operator_id=account.entity_id, given=True)
        elif search_by == 'operation':
            try:
                destination = int(
                    self.const.BofhdRequestOp('br_' + destination))
            except Errors.NotFoundError:
                raise CerebrumError("Unknown request operation %s" %
                                    destination)
            rows = br.get_requests(operation=destination)
        elif search_by == 'disk':
            disk_id = self._get_disk(destination)[1]
            rows = br.get_requests(destination_id=disk_id)
        elif search_by == 'account':
            account = self._get_account(destination)
            rows = br.get_requests(entity_id=account.entity_id)
        else:
            raise CerebrumError("Unknown search_by criteria")

        for r in rows:
            op = self.const.BofhdRequestOp(r['operation'])
            dest = None
            ent_name = None
            if op in (self.const.bofh_move_user, self.const.bofh_move_request,
                      self.const.bofh_move_user_now):
                disk = self._get_disk(r['destination_id'])[0]
                dest = disk.path
            elif op in (self.const.bofh_move_give,):
                dest = self._get_entity_name(r['destination_id'],
                                             self.const.entity_group)
            elif op in (self.const.bofh_email_create,
                        self.const.bofh_email_delete):
                dest = self._get_entity_name(r['destination_id'],
                                             self.const.entity_host)
            elif op in (self.const.bofh_sympa_create,
                        self.const.bofh_sympa_remove):
                ea = Email.EmailAddress(self.db)
                if r['destination_id'] is not None:
                    ea.find(r['destination_id'])
                    dest = ea.get_address()
                ea.clear()
                try:
                    ea.find(r['entity_id'])
                except Errors.NotFoundError:
                    ent_name = "<not found>"
                else:
                    ent_name = ea.get_address()
            if ent_name is None:
                ent_name = self._get_entity_name(r['entity_id'],
                                                 self.const.entity_account)
            if r['requestee_id'] is None:
                requestee = ''
            else:
                requestee = self._get_entity_name(r['requestee_id'],
                                                  self.const.entity_account)
            ret.append({'when': r['run_at'],
                        'requestee': requestee,
                        'op': six.text_type(op),
                        'entity': ent_name,
                        'destination': dest,
                        'args': r['state_data'],
                        'id': r['request_id']
                        })
        ret.sort(lambda a, b: cmp(a['id'], b['id']))
        return ret
