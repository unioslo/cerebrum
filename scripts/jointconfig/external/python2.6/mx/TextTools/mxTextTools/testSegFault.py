#
# Bug (segfault) reported by
# Date: Wed, 25 Jan 2006 14:29:34 +0100
# From: Reinhard Engel <nc-engelre@netcologne.de>
#
from mx.TextTools import *

tagtable = (
    (None, Word, '<p'),
    (None, IsNot, '>', +1, 0),
    (None, Is, '>', MatchFail, MatchOk),
    )
            
# This works
str1 = '<p class="nummer" abc>'
print tag(str1, tagtable)
            
# This segfaults
str2 = '<p class="nummer" abc'
print tag(str2, tagtable)
