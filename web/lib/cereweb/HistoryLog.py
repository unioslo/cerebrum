from Cerebrum.web.templates.HistoryLogTemplate import HistoryLogTemplate
from Cerebrum.web.TableView import TableView
from Cerebrum.web.utils import url
from Cerebrum.Utils import Factory
ClientAPI = Factory.get_module("ClientAPI")
#from Cerebrum.web.Main import Main
import types
#import forgetHTML as html

def view_history_short(entity, id):
    # Could use some other template for 'short' view 
    template = HistoryLogTemplate()
    events = entity.get_history(5)
    table = _history_tableview(events)
    return template.viewHistoryLog(table, id)

def view_history(entity):
    template = HistoryLogTemplate()
    events = entity.get_history()
    table = _history_tableview(events)
    return template.viewCompleteHistoryLog(table)

def view_operator_history(session, limit=10):
    template = HistoryLogTemplate()
    server = session['server']
    events = session.get('operator_events')
    if not events:
        # get all  (TODO: Only one week or younger)
        events = ClientAPI.operator_history(server, )
    else:
        last_event = events[-1]
        # just get the new ones
        events.extend(ClientAPI.operator_history(server, last_event))

    # chop of the limit last events (if limit is 0 - all events)    
    events = events[-limit:]    
    session['operator_events'] = events
    table = _history_tableview(events)
    return template.viewHistoryLog(table)

def _history_tableview(events):    
    table = TableView("timestamp", "icon", "who", "message")
    icon_map = {
        "add" : "add.png",
        "del" : "delete.png",
        "delete" : "delete.png",
        "rem" : "remove.png",
        "create" : "create.png",
        "mod" : "modify.png"
    }
    for change in events:
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
        
    
