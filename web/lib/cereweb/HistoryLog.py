from Cerebrum.web.templates.HistoryLogTemplate import HistoryLogTemplate
from Cerebrum.web.TableView import TableView
from Cerebrum.web.utils import url
from Cerebrum.web.utils import object_link
from Cerebrum.Utils import Factory
ClientAPI = Factory.get_module("ClientAPI")
#from Cerebrum.web.Main import Main
import types
#import forgetHTML as html

def view_history_short(entity):
    # Could use some other template for 'short' view 
    template = HistoryLogTemplate()
    events = entity.get_history(5)
    id = entity.id
    table = _history_tableview(events)
    return template.viewHistoryLog(table, id)

def view_history(entity):
    template = HistoryLogTemplate()
    events = entity.get_history()
    table = _history_tableview(events)
    return template.viewCompleteHistoryLog(table)

def object_wrapper(object):
    """Wraps an object into a nice stringified link, if possible"""
    try:
        return str(object_link(object))
    except:
        try:
            return str(object)
        except:
            return repr(object)    

def _history_tableview(events):    
            
    table = TableView("timestamp", "icon", "who", "message")
    for change in events:
        if type(change.change_by) in types.StringTypes:
            who = change.change_by
        else:
            who = object_link(change.change_by)
        icon = get_icon_by_change_type(change.type.type)
        #server = req.session['server']
        #ent = ClientAPI.fetch_object_by_id(server, change.change_by)
        #who = ent.name            
        table.add(timestamp=change.date.Format("%Y-%m-%d"),
                  who=who,
                  # TODO: Should use hyperlinks on references 
                  message=change.message(object_wrapper), 
                  icon='<img src=\"'+url("img/"+icon)+'\">') 
    return table        
        
def get_icon_by_change_type(changetype):
    type = changetype.split("_")[-1]
    icon_map = {
        "add" : "add.png",
        "del" : "delete.png",
        "delete" : "delete.png",
        "rem" : "remove.png",
        "create" : "create.png",
        "mod" : "modify.png"
    }
    icon=icon_map.get(type, "blank.png")
    return icon
            
# arch-tag: c867b6bd-9a66-4967-9e41-fa88f669a641
