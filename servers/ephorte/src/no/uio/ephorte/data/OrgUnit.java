package no.uio.ephorte.data;

import java.text.ParseException;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Hashtable;
import java.util.Vector;

import no.uio.ephorte.xml.XMLUtil;

/**
 * Represents a admindel entry in ePhorte.
 * 
 * This module is currently not in use. 
 *
 * @author rogerha
 * 
 */

public class OrgUnit {
    public static SimpleDateFormat dayFormat = new SimpleDateFormat("yyyy-MM-dd");
    private String sko;
    private String akronym; 
    private String longname;
    private String journalEnhet;
    private int parent;
    private int id = -1;
    private Date fraDato;
    private int xmlRefId;
    private boolean changed = false;
    private boolean isDeletable = false;
    
    public boolean isChanged() {
        return changed;
    }


    // Hvilke data skal vi skrive til tabellen? De under er sikre, men
    // skal vi skrive AI_FULLSTENDIGSTED_G? (eks. "1 - 105" for sko 290800)
    public OrgUnit(String sko, int parent, String akronym, String longname,
		   String journalEnhet) 
    {
	//this.xmlRefId = ++xmlRefIdCounter; 
	this.parent = parent;
	this.sko = sko;
	this.akronym = akronym;
	this.longname = longname;
	this.journalEnhet = journalEnhet;
        fraDato = new Date();
    }
    // Hva gjør vi med parent? id eller sko?
    public OrgUnit(Hashtable<String, String> ht) {
	this.parent = Integer.parseInt(ht.get("AI_IDFAR"));
	this.sko = ht.get("AI_FORKDN");
	this.akronym = ht.get("AI_ADMKORT");
	this.longname = ht.get("AI_ADMBET");
	this.journalEnhet = ht.get("AI_JENHET_G");
        this.id = Integer.parseInt(ht.get("AI_ID"));
        try {
            if (ht.get("AI_FRADATO") != null) {
                fraDato = Person.dayFormat.parse(ht.get("AI_FRADATO"));
	    }
        } catch (ParseException e) {
            e.printStackTrace();
        }
    }

    // equals
    @Override
    public boolean equals(Object obj) {
        if (obj instanceof OrgUnit) {
            OrgUnit ou = (OrgUnit) obj;
            return XMLUtil.equals(sko, ou.sko) 
		&& XMLUtil.equals(parent, ou.parent)
		&& XMLUtil.equals(akronym, ou.akronym)
		&& XMLUtil.equals(longname, ou.longname);
        }
        return super.equals(obj);
    }

    public void toXML(XMLUtil xml) {
        xml.startTag("ADMINDEL");
        if (id != -1) {
	    // The OU exists in ePhorte. Change attributes
            //xml.writeElement("AI_ID", "" + xmlRefId++);
            xml.writeElement("AI_ID", "" + id);
            xml.writeElement("SEEKFIELDS", "AI_ID");
            xml.writeElement("SEEKVALUES", "" + id);
            xml.writeElement("AI_TILDATO", OrgUnit.dayFormat.format(new Date()));
            //xml.writeElement("", );
            //xml.writeElement("", );
            //xml.writeElement("", );
            //xml.writeElement("", );
            //xml.writeElement("", );
            //xml.writeElement("", );
            //xml.writeElement("", );
            //xml.writeElement("", );

        } else {
            xml.writeElement("", "");
        }

        xml.endTag("ADMINDEL");
    }

    public void toSeekXML(XMLUtil xml) {


    }

    // getters og setters
    //public void setNew(boolean isNew) {
    //    this.isNew = isNew;
    //}
    //
    //public boolean isNew() {
    //    return isNew;
    //}

    //public void setTilDato(Date tilDato) {
    //    this.tilDato = tilDato;
    //}

    public void setDeletable(boolean isDeletable) {
	this.isDeletable = isDeletable;
    }

    //public Date getTilDato() {
    //    return this.tilDato;
    //}
}
