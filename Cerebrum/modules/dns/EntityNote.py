# TODO: This class probably belongs directly below Cerebrum

class EntityNote(object):
    """Mix-in class for extra info that one might want to attach to an
    entity, and that one can only have one of."""

    def __fill_coldata(self, coldata):
        binds = coldata.copy()
        if binds['entity_id'] is None:
            binds['entity_id'] = self.entity_id
        del(binds['self'])
        if binds['note_type']:
            binds['note_type'] = int(binds['note_type'])
        cols = [ ("%s" % x, ":%s" % x) for x in binds.keys() ]
        return cols, binds

    def add_entity_note(self, note_type, data, entity_id=None):
        cols, binds = self.__fill_coldata(locals())
        self.execute("""
        INSERT INTO [:table schema=cerebrum name=dns_entity_note] (%(tcols)s)
        VALUES (%(binds)s)""" % {'tcols': ", ".join([x[0] for x in cols]),
                                 'binds': ", ".join([x[1] for x in cols])},
                     binds)

    def delete_entity_note(self, note_type=None, entity_id=None):
        cols, binds = self.__fill_coldata(locals())
        if not note_type:
            cols.remove(('note_type', ':note_type'))
        return self.execute("""
        DELETE FROM [:table schema=cerebrum name=dns_entity_note]
        WHERE %s""" % " AND ".join(["%s=%s" % x for x in cols]), binds)

    def get_entity_note(self, note_type, entity_id=None):
        cols, binds = self.__fill_coldata(locals())
        return self.query_1("""
        SELECT data
        FROM [:table schema=cerebrum name=dns_entity_note]
        WHERE entity_id=:entity_id AND note_type=:note_type""", binds)

    def update_entity_note(self, note_type, data, entity_id=None):
        cols, binds = self.__fill_coldata(locals())
        self.execute("""
        UPDATE [:table schema=cerebrum name=dns_entity_note]
        SET %(defs)s
        WHERE entity_id=:entity_id AND note_type=:note_type""" % {
            'defs': ", ".join(["%s=%s" % x for x in cols])}, binds)

