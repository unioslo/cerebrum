import cerebrum_path
import forgetHTML as html
from Cerebrum.Utils import Factory
ClientAPI = Factory.get_module("ClientAPI")
from Cerebrum.web.templates.FullHistoryLogTemplate import FullHistoryLogTemplate
from Cerebrum.web.Main import Main
from gettext import gettext as _
from Cerebrum.web.utils import url

def index(req):
    page = Main(req)
    #page.menu.setFocus("group/search")
    viewhistory = FullHistoryLogTemplate()
    #page.content = viewhistory.form
    return page

def _create_view(req, id):
    """Creates a page with a view of the entire historylog
       based on an entity"""
    server = req.session['server']
    page = Main(req)
    try:
        entity = ClientAPI.fetch_object_by_id(server, id)
        entity.quarantines = entity.get_quarantines()
        entity.uri = req.unparsed_uri
    except:
        page.add_message(_("Could not load entity with id %s") % id)
        return (page, None)

    view = FullHistoryLogTemplate()
    page.content = lambda: view.viewFullHistoryLog(entity)
    return (page, entity)
                                                                                                                                                                            
def view(req, id):
    server = req.session['server']
    page = Main(req)
    entity = ClientAPI.fetch_object_by_id(server,id)
    (page, entity) = _create_view(req, id)
    return page

