/*
 * Copyright rune.froysa@usit.uio.no 2001.
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 * 
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 */
package no.uio.jbofh;

import java.io.File;
import java.io.IOException;
import java.net.JarURLConnection;
import java.net.URL;
import java.util.Enumeration;
import java.util.Vector;
import java.util.jar.JarEntry;
import java.util.jar.JarFile;

/**
 * ResourceLocator alows you to use the same code to access data from
 * a jar file as from the local filesystem.  This is conventient when
 * you don't keep your code in a jar file while developing.  It also
 * alows you to have a bunch of files in the jar file, and reference
 * them without hardcoding their names into your aplication.
 * <p>
 * Example of usage: <pre>
 * String []s = ResourceLocator.getResources(this, "images");
 * for(int i = 0; i < s.length; i++) {
 *     URL url = ResourceLocator.getResource(r, s[i]);
 *     ...
 * }
 * </pre>
 */

public class ResourceLocator {
    protected ResourceLocator() {}  // It is not suposed to be instantiated

    /**
     * Get a resource
     *
     * @param ref Object the object who is used as a reference when
     * looking up the resource
     * @param name String the name of the resource
     * @return URL reference to the resource
     */
    static public URL getResource(Object ref, String name) {
	return ref.getClass().getResource(name);
    }
    
    /**
     * Get an array of resources
     * @param ref Object the object who is used as a reference when
     * looking up the resource
     * @param name String the name of the resource.  Must be a directory
     * @return String[] list of resources.  Those with a trailing slash
     * are directories
     */
    static public String[] getResources(Object ref, String key) {
	Vector v = new Vector();
	if(! key.endsWith("/")) {  // jc.getJarEntry().isDirectory()
	    key = key+"/";
	}
	URL u = getResource(ref, key);
	if(u == null) return null;
	if(u.getProtocol().equals("jar")) {
	    try {
		JarURLConnection jc = (JarURLConnection) u.openConnection();
		JarFile jFile = jc.getJarFile();
		String base = jc.getEntryName();
		for (Enumeration e = jFile.entries() ; e.hasMoreElements() ;) {
		    JarEntry ob = (JarEntry) e.nextElement();
		    int pos;
		    if(ob.getName().startsWith(base) && ! ob.getName().equals(base)) {
			pos = ob.getName().indexOf("/", base.length());
			if(pos == -1 || pos == ob.getName().length() - 1) {
			    v.add(ob.toString());
			}
		    }
		}		
	    } catch (IOException io) {
	    }
	} else if(u.getProtocol().equals("file")){
	    File f = new File(u.getFile());
	    File files[] = f.listFiles();
	    for(int i = 0; i < files.length; i++) {
		v.add(key+files[i].getName()+
		      (files[i].isDirectory() ? "/" :""));
	    }
	} else {
	    throw new UnsupportedOperationException("Can't handle protocol:"+u.getProtocol());
	}
	String ret[] = new String[v.size()];
	System.arraycopy(v.toArray(), 0, ret, 0, v.size());
	return ret;
    }
}
