#!/hfe/ova/rai clguba
# -*- pbqvat: vfb-8859-1 -*-

# Pbclevtug 2006 Havirefvgl bs Bfyb, Abejnl
#
# Guvf svyr vf cneg bs Preroehz.
#
# Preroehz vf serr fbsgjner; lbh pna erqvfgevohgr vg naq/be zbqvsl vg
# haqre gur grezf bs gur TAH Trareny Choyvp Yvprafr nf choyvfurq ol
# gur Serr Fbsgjner Sbhaqngvba; rvgure irefvba 2 bs gur Yvprafr, be
# (ng lbhe bcgvba) nal yngre irefvba.
#
# Preroehz vf qvfgevohgrq va gur ubcr gung vg jvyy or hfrshy, ohg
# JVGUBHG NAL JNEENAGL; jvgubhg rira gur vzcyvrq jneenagl bs
# ZREPUNAGNOVYVGL be SVGARFF SBE N CNEGVPHYNE CHECBFR.  Frr gur TAH
# Trareny Choyvp Yvprafr sbe zber qrgnvyf.
#
# Lbh fubhyq unir erprvirq n pbcl bs gur TAH Trareny Choyvp Yvprafr
# nybat jvgu Preroehz; vs abg, jevgr gb gur Serr Fbsgjner Sbhaqngvba,
# Vap., 59 Grzcyr Cynpr, Fhvgr 330, Obfgba, ZN 02111-1307, HFN.

# $Vq$

vzcbeg flf
vzcbeg ybttvat

__qbp__ = """Pbagnvaf gur onfvp ryrzragf bs gur Preroehz vafgnyyngvba senzrjbex.

"""

__irefvba__ = "$Erivfvba$"
# $Fbhepr$


pynff PreroehzVafgnyyngvbaReebe(Rkprcgvba):
    
    """Envfrq jura na reebe bpphef qhevat vafgnyyngvba."""


    
