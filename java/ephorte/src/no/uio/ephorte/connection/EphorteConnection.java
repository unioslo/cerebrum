package no.uio.ephorte.connection;

import java.rmi.RemoteException;
import java.util.Hashtable;
import java.util.Vector;

/**
 * Class that wraps all WebService calls so that we can provide pre-generated
 * results for off-line debugging.
 * 
 * @author rune
 * 
 */
public abstract class EphorteConnection {
    public abstract Vector<Hashtable<String, String>> getDataSet(
            String criteriaCollectionString, String tagName) throws RemoteException;

    abstract protected int updatePersonByXML(String xml) throws RemoteException;

}
