from Cheetah.Template import Template
from gettext import gettext

class InitTemplate(Template):
    _ = staticmethod(gettext)
