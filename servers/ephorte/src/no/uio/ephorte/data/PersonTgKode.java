package no.uio.ephorte.data;

import java.text.ParseException;
import java.util.Date;
import java.util.Hashtable;
import java.util.Vector;
import org.apache.commons.logging.Log;
import org.apache.commons.logging.LogFactory;

import no.uio.ephorte.xml.XMLUtil;

/**
 * Represents a pertgkode entry in ephorte
 *
 * @author rogerha
 *
 **/

public class PersonTgKode {
    static Hashtable<String, Integer> stedkode2Id;
    //static Hashtable<String, Integer> tgKodeType2Id;
    private static Log log = LogFactory.getLog(PersonTgKode.class);

    private Person person;
    private int pe_id = -1;
    private String operatorBrukerId;
    private int operatorId = -1;
    private int autopphav = 0;
    private String tgKodeType;
    private Integer adminDel;
    private Date tilDato;
    private Date fraDato;

    public static void setup(Vector<Hashtable<String, String>> adminDelDataSet) {
        stedkode2Id = new Hashtable<String, Integer>();
        for (Hashtable<String, String> ht : adminDelDataSet) {
    	    try {
    		stedkode2Id.put(ht.get("AI_FORKDN"), Integer.parseInt(ht.get("AI_ID")));
    	    } catch (Exception e) {
    		log.warn("Wrong format: AI_FORKDN: " + ht.get("AI_FORKDN") + 
    			 ", AI_ID: " + ht.get("AI_ID"));
    	    }
        }
    }

    public PersonTgKode(Person person, Hashtable<String, String> ht) {
        this.person = person;
        pe_id = Integer.parseInt(ht.get("PT_PEID_PE"));
	tgKodeType = ht.get("PT_TGKODE_TK");
        String tmp = ht.get("PT_ADMID_AI");
        if (tmp != null)
            adminDel = Integer.parseInt(tmp);
        tmp = ht.get("PT_AUTAV_PE");
        if (tmp != null)
            operatorId= Integer.parseInt(tmp);	
        try {
            tmp = ht.get("PR_FRADATO");
            if (tmp != null)
                fraDato = Person.dayFormat.parse(tmp);
        } catch (ParseException e) {
            e.printStackTrace();
        }
    }

    public PersonTgKode(Person person, String tgKodeType, String sko, 
			String feideId) 
	throws BadDataException 
    {
        this.person = person;
	this.tgKodeType = tgKodeType;
        Integer tmp = stedkode2Id.get(sko);
        if (tmp == null)
            throw new BadDataException("Illegal sko: " + sko);
        adminDel = tmp;
        operatorBrukerId = feideId;
        fraDato = new Date();
    }

    // equals
    @Override
    public boolean equals(Object obj) {
        if (obj instanceof PersonTgKode) {
            PersonTgKode tk = (PersonTgKode) obj;
            // Vi ser ikke på self.id ettersom denne vil være -1 fra import filen
            return  XMLUtil.equals(pe_id, tk.pe_id) && 
		XMLUtil.equals(tgKodeType, tk.tgKodeType) && 
		XMLUtil.equals(adminDel, tk.adminDel);
        }
        return super.equals(obj);
    }

    public void toXML(XMLUtil xml) {
        xml.startTag("PERTGKODE");
	xml.writeElement("PT_PEID_PE", "" + person.getId());
	xml.writeElement("PT_TGKODE_TK", tgKodeType);
	xml.writeElement("PT_ADMID_AI", "" + adminDel);
	xml.writeElement("PT_AUTAV_PE", "" + operatorId);
	xml.writeElement("PT_AUTOPPHAV_PE", "" + autopphav);
	xml.writeElement("PT_FRADATO", Person.dayFormat.format(fraDato));
        if (tilDato != null)
            xml.writeElement("PT_TILDATO", Person.dayFormat.format(tilDato));
        xml.endTag("PERTGKODE");
    }

    public void toDeleteXML(XMLUtil xml) {
        xml.startTag("PERTGKODE");
	xml.writeElement("PT_PEID_PE", "" + person.getId());
	xml.writeElement("PT_TGKODE_TK", tgKodeType);
	xml.writeElement("PT_ADMID_AI", "" + adminDel);
        xml.writeElement("SEEKFIELDS", "PT_PEID_PE;PT_TGKODE_TK;PT_ADMID_AI");
        xml.writeElement("SEEKVALUES", "" + person.getId() + ";" + tgKodeType +
			 ";" + adminDel);
	// TBD: skal vi slette raden eller sette tildato? Begge deler
	// virker. Setter tildato i f�rste omgang
	xml.writeElement("PT_TILDATO", Person.dayFormat.format(getTilDato()));
        xml.endTag("PERTGKODE");
    }

    @Override
    public String toString() {
	return "TgKode: pid=" + person.getId() + ", type=" + tgKodeType + 
	    ", adminDel=" + adminDel + ", autav=" + operatorId;
    }

    public void setOperatorId(int peId) {
	operatorId = peId;
    }

    public String getOperatorBrukerId() {
	return operatorBrukerId;
    }

    public void setTilDato(Date tilDato) {
        this.tilDato = tilDato;
    }

    public Date getTilDato() {
        return tilDato;
    }

}