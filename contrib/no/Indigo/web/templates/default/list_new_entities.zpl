<span tal:define="title string:Nye objekter i Cerebrum;title_id string:list_changes" tal:omit-tag=""><span metal:use-macro="tpl/macros/page">
<span metal:fill-slot="body" tal:omit-tag="">

<p>
<form action="#" method="get">
Vis endringer de siste
<input type="HIDDEN" name="action" value="do_list_new_entities">

<select name="dager">
  <option value="0">0
  <option value="1">1
  <option value="3">3
  <option value="5">5
  <option value="7">7
  <option value="14">14
  <option value="30">30
</select> dagene.  <input type="SUBMIT" value="Vis">
</form>
</p>

<span tal:condition="not:changes" tal:omit-tag="">
<p>
  Ingen endringer i den angitte perioden.
</p>
</span>

<span tal:condition="changes" tal:omit-tag="">

<hr>

<!--TODO: del opp basert på endringstype, vis listen ved klikk på e_type-->
<!--TODO: legg inn antall endringer for hver e_type--> 
<h2>Endringer siste (<span tal:content="days" tal:omit-tag=""/>) dager:</h2>

<table border=1>
  <tr><th>Endring</th><TH>Navn</TH> <TH>Diverse</TH> <th>Dato</th></tr>
  <tr valign="top" tal:repeat="c changes"
    tal:attributes="class python:test(path('repeat/c/odd'), 'white', 'grey')">
    <td tal:content="c/change_type"/>

    <span tal:condition="exists:c/person_id" tal:omit-tag="">
      <td><a tal:attributes="href string:?action=show_person_info&entity_id=${c/person_id}" tal:content="c/name">test</a></td>
    </span>
    <span tal:condition="not:exists:c/person_id" tal:omit-tag="">
      <td tal:content="c/name"/>
    </span>
    <td tal:content="c/misc"/>
    <td tal:content="c/tstamp"/>
  </tr>
</table>
</span>

</span></span></span>
