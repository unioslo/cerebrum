import forgetHTML as html
import sci_exp

class TableView:
    """Selects columns and sorts by several columns from a given dataset."""
    def __init__(self, *columns):
        """Defines the initial set of columns to be selected. 
           Other columns might be defined by changing self.columns. Columns is
           a list of strings. See add()."""
        self.columns = columns
        # sort is a list of column names, prepended with + and - to
        # denote ascending or descending sorting. + or - IS required.
        # by default, sorted left to right ascending
        self.sort = ["+" + field for field in self.columns]
        self._width = len(self.columns)
        self._rows = []
        
    def add(self, *data, **fields):
        """Adds a data row with field=value. 
        If positional arguments are given, their value are 
        associated according to fields in self.columns
        
        Example:
        
        >>> t.add(name="stain", fullname="Stian Soiland", tel="92019694")
        >>> t.columns = ("name", "tel")

        t.sorted() will then return a table contaning data from fields 
        'name' and 'tel' from each row.
        """
        myfields = dict(zip(self.columns, data))
        myfields.update(fields)
        self._rows.append(myfields)
    
    def _sorter(self, a, b):
        """Sorts according to rules in self.sort. This is called for each
           elements that needs to be compared."""
        for column in self.sort:
            way = column[0]
            if way == "+":
                way = 1    
            elif way == "-":
                way = -1
            else:        
                raise "Invalid sort order %s - should start with + or -" % column
            column = column[1:]
            diff = cmp(a.get(column), b.get(column))
            if diff:
                return way * diff
        return diff        
        
    def sorted(self):
        """Returns a two dimensional sorted list. 
           Rows are taken from self._rows with the columns selected from
           self.columns, and sorted by the rules in self.sort."""
        self._rows.sort(self._sorter)
        return [[row.get(column) for column in self.columns] for row in self._rows] 

    def html(self, **titles):
        """Returns a HTML version of the sorted table. Keyword arguments
           defines headers for the columns, only titles which names are
           in self.columns will be output."""
        table = html.SimpleTable(header="row")
        headers = []
        for column in self.columns:
            # header defined as keyword argument
            header = titles.get(column)
            if header is None:
                # select header from self.columns
                header = column.capitalize()
            headers.append(header)
        table.add(*headers)       
        for row in self.sorted():
            # Prepare values to be HTML-able
            row = map(prepareForHTML, row)
            table.add(*row)
        return table    

def _prepareForHTML(value):
    """Returns a forgetHTML-compatible value"""
    if isinstance(value, html.Element):
        return value
    if type(value) in (int, long):
        return Value(value, decimals=0)
    if type(value) == float:
        return Value(value)
    if value is None:
        return ""        
    return str(value)

class Value(html.Text):
    """A special html-text containing a number.
       The item is sorted according to the numeric value, but 
       printed with the given decimal counts and the optional unit. 
       """
    def __init__(self, value, unit="", decimals=2, 
                 sciunit=False, **kwargs):
        try:
            _ = value + 0
            assert _ == value
        except:
            raise "Value %r not a number" % value
        self.value = value
        self.decimals = decimals
        self.unit = unit
        self.sciunit = sciunit
        html.Text.__init__(self, self._display(), **kwargs)
    def _display(self):
        format = "%0." + str(self.decimals) + "f"
        if self.sciunit:
            (value, unit) = sci_exp.sci(self.value)
            unit = unit + self.unit
        else:
            unit = self.unit
            value = self.value
        formatted = format % value
        return formatted + unit
    def __cmp__(self, other):
        if isinstance(other, html.TableCell):
            return cmp(self.value, other.value)
        else:
            return cmp(self.value, other)

