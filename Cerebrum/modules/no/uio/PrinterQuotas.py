from Cerebrum.Entity import Entity

# TBD: Should this inherit from Entity or object?
class PrinterQuotas(Entity):
    #__metaclass__ = Utils.mark_update

    __read_attr__ = ('__in_db',)
    __write_attr__ = ('account_id', 'printer_quota', 'pages_printed',
                      'pages_this_semester', 'termin_quota',
                      'has_printerquota', 'weekly_quota', 'max_quota')

    def clear(self):
        super(PrinterQuotas, self).clear()
        for attr in PrinterQuotas.__read_attr__:
            if hasattr(self, attr):
                delattr(self, attr)
        for attr in PrinterQuotas.__write_attr__:
            setattr(self, attr, None)
        self.__updated = False

    def populate(self, account_id, printer_quota, pages_printed,
                 pages_this_semester, termin_quota, has_printerquota,
                 weekly_quota, max_quota):
        try:
            if not self.__in_db:
                raise RuntimeError, "populate() called multiple times."
        except AttributeError:
            self.__in_db = False
        for k in locals():
            setattr(self, k, locals[k])

    def find(self, entity_id):
        self.__super.find(entity_id)

        (self.account_id, self.printer_quota, self.pages_printed,
         self.pages_this_semester, self.termin_quota,
         self.has_printerquota, self.weekly_quota, self.max_quota) = self.query_1("""
        SELECT account_id, printer_quota, pages_printed,
          pages_this_semester, termin_quota, has_printerquota,
          weekly_quota, max_quota
        FROM [:table schema=cerebrum name=printerquotas]
        WHERE account_id=:entity_id""", {'entity_id': entity_id})
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = False

    def write_db(self):
        # self.__super.write_db()
        # TODO: Due to a bug somewhere, self.__updated is not set by pq.py SUBP
        if 1 or self.__updated:
            is_new = not self.__in_db
            cols = {
                'account_id': self.account_id,
                'printer_quota': self.printer_quota,
                'pages_printed': self.pages_printed,
                'pages_this_semester': self.pages_this_semester,
                'termin_quota': self.termin_quota,
                'has_printerquota': self.has_printerquota,
                'weekly_quota': self.weekly_quota,
                'max_quota': self.max_quota
                }
            if is_new:
                self.execute("""
                INSERT INTO [:table schema=cerebrum name=printerquotas]
                (%s) VALUES (%s)""" % (", ".join(cols.keys()),
                                       ", ".join([":%s" % t for t in cols.keys()]
                                                 )), cols)
            else:
                self.execute("""
                UPDATE [:table schema=cerebrum name=printerquotas]
                SET %s WHERE account_id=:account_id""" % 
                             (", ".join(["%s=:%s" % (t,t) for t in cols.keys()])), cols)
        else:
            is_new = None
        return is_new

