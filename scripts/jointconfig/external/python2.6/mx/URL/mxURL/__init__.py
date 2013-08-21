from mxURL import *
from mxURL import __version__

# Python part of module initialization
import mimetypes
mimemap = mimetypes.types_map
setmimedict(mimemap)
del mimetypes
