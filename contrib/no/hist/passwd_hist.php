<?
/*
# Script for changing a user's password using a web based interface.
#
# Requirements: php --with-curl and XMLRPC library
#
# httpd environment variables used: REQUEST_URI, HTTP_HOST
#
########################################################################

# Copyright 2002, 2003 Steinar Kleven, Norway
#
# This file is part of Cerebrum.
#
# Cerebrum is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Cerebrum is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Cerebrum; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.
*/


// Force SSL for this page
if ($_SERVER['HTTPS'] != "on") {
	header("Location: https://".$_SERVER['HTTP_HOST'].$_SERVER['REQUEST_URI']);
}

// http://xmlrpc.usefulinc.com XMLRPC classes (--with-curl required)
// http://xmlrpc-epi.sourceforge.net/ can be used as an alternative but
// requries to be enabled at php compile time.
include("../xmlrpc/xmlrpc.inc");

// Bofh server
$BOFHD_HOST = "pc1039.ahs.hist.no";
$BOFHD_PORT = 8000;
$PROTOCOL = "https"; // https | http



function bofhd_logout($server, $sid)
{
        global $PROTOCOL;
        $message = new xmlrpcmsg('logout',         
                   array(new xmlrpcval($sid)));
        $result = $server->send($message,10,$PROTOCOL);
}


function bofhd_login($server, $uname, $password)
{
        global $PROTOCOL;
        $message = new xmlrpcmsg('login',         
                   array(new xmlrpcval($uname), 
                         new xmlrpcval($password)));
        $result = $server->send($message,10,$PROTOCOL);
        if ($result->faultCode())
        {
	  return array($undef, $result->faultString());
        } else {
          $ssidobj = $result->value();
          if ($ssidobj->scalartyp())
          {
            return array($ssidobj->scalarval(), "");
          }else {
            return array(undef, "Internal system error");
          }
	}
}

function print_err($strErr)
{
        list($src, $reason) = split(":", $strErr, 2); 
	print "<hr> $reason";
}


function run_command($server, $sid, $msg_array)
{
        global $PROTOCOL;
        $tosend = array_merge(array(new xmlrpcval($sid)), $msg_array); 
        $message = new xmlrpcmsg('run_command', $tosend);
        return $server->send($message,10,$PROTOCOL);
}



function call_bofhd($uname, $password, $new_password)
{
	global $BOFHD_HOST, $BOFHD_PORT;
        $server = new xmlrpc_client("/RPC2",$BOFHD_HOST,$BOFHD_PORT);
//	$server->setDebug(1);
        $server->setSSLVerifyPeer(0);
//	$server->setSSLVerifyHost(0);
//  $server->setCertificate($CACERT_FILE, "");
        $server->setCredentials($uname, $password);
        list($sid, $strErr) = bofhd_login($server, $uname, $password);
        if (!strlen($sid))
        {
          print_err($strErr);  
          return False;
        } else {
          $result = run_command($server, $sid, array(
                         new xmlrpcval('user_password')
                         ,new xmlrpcval($uname) 
                         ,new xmlrpcval($new_password)));
          // print $result->serialize();
          bofhd_logout($server, $sid);
          if ($result->faultCode())
          {
            print_err($result->faultString());
            return False;
          } else {
            print "<b>Passordet ditt er endret, det vil bli aktivisert innen et døgn.</b>";
            return True;
          }
        }
}


