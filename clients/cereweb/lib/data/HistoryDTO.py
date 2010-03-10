from lib.data.DTO import DTO

class HistoryDTO(DTO):
    def __init__(self, event=None, event_type=None):
        if event is None or event_type is None:
            return

        self.id = event['change_id']
        self.type = event_type.type
        self.message = event_type.type
        self.category = event_type.category
        self.timestamp = event['tstamp']
        self.subject_entity = event['subject_entity']
        self.dest_entity = event['dest_entity']
        self.change_params = event['change_params']
