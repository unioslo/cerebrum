#!/usr/bin/env  python

import time

from Cerebrum.extlib import sets

import Cerebrum_core
import Cerebrum_core__POA
import Cerebrum_core.Errors

import Communication
import classes.Registry
import classes.Scheduler

com = Communication.get_communication()
registry = classes.Registry.get_registry()
scheduler = classes.Scheduler.get_scheduler()

GroupSearch = registry.GroupSearch
AccountSearch = registry.AccountSearch

class LOHandler(Cerebrum_core__POA.LOHandler):
    def get_all(self, group_name, tags):
        print group_name, tags
        search = GroupSearch()
        search.set_name(group_name) # FIXME: dette må være et eksakt søk. her er det mulig med *?%_
        groups = search.search()
        assert len(groups) <= 1

        if not groups:
            raise Exception('group not found') # hmm.. retunere not tomt i stedet.

        group = groups[0]
        print 'group found:', group.get_name()

        entity_list = {}

        def add_entity(entity):
            # sjekk om entity har en av taggene
            if not 1:
                return None
            id = entity.get_entity_id()
            if id in entity_list:
                return id

            attributes = []
            for i in entity.slots:
                if i.data_type in ('long', 'string'):
                    value = getattr(entity, 'get_' + i.name)()
                    attributes.append(Cerebrum_core.KeyValue(i.name, str(value)))

            type = entity.get_entity_type().get_name()

            print 'adding entity with id:', id
            entity_list[id] = Cerebrum_core.Entity(id, type, attributes)

            if type == 'group':
                add_group(entity)

            return id

        group_member_list = []

        def add_group(group):
            members = []
            for i in group.get_members():
                id = add_entity(i.get_member())
                if id is not None:
                    member = Cerebrum_core.GroupMember(group.get_entity_id(), i.get_operation().get_name(), id)
                    members.append(member)

        add_entity(group)

        entity_list = entity_list.items()
        entity_list.sort()


        return 0, [j for i, j in entity_list], group_member_list