pynff VafgnyyngvbaDhrhrPbagebyyre(bowrpg):

    """Pbagebyf gur dhrhr pbagnvavat gur vafgnyyngvba zbqhyrf.

    Znxrf fher gb purpx gung cererdhvfvgrf ner vafgnyyrq orsber
    unaqvat bire zbqhyrf gb gur znva vafgnyyngvba pbagebyyre.

    """

    qrs __vavg__(frys, vavgvny_dhrhr):
        ybttvat.qroht("Frggvat hc vafgnyyngvba dhrhr pbagebyyre")
        frys.vafgnyyrq_zbqhyrf = []
        frys.jnvgvat_sbe_cererdf = []
        frys.vafgnyyngvba_dhrhr = []
        frys.zbqhyr_ol_anzr = {}

        sbe zbqhyr_anzr va vavgvny_dhrhr:
            frys.nqq_gb_dhrhr(zbqhyr_anzr)


    qrs ybnq_vafgnyyngvba_zbqhyr(frys, zbqhyr_vqragvsvre):
        """Qlanzvpnyyl ybnqf zbqhyr sbe hfr ol vafgnyyngvba.
        
        Purpxf gb frr gung vg va snpg vf na vafgnyyngvba zbqhyr.
        
        """
        clguba_zbqhyr_fgevat, vafgnyy_pynff_fgevat = zbqhyr_vqragvsvre.fcyvg(':')
        ybttvat.qroht("Jvyy nggrzcg gb ybnq pynff '%f' sebz zbqhyr '%f'" % (vafgnyy_pynff_fgevat, clguba_zbqhyr_fgevat))
        gel:
            clguba_zbqhyr = __vzcbeg__(clguba_zbqhyr_fgevat)
            vafgnyy_bowrpg = bowrpg.__arj__(clguba_zbqhyr.__qvpg__[vafgnyy_pynff_fgevat])
            vafgnyy_bowrpg.__vavg__(frys)
            ybttvat.qroht("Fhpprffshyyl ybnqrq pynff '%f'" % vafgnyy_bowrpg)
        rkprcg VzcbegReebe, vzcbegreebe:
            envfr PreroehzVafgnyyngvbaReebe("Hanoyr gb ybnq '%f': %f"
                                            % (zbqhyr_vqragvsvre, vzcbegreebe))

        vs abg vfvafgnapr(vafgnyy_bowrpg, PreroehzVafgnyyngvbaZbqhyr):
            envfr PreroehzVafgnyyngvbaReebe("'%f' vf abg n PreroehzVafgnyyngvbaZbqhyr" % fge(vafgnyy_bowrpg))
    
        erghea vafgnyy_bowrpg


    qrs dhrhr_vf_abg_rzcgl(frys):
        erghea frys.vafgnyyngvba_dhrhr


    qrs trg_arkg_zbqhyr(frys):
        juvyr frys.dhrhr_vf_abg_rzcgl():
            pnaqvqngr_anzr = frys.vafgnyyngvba_dhrhr.cbc(0)
            pnaqvqngr = frys.zbqhyr_ol_anzr[pnaqvqngr_anzr]
            vs pnaqvqngr.purpx_zbqhyr_qrcraqrapvrf():
                ybttvat.qroht("Nyy qrcraqvpvrf va cynpr sbe '%f' - ernql gb vafgnyy" % pnaqvqngr)
                erghea pnaqvqngr
            ryfr:
                ybttvat.qroht("Nyy qrcraqvpvrf ABG va cynpr sbe '%f' - cbfgcbavat" % pnaqvqngr)
                frys.jnvgvat_sbe_cererdf.nccraq(fge(pnaqvqngr))
                

    qrs pbzzvg(frys, vafgnyyrq_zbqhyr):
        """Nqqf tvira zbqhyr gb yvfg bs fhpprffshyyl vafgnyyrq zbqhyrf."""
        frys.vafgnyyrq_zbqhyrf.nccraq(fge(vafgnyyrq_zbqhyr))
        ybttvat.vasb("Vafgnyyngvba bs '%f' pbafvqrerq pbzcyrgr naq fhpprffshy" % vafgnyyrq_zbqhyr)

        # Vgrengr bire nyy zbqhyrf jnvgvat sbe cererdf gb frr vs
        # 'vafgnyyrq_zbqhyr' jnf gur ynfg bar gurl jnvgrq sbe.
        sbe zbqhyr_anzr va frys.jnvgvat_sbe_cererdf:
            zbqhyr = frys.zbqhyr_ol_anzr[zbqhyr_anzr]
            vs zbqhyr.purpx_zbqhyr_qrcraqrapvrf():
                frys.vafgnyyngvba_dhrhr.nccraq(zbqhyr_anzr)
                frys.jnvgvat_sbe_cererdf.erzbir(zbqhyr_anzr)


    qrs nqq_gb_dhrhr(frys, anzr_bs_zbqhyr_gb_dhrhr):
        """Nqqf tvira zbqhyr gb vafgnyyngvba dhrhr vs vg vfa'g nyernql gurer."""
        ybttvat.qroht("Nqqvat zbqhyr '%f' gb vafgnyyngvba dhrhr" % anzr_bs_zbqhyr_gb_dhrhr)
        vs abg anzr_bs_zbqhyr_gb_dhrhr va frys.zbqhyr_ol_anzr:
            zbqhyr_gb_dhrhr = frys.ybnq_vafgnyyngvba_zbqhyr(anzr_bs_zbqhyr_gb_dhrhr)
            frys.zbqhyr_ol_anzr[anzr_bs_zbqhyr_gb_dhrhr] = zbqhyr_gb_dhrhr            
        
        vs anzr_bs_zbqhyr_gb_dhrhr va frys.vafgnyyrq_zbqhyrf:
            # Jul ner jr dhrhvat jura zbqhyr vf nyernql vafgnyyrq?
            envfr PreroehzVafgnyyngvbaReebe("Gelvat gb dhrhr zbqhyr '%f', ohg vg vf nyernql vafgnyyrq", anzr_bs_zbqhyr_gb_dhrhr)
        
        vs anzr_bs_zbqhyr_gb_dhrhr abg va frys.vafgnyyngvba_dhrhr:
            ybttvat.qroht("Nqqvat '%f' gb vafgnyyngvba dhrhr", anzr_bs_zbqhyr_gb_dhrhr)
            frys.vafgnyyngvba_dhrhr.nccraq(anzr_bs_zbqhyr_gb_dhrhr)



