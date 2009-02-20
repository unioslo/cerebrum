<span tal:define="title string:Endre passord for gruppemedlemmer;title_id string:group_password" tal:omit-tag="">
  <span metal:use-macro="tpl/macros/page">
    <span metal:fill-slot="body" tal:omit-tag="">

      <script type="text/javascript">
      <!--
      function markAll(name, state)
      {
          for (i=0; i < name.length; ++i)
              name[i].checked = state;
      }
      // -->
      </script>

      <p>
        Medlemmer:
      </p>

      <form action="#" method="post" name="group_members">
        <input type="HIDDEN" name="action" value="do_group_password">
        <input type="HIDDEN" name="target_id" tal:attributes="value target_id">

        <table>
          <tr>
            <th>Navn</th> <th>Type</th>
          </tr>
          <tr valign="top" tal:repeat="m members"
              tal:attributes="class python:test(path('repeat/m/odd'), 'white', 'grey')">
            <td><input type="CHECKBOX" name="change_password" 
                       tal:attributes="value string:${m/entity_id}" 
                       tal:content="m/name"></td>
            <td tal:content="m/type">account</td>
          </tr>
        </table>

        <p>
            <script type="text/javascript">
            <!--
            document.write(
              "<input type=\"BUTTON\" name=\"checkall\" value=\"Velg alle\" " +
                     "onClick=\"markAll(document.group_members.change_password, true)\"> " +
              "<input type=\"BUTTON\" name=\"uncheckall\" value=\"Nullstill\" " + 
                     "onClick=\"markAll(document.group_members.change_password, false)\">"
                     );
            //-->
            </script>
            <noscript>
                Sl&aring; p&aring; javascript for raske operasjoner p&aring; avkrysningsboksene.
            </noscript>
        </p>

        <p>
          <input type="SUBMIT" name="choose_some" value="Bytt passord (kun avkryssede)">
        </p>

      </form>
    </span>
  </span>
</span>
