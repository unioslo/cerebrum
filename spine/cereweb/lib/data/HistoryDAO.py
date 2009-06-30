from lib.data.HistoryDTO import HistoryDTO
from lib.data.AccountDAO import AccountDAO
import cerebrum_path
from Cerebrum import Utils
from Cerebrum.Errors import NotFoundError
Database = Utils.Factory.get("Database")
Constants = Utils.Factory.get("Constants")
Entity = Utils.Factory.get("Entity")

class HistoryDAO(object):
    def __init__(self, db=None):
        if db is None:
            db = Database()

        self.db = db
        self.co = Constants(db)
        self.ac = AccountDAO(self.db)

    def get_entity_history_tail(self, id):
        return self.get_entity_history(id)[-5:]

    def get_entity_history(self, id):
        events = []
        
        for cerebrum_event in self.db.get_log_events(subject_entity=id):
            event_type = self._get_event_type(cerebrum_event)
            event = HistoryDTO(cerebrum_event, event_type)
            event.creator = self._get_creator(cerebrum_event)
            events.append(event)
        return events

    def _get_event_type(self, event):
        change_type_id = event['change_type_id']
        return self.co.ChangeType(change_type_id)

    def _get_creator(self, event):
        if event.change_by:
            return self.ac.get_entity(event.change_by)
        elif event.change_program:
            return event.change_program
        return "unknown"
