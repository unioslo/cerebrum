from Cerebrum.web.templates.MainTemplate import MainTemplate
from Cerebrum.web import ActivityLog
from Cerebrum.web.WorkList import WorkList
from Cerebrum.web.SideMenu import SideMenu

class Main(MainTemplate):
    def __init__(self, req):
        MainTemplate.__init__(self)
        self.session = req.session
        self.prepareSession()
        self.menu = SideMenu()
        self.worklist = self.session['worklist']
        #self.activitylog = self.session['activitylog']
        self.activitylog = lambda: ActivityLog.view_operator_history(self.session)
        self.messages = [] # reset each time =)

    def add_message(self, message, error=False):
        """Adds a message on top of page. If error is true, the 
        message will be highlighted as an error"""
        self.messages.append((message, error))

    def prepareSession(self):    
        #if not self.session.has_key("activitylog"):
        #    self.session['activitylog'] = ActivityLog() 
        if not self.session.has_key("worklist"):
            self.session['worklist'] = WorkList() 
        
    def setFocus(self, *args):
        self.menu.setFocus(*args)    
        

