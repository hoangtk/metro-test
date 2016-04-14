# -*- coding: utf-8 -*-s
from openerp.osv import fields, osv
from openerp.tools.translate import _

class res_company(osv.osv):
    _name = 'res.company'
    _inherit = 'res.company'
    _columns = {
        'stamp': fields.binary('Company Stamp'),
        'stamp_landscape': fields.binary('Company Stamp Landscape'),
        'stamp_portrait': fields.binary('Company Stamp Portrait')
    }
res_company()