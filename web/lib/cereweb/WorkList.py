from Cerebrum.web.templates.WorkListTemplate import WorkListTemplate

import forgetHTML as html

# subclass Division to be included in a division..
class WorkList(html.Division):
    def __init__(self):
        self.remembered = []
        self.selected = []
    def addEntity(self, id):
        object = APImannen.getEntity(id)
        self.remembered.append(object)
    def output(self):
        template = WorkListTemplate()
        objects = []
        for object in self.remembered:
            view = str(object)
            key = object.getEntityID()
            objects.append( (key, view) )
        selected = [object.getEntityID() for object in self.selected]       
        actions = self.getActions()
        return template.worklist(objects, actions, selected)
    def getActions(self):
        actions = []
        actions.append(("view", "View"))
        actions.append(("edit", "Edit"))
        actions.append(("delete", "Delete"))
        actions.append(("fix", "Fix it"))
        return actions
            

