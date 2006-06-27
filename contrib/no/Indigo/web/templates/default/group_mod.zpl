<span tal:define="title string:Endre gruppemedlemskap;title_id string:group_mod" tal:omit-tag=""><span metal:use-macro="tpl/macros/page">
<span metal:fill-slot="body" tal:omit-tag="">

<p>
Medlemmer:
</p>
<form action="#" method="post">
<input type="HIDDEN" name="action" value="do_group_mod">
<input type="HIDDEN" name="target_id" tal:attributes="value target_id">

<table>
  <tr><th>Navn</th> <th>Type</th></tr>
  <tr valign="top" tal:repeat="m members"
      tal:attributes="class python:test(path('repeat/m/odd'), 'white', 'grey')">
      <td><input type="CHECKBOX" name="remove_member" tal:attributes="value string:${m/entity_id}" tal:content="m/name"></td>
      <!--TODO: fix select stuff real soon-->
      <!--<a tal:attributes="href string:?action=do_select_target&type=${m/type}&entity_id=${m/entity_id}"..>foogroup</a></td>-->
      <td tal:content="m/type">account</td>  
</tr>
</table>

<p>
<input type="SUBMIT" name="choice" value="Meld ut"> (Bare merkede brukere meldes ut).
</p>

<p>
For å melde nye brukere i denne gruppen oppgi ett brukernavn per linje
og klikk på "Meld inn".<br>
</p>

<textarea name="new_users" rows="10" cols="20" tal:content="state/tgt_user_str"></textarea>

<p>
<input type="SUBMIT" name="choice" value="Meld inn">
</p>
</form>

</span></span></span>
