from Cerebrum.web.templates.HistoryLogTemplate import HistoryLogTemplate
from Cerebrum.web.TableView import TableView
import types

def view_history(entity):
    template = HistoryLogTemplate()
    history = entity.get_history()
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
    return template.viewHistoryLog(table)
    
