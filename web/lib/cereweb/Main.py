from Cerebrum.web.templates.MainTemplate import MainTemplate
from Cerebrum.web.ActivityLog import ActivityLog
from Cerebrum.web.WorkList import WorkList
from Cerebrum.web.SideMenu import SideMenu

class Main(MainTemplate):
    def __init__(self, req):
        MainTemplate.__init__(self)
        self.session = req.session
        self.prepareSession()
        self.menu = SideMenu()
        self.worklist = self.session['worklist']
        self.activitylog = self.session['activitylog']
    def prepareSession(self):    
        if not self.session.has_key("activitylog"):
            self.session['activitylog'] = ActivityLog() 
        if not self.session.has_key("worklist"):
            self.session['worklist'] = WorkList() 
        
    def setFocus(self, *args):
        self.menu.setFocus(*args)    
        

