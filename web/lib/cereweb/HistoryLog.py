from Cerebrum.web.templates.HistoryLogTemplate import HistoryLogTemplate
from Cerebrum.web.TableView import TableView
import types

def view_history_short(entity):
    # Could use some other template for 'short' view 
    template = HistoryLogTemplate()
    table = _history_tableview(entity, 5)
    return template.viewHistoryLog(table)

def view_history(entity):
    template = HistoryLogTemplate()
    table = _history_tableview(entity)
    return template.viewHistoryLog(table)

def _history_tableview(entity, max_entries=None):    
    history = entity.get_history(max_entries)
    table = TableView("timestamp", "icon", "who", "message")
    for change in history:
        if type(change.change_by) in types.StringTypes:
            who = change.change_by
        else:
            # TODO: should be a hyperlink to the account
            who = str(change.change_by)    
        table.add(timestamp=change.date.Format("%Y-%m-%d"),
                  who=who,
                  # TODO: Should use hyperlinks on references 
                  message=change.message(), 
                  #TODO: should be an icon reference!
                  icon="") 
    return table        
        
    
