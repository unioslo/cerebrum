from Cerebrum.web.templates.HistoryLogTemplate import HistoryLogTemplate
from Cerebrum.web.TableView import TableView
from Cerebrum.web.utils import url
#from Cerebrum.Utils import Factory
#ClientAPI = Factory.get_module("ClientAPI")
#from Cerebrum.web.Main import Main
import types
#import forgetHTML as html

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
    icon_map = {
        "add" : "add.png",
        "del" : "delete.png",
        "delete" : "delete.png",
        "rem" : "remove.png",
        "create" : "create.png",
        "mod" : "modify.png"
    }
    for change in history:
        if type(change.change_by) in types.StringTypes:
            who = change.change_by
        else:
            # TODO: should be a hyperlink to the account
            who = str(change.change_by)
        icon=icon_map.get(change.type.type, "blank.png")
        #server = req.session['server']
        #ent = ClientAPI.fetch_object_by_id(server, change.change_by)
        #who = ent.name            
        table.add(timestamp=change.date.Format("%Y-%m-%d"),
                  who=who,
                  # TODO: Should use hyperlinks on references 
                  message=change.message(), 
                  icon='<img src=\"'+url("img/"+icon)+'\">') 
    return table        
        
    