function handle_request()
{
    $uname =  strip_tags(stripslashes($_REQUEST['uname']));
    $pass = strip_tags(stripslashes($_REQUEST['pass']));
    $newpass = strip_tags(stripslashes($_REQUEST['newpass']));
    $newpass2 = strip_tags(stripslashes($_REQUEST['newpass2']));
    
    if (!isset($_REQUEST['action']))
    {
      print "<form method=\"POST\" action=\"".$_SERVER['PHP_SELF']."\">";
      print <<<END


<table cellpadding=0 cellspacing=5 border=1 bgcolor=eeeeee>
<tr align=right><td><b>Brukernavn:</td><td> <input type="text" name="uname"
size=20></td>
<tr align=right><td><b>Passord:</td><td> <input type="password" name="pass"
size=20></td>
<tr align=right><td><b>Nytt passord:</td><td> <input type="password" name="newpass"
size=20></td>
<tr align=right><td><b>Gjenta nytt passord:</td><td> <input type="password" name="newpass2"
size=20></td>
<tr align=center><td></td><td><input type="submit" name="action" value="Send"></td>
</b></table></form>
END;
    }    
    else if (!check_fields($uname, $pass, $newpass, $newpass2) || 
             !call_bofhd($uname, iconv("ISO-8859-1", "UTF-8", $pass), 
                                 iconv("ISO-8859-1", "UTF-8", $newpass2)))
    {
        print "<p>Trykk 'Tilbake' og prøv en gang til</p>"; 
    }
}


function check_fields($uname, $pass, $newpass, $newpass2)
{
    if (!strlen($uname)) {
            print "<hr>\n<p> Du må skrive inn brukernavn </p>";
            return 0;
    }
    if (strcmp($newpass, $newpass2)) {
        print "<hr>\n<p>De nye passordene er ikke like</p>";
        return 0;
    }
    if (!strlen($newpass) || !strcmp($pass, $newpass)) {
        print "<hr>\n<p>Les veiledningen over og prøv på nytt</p>";
        return 0;
    }    
    return 1;
}


/*
########################################################################
#
# Main info
*/

function printInfo()
{
print <<<EOM
<h1>Skifte av passord ved Høgskolen i Sør-Trøndelag</h1>

<p>På denne websiden kan du endre passordet du blant annet bruker for
å få lest eposten din ved Høgskolen i Sør-Trøndelag.</p>

<p>For å endre passord må du gjøre følgende:</p>

<ol>
  <li>Tast inn brukernavnet ditt i feltet 'Brukernavn' nedenfor,
  <li>Tast inn det nåværende passordet ditt i feltet 'Passord'
      nedenfor,
  <li>Tast inn det nye passordet ditt (det du ønsker å bytte til) i
      feltet 'Nytt passord' nedenfor,
  <li>Bekreft det nye passordet ved å taste det en gang til i feltet
      'Gjenta nytt passord' nedenfor,
  <li>Trykk på 'Send'-knappen nedenfor, og vent på bekreftelse fra
      serveren om at det nye passordet er godkjent.
</ol>
<p>Nye passord må bestå av en blanding av store og små bokstaver, tall og
andre tegn.  Det bør ikke inneholde ord som finnes i en ordliste, og
må være på minst 8 tegn.</p>
<p>Du må bytte passord minst en gang i året, helst oftere.  Dersom du
ikke har byttet passord på over et år, vil du bli varslet om dette i
mail.  Dersom du en måned etter et slikt varsel fortsatt ikke har
byttet passord, vil kontoen din bli stengt.  Den vil fortsatt kunne
motta epost, og filene vil bli liggende, men ingen vil kunne bruke
kontoen.  En konto som har vært stengt i mer enn ett år antas å ikke
lenger være i bruk, og vil automatisk bli slettet.</p>

<p>Av sikkerhetshensyn vil all informasjon du registrerer på disse
sidene bli kryptert under overføringen.  Husk at du normalt aldri skal
oppgi ditt brukernavn og passord til en webside, men denne siden
er kryptert og har sertifikat som forteller at siden tilhører Høgskolen i
Sør-Trøndelag. Dette kan du sjekke ved å se på 'egenskapene' til denne
siden.

EOM;
}


// Main

//pageHeader(DEFAULT_DESIGN);
printInfo();
handle_request();
//pageFooter(DEFAULT_DESIGN);

?>
<!-- arch-tag: 6c740716-cc03-443c-b441-9f76c738e773
     (do not change this comment) -->
