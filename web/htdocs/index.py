import forgetHTML as html
html.Element.__call__ = html.Element.__str__

from Cerebrum.web.templates.MainTemplate import MainTemplate
from Cerebrum.web.ActivityLog import ActivityLog
from Cerebrum.web.WorkList import WorkList
#from mod_python.Session import Session

def index(req, tag="p"):
    req.content_type="text/html"
#    session = Session(req)
    body = MainTemplate()
    body.title = "Heia du der"
    table = html.SimpleTable(header="row")
    table.add("Hei", "du", "der")
    table.add("Dette", "er")
    table.add("Jævlig", "bra", "altså")
    body.content = table
    #body.bottom = lambda: "<%s>Heia du</%s>" % (tag, tag)
#    log = session.setdefault('log', ActivityLog())
    log = ActivityLog()
    log.add("Retrieved session")
    log.add("Said hello")
    log.add("And finally goodbye")

    worklist = WorkList()
    
    body.bottom = worklist
    body.menu = lambda: "Heia du<br/>\n" * 10
    return body
