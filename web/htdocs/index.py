import forgetHTML as html
html.Element.__call__ = html.Element.__str__

from Cerebrum.web.templates.MainTemplate import MainTemplate
from Cerebrum.web.ActivityLog import ActivityLog
from Cerebrum.web.WorkList import WorkList
from Cerebrum.web.SideMenu import SideMenu

def index(req, tag="p"):
    req.content_type="text/html"
    body = MainTemplate()
    body.title = "Heia du der"
    table = html.SimpleTable(header="row")
    table.add("Hei", "du", "der")
    table.add("Dette", "er")
    table.add("Jævlig", "bra", "altså")
    body.content = table

    log = ActivityLog()
    log.add("Retrieved session")
    log.add("Said hello")
    log.add("And finally goodbye")
    body.activitylog = log

    worklist = WorkList()
    body.worklist = worklist


    sidemenu = SideMenu()
    body.menu = sidemenu


    return body
