import cerebrum_path
from Cerebrum.Utils import Factory
ClientAPI = Factory.get_module("ClientAPI")
from gettext import gettext as _
from Cerebrum.web.utils import redirect_object
from Cerebrum.web.utils import queue_message

def add(req, entity, subject, description):
    """Adds a note to some entity"""
    server = req.session['server']
    entity = ClientAPI.fetch_object_by_id(server, entity)
    entity.add_note(subject, description)
    queue_message(req, _("Added note '%s'") % subject)
    return redirect_object(req, entity, seeOther=True)

def delete(req, entity, id):
    """Removes a note"""
    server = req.session['server']
    entity = ClientAPI.fetch_object_by_id(server, entity)
    entity.remove_note(id)
    queue_message(req, _("Deleted note"))
    return redirect_object(req, entity, seeOther=True)

# arch-tag: a346491e-4e47-42c1-8646-391b6375b69f
