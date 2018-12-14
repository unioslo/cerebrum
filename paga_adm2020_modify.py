#!/usr/bin/python

import sys, getopt

def usage():
    print("python paga_adm2020_modify.py --input1=test1.txt --input2=test2.txt --output=test3.txt")

try:
    opts, args = getopt.getopt(sys.argv[1:], 'h', ['input1=', 'input2=', 'output=', 'help'])
except getopt.GetoptError:
    usage()
    sys.exit(2)

inputname1 = "/cerebrum/var/dumps/paga/uit_paga_last.csv"
inputname2 = "/home/cerebrum/cerebrum/contrib/no/uit/uit_addons/scripts/adm2020/uit_paga_adminpeople_final.csv"
outputname = "/cerebrum/var/dumps/paga/uit_paga_last.csv"

for o, a in opts:
    if o == "--input1":
        inputname1 = a
    elif o == "--input2":
        inputname2 = a
    elif o == "--output":
        outputname = a
    elif o in ("-h", "--help"):
        usage()
        sys.exit()
    else:
        assert False, "unhandled option"

fout = open(outputname, "w")

fin = open(inputname1, "r")
filedata = fin.read()
fin.close()
fout.write(filedata)

fin = open(inputname2, "r")
filedata = fin.read()
fin.close()
fout.write(filedata)

fout.close()


