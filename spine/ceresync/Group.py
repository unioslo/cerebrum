import sets
import SpineClient

def get_groups(tr, const):
    def get_members(group, group_members):
        """Return members for a group.
        
        Algorithm to resolve union/difference/intersecion membership 
        """
        unions = sets.Set()
        intersects = sets.Set()
        differences = sets.Set()

        for entity, operation in group_members[group]:
            if entity.type is const.group_type:
                members = get_members(entity.name, group_members)
            else:
                members = sets.Set([(entity.name, entity.type)])

            if operation == const.union_type:
                unions.update(members)
            elif operation == const.intersection_type:
                intersects.update(members)
            elif operation == const.difference_type:
                differences.update(members)

        if intersects:
            unions.intersection_update(intersects)
        if differences:
            unions.difference_update(differences)

        return unions

    group_members = {}

    def add_group_member(groupname, member, operation):
        assert type(groupname) == str
        try:
            group_members[groupname].append((member, operation))
        except KeyError:
            group_members[groupname] = [(member, operation)]


    # first we get all group-group relations
    search = SpineClient.Search(tr)
    group = search.get_group_searcher('group')
    member = search.get_group_searcher('member')
    gm = search.get_group_member_searcher('gm')

    gm.add_join('group', group, '')
    gm.add_join('member', member, '')
    for i in search.dump(gm):
        add_group_member(i['group'].name, i['member'], i['gm'].operation)

    # then all group-account relations where account is member of <spread>
    search = SpineClient.Search(tr)
    group = search.get_group_searcher('group')
    member = search.get_account_searcher('member')
    gm = search.get_group_member_searcher('gm')
    entityspreads = search.get_entity_spread_searcher('spread', spread=const.account_spread, entity_type=const.account_type)

    gm.add_join('group', group, '')
    gm.add_join('member', member, '')
    member.add_join('', entityspreads, 'entity')
    for i in search.dump(gm):
        add_group_member(i['group'].name, i['member'], i['gm'].operation)

    # resolve membership
    members = {}
    for group in group_members.keys():
        members[group] = get_members(group, group_members)

    def get_flat(group):
        for member, type in members.get(group, ()):
            if type == const.group_type:
                for member in get_flat(member):
                    yield member
            else:
                yield member

    search = SpineClient.Search(tr)

    groups = search.get_group_searcher('group')

    if const.group_spread is not None:
        entityspreads = search.get_entity_spread_searcher('spread', spread=const.group_spread, entity_type=const.group_type)
        groups.add_join('', entityspreads, 'entity')

    for group in search.dump(groups):
        flat = list(sets.Set(get_flat(group['group'].name)))
        flat.sort()
        yield group, flat

# arch-tag: 8ffdd04e-47f8-11da-8410-b65d5173994a
