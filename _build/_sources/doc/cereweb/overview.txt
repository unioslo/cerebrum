====================
Overview of cereweb
====================

Overview
=========
* Presentation, styling and code is split into their own files and
  directories.

* Presentation
  Presentation of data is done with html, where Cheetah is used to convert
  python templates into html files. These Cheetah-templates are found in
  <cereweb\lib\templates\>.

* Styling
  Html files are styled with cascade style sheet, where Cheetah is used to
  convert templates into css files. These Cheetah-templates are found in 
  <cereweb\htdocs\css\>.

* Code
  Python code-files are found in <cereweb\htdocs\> and <cereweb\lib\>.
  Code which handles requests of web pages from clients are placed in
  <cereweb\htdocs\>, while commonly used code, including the web server,
  is placed in <cereweb\lib\>.

* Javascript
  Javascript-files are found in <cereweb\htdocs\jscript\>.

..
   arch-tag: 53d92f9c-ce52-11da-973a-49a13f61403c
