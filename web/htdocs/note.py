import cerebrum_path
from Cerebrum.Utils import Factory
ClientAPI = Factory.get_module("ClientAPI")
from gettext import gettext as _
from Cerebrum.web.utils import url

def add(req, entity, subject, description):
    """Adds a note to some entity"""
    server = req.session['server']
    entity = ClientAPI.fetch_object_by_id(server, entity)
    entity.add_note(subject, description)
    return "OK, added dings"

def delete(req, entity, id):
    server = req.session['server']
    entity = ClientAPI.fetch_object_by_id(server, entity)
    entity.remove_note(id)
    return "OK, Gone"
