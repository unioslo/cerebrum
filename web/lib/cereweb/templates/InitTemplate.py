from Cheetah.Template import Template
from gettext import gettext

class InitTemplate(Template):
    _ = staticmethod(gettext)

# arch-tag: 463ae14b-2f10-43e3-8019-9b1e33b7be37