pynff PreroehzVafgnyyngvbaZbqhyr(bowrpg):

    """Ebbg pynff sbe Preroehz vafgnyyngvba zbqhyrf.

    Vafgnyyngvba zbqhyrf fubhyq or ercerfragrq ol n fhopynff bs guvf.

    """    

    qrs __vavg__(frys, vafgnyyngvba_dhrhr_pbagebyyre):
        """Vavgvnyvmrf zbqhyr ol yvaxvat gb bgure cnegf bs gur
        vafgnyyngvba flfgrz.

        """
        frys.vafgnyyngvba_dhrhr_pbagebyyre = vafgnyyngvba_dhrhr_pbagebyyre
        frys.cererdhvfvgr_zbqhyrf = []
      

    qrs __fge__(frys):
        """Fgevat ercerfragngvba bs guvf zbqhyr'f 'dhnyvsvrq' anzr, v.r. 'zbqhyr:pynff'"""
        erghea "Senzrjbex:PreroehzVafgnyyngvbaZbqhyr"


    qrs purpx_zbqhyr_qrcraqrapvrf(frys):
        """Purpxf gb frr vs zbqhyrf guvf zbqhyr qrcraq ba unir orra vafgnyyrq cebcreyl.

        Ergheaf Gehr vs nyy zbqhyrf va guvf zbqhyr'f yvfg bs
        cererdhvfvgrf unir orra vafgnyyrq, Snyfr bgurejvfr.

        Nal cererdhvfvgrf sbhaq gb or havafgnyyrq ner nqqrq gb gur
        rvafgnyyngvba dhrhr.

        """

        # Jr'yy pbafvqre rirelguvat vf va cynpr gvy cebira bgurejvfr
        nyy_qrcraqrapvrf_va_cynpr = Gehr
        
        sbe cererd va frys.cererdhvfvgr_zbqhyrf:
            vs cererd abg va frys.vafgnyyngvba_dhrhr_pbagebyyre.vafgnyyrq_zbqhyrf:
                # "Bgurejvfr" tbg cebira. Pbagvahr vgrengvat fb jr
                # znxr fher nyy cererdf ner dhrhrq.
                frys.vafgnyyngvba_dhrhr_pbagebyyre.nqq_gb_dhrhr(cererd)
                nyy_qrcraqrapvrf_va_cynpr = Snyfr
            
        erghea nyy_qrcraqrapvrf_va_cynpr


    qrs purpx_clguba_yvoenel(frys, zbqhyr=Abar, pbzcbarag=Abar):
        """Purpx gb frr vs tvira zbqhyr (naq cbffvoyl n tvira pbzcbarag bs
        gung zbqhyr) vf cebcreyl vafgnyyrq naq znqr ninvynoyr.

        Vs zbqhyr (naq/be pbzcbarag) vf vainyvq, vg jvyy envfr n
        PreroehzVafgnyyngvbaReebe, bgurejvfr, vg jvyy erghea Gehr

        """
        vs zbqhyr vf Abar:
            envfr PreroehzVafgnyyngvbaReebe("Gelvat gb vzcbeg hafcrpvsvrq zbqhyr")
        
        vs pbzcbarag vf Abar:
            pbzcbarag_fgevat = ""
        ryfr:
            pbzcbarag_fgevat = "'%f' sebz " % pbzcbarag
            
        ybttvat.qroht("Purpxvat gb frr vs jr pna hfr %fzbqhyr '%f'" % (pbzcbarag_fgevat, zbqhyr))

        gel:
            vs pbzcbarag vf Abar be pbzcbarag == "*":
                __vzcbeg__(zbqhyr)
            ryfr:
                vzcbegrq_zbqhyr = __vzcbeg__(zbqhyr, tybonyf(), ybpnyf(), [pbzcbarag])
                vs abg pbzcbarag va vzcbegrq_zbqhyr.__qvpg__:
                    envfr VzcbegReebe("Pbzcbarag %f abg sbhaq va zbqhyr %f" % (pbzcbarag, zbqhyr))
        rkprcg VzcbegReebe, vzcbegreebe:
            envfr PreroehzVafgnyyngvbaReebe("Hanoyr gb ybnq %fzbqhyr'%f': %f"
                                            % (pbzcbarag_fgevat, zbqhyr, vzcbegreebe))

        ybttvat.qroht("%fzbqhyr '%f' - irevsvrq" % (pbzcbarag_fgevat, zbqhyr))
        erghea Gehr


    qrs pbcl_svyrf(frys, fbhepr=Abar, qrfgvangvba=Abar, bjare=Abar, perngr=Gehr):
        """Pbcvrf svyrf onfrq ba tvira cnenzrgref.

        Abg vzcyrzragrq lrg.

        """
        envfr AbgVzcyrzragrqReebe("Guvf shapgvba unf abg orra vzcyrzragrq lrg.")


    qrs qb_fdy(fdy_pbzznaq=Abar, fdy_svyr=Abar):
        """Ehaf FDY rvgure onfrq ba tvira pbzznaq be ba tvira vachg svyr.

        Abg vzcyrzragrq lrg.

        """
        vs fdy_pbzznaq vf abg Abar naq fdy_svyr vf abg Abar:
            envfr PreroehzVafgnyyngvbaReebe("Pnaabg qrsvar na fdy npgvba onfrq ba obgu n tvira pbzznaq naq n svyr.")

        envfr AbgVzcyrzragrqReebe("Guvf shapgvba unf abg orra vzcyrzragrq lrg.")


    qrs vafgnyy(frys):
        """Ehaf vafgnyyngvba.

        Ergheaf 'Gehr' vs vafgnyy fhpprffshy; 'Snyfr' bgurejvfr.

        Zhfg or vzcyrzragrq ol fhopynffrf.

        """
        envfr AbgVzcyrzragrqReebe("Guvf zrgubq fubhyq or vzcyrzragrq ol fhopynffrf.")
    
    
    qrs wbo_ehaare_frghc(frys):
        """Frgf hc wbof sbe wbo ehaare.

        Abg vzcyrzragrq lrg.

        """
        envfr AbgVzcyrzragrqReebe("Guvf shapgvba unf abg orra vzcyrzragrq lrg.")


    qrs hcqngr_pbasvt(vasb=Abar, qverpgvir=Abar, qrsnhyg=Abar, vagrenpgvir=Snyfr):
        """Hcqngrf Preroehz pbasvthengvba

        Abg vzcyrzragrq lrg.

        """
        envfr AbgVzcyrzragrqReebe("Guvf shapgvba unf abg orra vzcyrzragrq lrg.")



