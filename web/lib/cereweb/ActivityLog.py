from gettext import gettext as _
import forgetHTML as html
from time import strftime

class ActivityLog(html.Division):
    def __init__(self):
        html.Division.__init__(self)
        self['class'] = "activitylog"
        self.append(html.Header(_("Activity log"), level=2))

    def add(self, entryline):
        entry = html.Division()
        entry.append(strftime("%Y-%m-%d %H:%M:%S"))
        entry.append(entryline)
        entry['class'] = 'entry'
        self._content.insert(1, entry)
