#! /usr/bin/env python


import sys
import os
from sets import Set

fnamea = sys.argv[1]
fa = open(fnamea,'r')
la = fa.readlines()
fa.close()
sa = Set(la)


fnameb = sys.argv[2]
fb = open(fnameb,'r')
lb = fb.readlines()
fb.close()
sb=Set(lb)


not_in_b = sa - sb
for i in not_in_b:
    print i.rstrip()


        