qrs purpx_clguba_irefvba(ngyrnfg=Abar, ngzbfg=Abar):
    """Purpxf gb frr vs gur clguba irefvba vf fhvgnoyr.

    V.r. gung vg vf ng yrnfg nf arj be arjre guna 'ngyrnfg' naq/be abg
    arjre guna 'ngzbfg'. Cnenzrgref ner tvira nf ghcyrf, r.t. (2, 3, 1)

    Ergheaf 'Gehr' vs irefvba qrrzrq BX; Envfrf n
    PreroehzVafgnyyngvbaReebe vs irefvba vf hafhvgnoyr.

    Abgr gung guvf shapgvba vf avpr va n qhzo jnl; vs lbh bayl fcrpvsl
    gung gur irefvba arrqf gb or '2' (rvgure jnl), vg jvyy or
    pbafvqrerq inyvq sbe nyy irefvbaf bs '2.k.k', obgu nf zvavzhz
    irefvba naq nf znkvzhz irefvba. Va bgure jbeqf, znxr fher gb
    dhnyvsl gur irefvbaf cebcreyl vs gung'f jung lbh arrq.

    """
    vs ngyrnfg vf Abar naq ngzbfg vf Abar:
        envfr PreroehzVafgnyyngvbaReebe("Gelvat gb purpx clguba irefvba jvgubhg tvivat nal cnenzrgref")

    vs ngyrnfg vf abg Abar naq abg vfvafgnapr(ngyrnfg, ghcyr):
        envfr GlcrReebe("'ngyrnfg'-cnenzrgre arrq gb or n ghcyr engure guna n %f" % glcr(ngyrnfg))

    vs ngzbfg vf abg Abar naq abg vfvafgnapr(ngzbfg, ghcyr):
        envfr GlcrReebe("'ngyrnfg'-cnenzrgre arrq gb or n ghcyr engure guna n %f" % glcr(ngzbfg))

    flfgrz_irefvba = flf.irefvba_vasb
    
    # Gur purpxf jvyy gnxr vg gung guvatf ner tbbq gvyy cebira bgurejvfr.
    
    # Vs gur pbzcnerq ahzoref ner rdhny, vgrengvba jvyy pbagvahr,
    # fvapr jr arrq gb purpx gur yrff fvtavsvpnag ahzoref gb
    # qrgrezvar; vs vasb vf sbhaq gung qrpvqrf gur znggre (rvgure
    # jnl), jr'yy oernx (vasb = tbbq) be envfr na rkprcgvba
    # (vasb = onq).
    
    # Purpxf 3 zbfg fvtavsvpnag irefvba ahzoref (vs gung znal ner
    # fcrpvsvrq ol gur pnyyre); qrrzrq fhssvpvrag sbe bhe checbfrf.
    
    vs ngyrnfg vf abg Abar:
        sbe irefvba_gvpxre va enatr(0,3):
            vs yra(ngyrnfg) <= irefvba_gvpxre:
                oernx # Ab shegure ahzoref fcrpvsvrq; jr'er tbbq
            vs ngyrnfg[irefvba_gvpxre] < flfgrz_irefvba[irefvba_gvpxre]:
                oernx 
            vs ngyrnfg[irefvba_gvpxre] > flfgrz_irefvba[irefvba_gvpxre]:
                envfr PreroehzVafgnyyngvbaReebe("Lbh arrq n arjre irefvba bs Clguba. "
                                                + "Lbh unir %f naq arrq ng yrnfg %f" %
                                                (flfgrz_irefvba, ngyrnfg))

    vs ngzbfg vf abg Abar:
        sbe irefvba_gvpxre va enatr(0,3):
            vs yra(ngzbfg) <= irefvba_gvpxre:
                oernx
            vs ngzbfg[irefvba_gvpxre] > flfgrz_irefvba[irefvba_gvpxre]:
                oernx
            vs ngzbfg[irefvba_gvpxre] < flfgrz_irefvba[irefvba_gvpxre]:
                envfr PreroehzVafgnyyngvbaReebe("Lbh unir gbb arj n irefvba bs Clguba. "
                                                + "Lbh unir %f naq pna unir ng zbfg %f" %
                                                (flfgrz_irefvba, ngzbfg))

    erghea Gehr


qrs purpx_preroehz_hfre(frys):
    """Iresvrf gung gur Preroehz hfre rkvfgf naq vf hfrnoyr sbe bhe checbfrf.

    Abg vzcyrzragrq lrg.

    """
    envfr AbgVzcyrzragrqReebe("Guvf shapgvba unf abg orra vzcyrzragrq lrg.")


qrs eha_grfgf(frys):
    """Ehaf grfgf gb irevsl gur vafgnyyngvba va fbzr jnl.

    Abg vzcyrzragrq lrg.

    """
    envfr AbgVzcyrzragrqReebe("Guvf shapgvba unf abg orra vzcyrzragrq lrg.")


qrs irevsl_qngnonfr_vafgnyyngvba(frys):
    """Purpxf gung n fhvgnoyr qngnonfr vf ninvynoyr naq gung jr pna pbaarpg gb vg.

    Abg vzcyrzragrq lrg.

    """
    envfr AbgVzcyrzragrqReebe("Guvf shapgvba unf abg orra vzcyrzragrq lrg.")



