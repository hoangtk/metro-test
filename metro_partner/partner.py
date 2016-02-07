from osv import fields, osv

class metro_partner(osv.osv):

    _name = "metro.partner_inquiry"
    _columns = {
        'date':fields.date("Date"),
        'method':fields.selection([
                    ('Alibaba','Alibaba'),
                    ('Email','Email'),
                    ('Phone_call','Phone call'),
                    ('Fax','Fax'),
                    ('Referral','Referral'),
                    ('Other','Other')
                ], 'Method'
        ),
        'inquiry':fields.text("Inquiry"),
        'response':fields.text("Response"),
        'partner':fields.many2one('res.partner','Partner'),
    }
    
    _defaults={
        'date':fields.date.context_today
    }
metro_partner()


class partner(osv.osv):

    _inherit="res.partner"
    _columns = {
        'inquiry':fields.one2many('metro.partner_inquiry','partner','Inquiries'),
        'street': fields.char('Street', size=128, translate=True),
        'street2': fields.char('Street2', size=128, translate=True),
        'city': fields.char('City', size=128, translate=True),
        'create_date': fields.datetime('Creation Date', readonly=True, select=True),
        'parent_name': fields.related('parent_id', 'name', type='char', readonly=True, string='Parent name'),
    }
    def name_get(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = []
        for record in self.browse(cr, uid, ids, context=context):
            name = record.name
            if record.parent_id:
                '''
                when current partner can read by user, but parent can not be read
                if use record.parent_id.name, then the _read_flat() will be trigger on parent_id, and the access checking will throw error
                use related field parent_name can avoid this issue, since in the related._fnct_read(), SUPERUSER_ID will be use to call read()  
                '''
                #name =  "%s (%s)" % (name, record.parent_id.name)
                name = "%s, %s" % (record.parent_name, name)
            if context.get('show_address'):
                name = name + "\n" + self._display_address(cr, uid, record, without_company=True, context=context)
                name = name.replace('\n\n','\n')
                name = name.replace('\n\n','\n')
            if context.get('show_email') and record.email:
                name = "%s <%s>" % (name, record.email)
            res.append((record.id, name))
        return res        
partner()      

class res_country_state(osv.osv):
    _inherit = "res.country.state"
    _columns = {
        'name': fields.char('State Name', size=64, required=True, translate=True,
                            help='Administrative divisions of a country. E.g. Fed. State, Departement, Canton'),
    }   
res_country_state()                  
