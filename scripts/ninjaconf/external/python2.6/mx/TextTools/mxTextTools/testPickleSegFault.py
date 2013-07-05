from mx.TextTools import *
import pickle

# This works fine:

tags = (
    (None, Is, 'a'),
)
        
t = TagTable(tags)
print type(t)
s = pickle.dumps(t)
print pickle.loads(s)
        
# But this crashes ...
        
tags = (
    (None, Is, u'\u03a3'),
)
                
t = UnicodeTagTable(tags)
print type(t)
s = pickle.dumps(t)
print pickle.loads(s)

