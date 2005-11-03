import SpineClient

def get_quarantines(tr, const):
    quarantines = {}
    def add_quarantine(obj):
        # FIXME: driter disable_until
        try:
            quarantines[obj['entity'].id].append(obj['q'])
        except KeyError:
            quarantines[obj['entity'].id] = [obj['q']]

    now = tr.get_commands().get_date_now()

    for spread in (const.account_spread, const.group_spread, const.person_spread):
        if spread is None:
            continue
        search = SpineClient.Search(tr)
        q = search.entity_quarantine('q', start_date_less_than=now)
        s = search.entity_spread('spread', spread=spread, entity_type=spread.get_entity_type())
        e = search.entity('entity')
        q.add_join('entity', s, 'entity')
        q.add_join('entity', e, '')

        q.set_end_date_exists(False)
        for i in search.dump(q):
            add_quarantine(i)
        q.set_end_date_exists(True)
        q.set_end_date_more_than(now)
        for i in search.dump(q):
            add_quarantine(i)

    return quarantines

# arch-tag: 90bb2766-47f8-11da-9f14-4ce06d1416d0
