from Cheetah.Template import Template
from gettext import gettext

class InitTemplate(Template):
    _ = staticmethod(gettext)

# arch-tag: e4dc87f8-a862-4ff9-9800-479f82be8589
