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
GroupMemberSearch = registry.GroupMemberSearch
AccountSearch = registry.AccountSearch
ChangeEventSearch = registry.ChangeEventSearch

class LOHandler(Cerebrum_core__POA.LOHandler):
    def __init__(self, client):
        self.client = client

    def get_all(self, group_name, group_tags, entity_tags):
        searcher = GroupMemberSearch()
        searcher.set_include_subgroups(True)
        searcher.set_include_parentgroups(True)

        # finne gruppe
        if group_name:
            group_search = GroupSearch()
            # FIXME: dette må være et eksakt søk. her er det mulig med *?%_
            group_search.set_name(group_name)
            groups = group_search.search()
            assert len(groups) <= 1

        if not groups:
            raise Exception('group not found') # hmm.. retunere noe tomt i stedet.

        # FIXME: finne tags
        group_tags = []
        entity_tags = []


        searcher.set_group(groups[0])
        if group_tags:
            searcher.set_group_tags(group_tags)
        if entity_tags:
            searcher.set_member_tags(entity_tags)

        entities = {}
        group_members = []

        def add_entity(entity):
            id = entity.get_entity_id()

            if id not in entities:
                attributes = []
                for i in entity.slots:
                    if i.data_type in ('long', 'string'): # TODO: fikse støtte for konstanter
                        value = getattr(entity, 'get_' + i.name)()
                        attributes.append(Cerebrum_core.KeyValue(i.name, str(value)))

                entity_type = entity.get_entity_type().get_name()

                entities[id] = Cerebrum_core.Entity(id, entity_type, attributes)
            
        for group_member in searcher.search():
            group = group_member.get_group()
            operation = group_member.get_operation().get_name()
            member = group_member.get_member()

            add_entity(group)
            add_entity(member)

            g = Cerebrum_core.GroupMember(group.get_entity_id(), operation, member.get_entity_id())
            group_members.append(g)


        entities = entities.items()
        entities.sort()

        change_event = self.get_lastest_change_event()

        return change_event.get_id(), [j for i, j in entities], group_members

    def get_lastest_change_event(self):
        # FIXME: ChangeEventSearch trenger mer funksjonalitet
        return ChangeEventSearch('latest').search()[-1]

# arch-tag: ad03a9db-fe3f-4e1a-b130-4ad767579e93
