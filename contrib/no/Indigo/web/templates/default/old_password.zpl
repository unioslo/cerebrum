<span tal:define="title string:Nåværende passord;title_id string:old_passwords" tal:omit-tag=""><span metal:use-macro="tpl/macros/page">
<span metal:fill-slot="body" tal:omit-tag="">

<br>
<hr>
  
  <table border="0">
    <tr><td><strong>Brukernavn:</strong></td> <td tal:content="string: ${uname}"></td></tr>
    <tr><td><strong>Passord:</strong></td><td tal:content="string: ${password}"></td></tr>
  </table>

</span></span></span>
