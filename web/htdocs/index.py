import forgetHTML as html
html.Element.__call__ = html.Element.__str__

from Cerebrum.web.templates.MainTemplate import MainTemplate
from Cerebrum.web import ActivityLog
from Cerebrum.web.WorkList import WorkList
from Cerebrum.web.SideMenu import SideMenu

def index(req, tag="p"):
    req.content_type="text/html"
    body = MainTemplate()
    body.title = "Cereweb"
    table = html.SimpleTable(header="row")
    table.add("Her", "kommer en", "velkomsthilsen")
    table.add("Dette", "er")
    table.add("Ganske", "bra", "altså")
    body.content = table

    log = ActivityLog()
    body.activitylog = log

    worklist = WorkList()
    body.worklist = worklist


    sidemenu = SideMenu()
    body.menu = sidemenu


    return body
