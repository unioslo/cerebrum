<form action="#" method="POST">
  <input type="HIDDEN" name="action" value="do_login">

  <table border=0>
    <tr><td colspan=2></td></tr>
    <tr><td colspan=2></td></tr>
    <tr><td>Brukernavn:</td><td><input type="TEXT" name="uname" size="12"></td></tr>
    <tr><td>Passord:</td><td><input type="password" name="pass" size="12"></td></tr>
  </table>

  <input type="HIDDEN" name="login_id" tal:attributes="value string:${login_id}">

  <p>
    <input type="SUBMIT" value="Logg inn">
  </p>

</form>
