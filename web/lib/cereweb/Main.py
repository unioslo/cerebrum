from Cerebrum.web.templates.MainTemplate import MainTemplate
from Cerebrum.web import ActivityLog
from Cerebrum.web.WorkList import WorkList
from Cerebrum.web.SideMenu import SideMenu

class Main(MainTemplate):
    def __init__(self, req):
        MainTemplate.__init__(self)
        self.session = req.session
        self.prepare_session()
        self.menu = SideMenu()
        self.worklist = self.session['worklist']
        #self.activitylog = self.session['activitylog']
        #self.activitylog = lambda: ActivityLog.view_operator_history(self.session)

    def add_message(self, message, error=False):
        """Adds a message on top of page. If error is true, the 
        message will be highlighted as an error"""
        self.messages.append((message, error))

    def prepare_session(self):    
        #if not self.session.has_key("activitylog"):
        #    self.session['activitylog'] = ActivityLog() 
        if not self.session.has_key("worklist"):
            self.session['worklist'] = WorkList() 
        self.prepare_messages()
    
    def prepare_messages(self):        
        self.messages = []
        queued_messages = self.session.get("messages")
        if not queued_messages:
            return
        for (message, error) in queued_messages:
            self.add_message(message, error)
        # We've moved them from the queue to be shown on the page    
        del self.session['messages']    
        
    def setFocus(self, *args):
        self.menu.setFocus(*args)    
        


# arch-tag: 3f246425-25b1-4e28-a969-3f04c31264c7
