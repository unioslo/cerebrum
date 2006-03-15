#!/bin/bash
cp -u  --preserve=timestamps /mnt/ad/AD_Emaildump.cvs /cerebrum/var/source/ad/AD_Emaildump.cvs
cp -u  --preserve=timestamps /mnt/ad/akademisk.csv /cerebrum/var/source/ad/akademisk.csv
cp -u  --preserve=timestamps /mnt/ad/humfak.csv /cerebrum/var/source/ad/humfak.csv
cp -u  --preserve=timestamps /mnt/ad/ita.csv /cerebrum/var/source/ad/ita.csv
cp -u  --preserve=timestamps /mnt/ad/jurfak.csv /cerebrum/var/source/ad/jurfak.csv
cp -u  --preserve=timestamps /mnt/ad/kun.csv /cerebrum/var/source/ad/kun.csv
cp -u  --preserve=timestamps /mnt/ad/matnat.csv /cerebrum/var/source/ad/matnat.csv
cp -u  --preserve=timestamps /mnt/ad/medfak.csv /cerebrum/var/source/ad/medfak.csv
cp -u  --preserve=timestamps /mnt/ad/nfh.csv /cerebrum/var/source/ad/nfh.csv
cp -u  --preserve=timestamps /mnt/ad/nuv.csv /cerebrum/var/source/ad/nuv.csv
cp -u  --preserve=timestamps /mnt/ad/orakel.csv /cerebrum/var/source/ad/orakel.csv
cp -u  --preserve=timestamps /mnt/ad/plp.csv /cerebrum/var/source/ad/plp.csv
cp -u  --preserve=timestamps /mnt/ad/sadm.csv /cerebrum/var/source/ad/sadm.csv
cp -u  --preserve=timestamps /mnt/ad/sito.csv /cerebrum/var/source/ad/sito.csv
cp -u  --preserve=timestamps /mnt/ad/svfak.csv /cerebrum/var/source/ad/svfak.csv
cp -u  --preserve=timestamps /mnt/ad/TMU.csv /cerebrum/var/source/ad/TMU.csv
cp -u  --preserve=timestamps /mnt/ad/ub.csv /cerebrum/var/source/ad/ub.csv
cp -u  --preserve=timestamps /mnt/ad/utdanning_no.csv /cerebrum/var/source/ad/utdanning_no.csv
cp -u  --preserve=timestamps /mnt/ad/uvett.csv /cerebrum/var/source/ad/uvett.csv
chown cerebrum.cerebrum /cerebrum/var/source/ad/*.csv
chown cerebrum.cerebrum /cerebrum/var/source/ad/AD_Emaildump.cvs
