<span tal:define="title string:Endre gruppemedlemmer;title_id string:group_mod" tal:omit-tag=""><span metal:use-macro="tpl/macros/page">
<span metal:fill-slot="body" tal:omit-tag="">

Nåværende medlemmer
<form action="#" method="post">
<input type="HIDDEN" name="action" value="do_group_mod">
<input type="HIDDEN" name="target_id" tal:attributes="value target_id">

<table>
  <tr><th>Type</th> <th>Navn</th></tr>
  <tr valign="top" tal:repeat="m members"
      tal:attributes="class python:test(path('repeat/m/odd'), 'white', 'grey')">
    <td tal:content="m/type">account</td>
    <td><input type="CHECKBOX" name="remove_member" tal:attributes="value string:${m/entity_id}"><a tal:attributes="href string:?action=do_select_target&type=${m/type}&entity_id=${m/entity_id}" tal:content="m/name">foogroup</a></td>
  </tr>
</table>
<input type="SUBMIT" name="choice" value="Fjern"> merkede medlemmer.

<p>

For å legge til nye medlemmer, oppgi brukernavn adskilt av linjeskift
og velg "Legg til"<br>

<textarea name="new_users" rows="10" cols="20" tal:content="state/tgt_user_str"></textarea>
<br>
<input type="SUBMIT" name="choice" value="Legg til"> nye medlemmer.

</form>

</span></span></span>
