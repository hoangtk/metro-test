# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (c) 2010-2013 Elico Corp. All Rights Reserved.
#    Author: Yannick Gouin <yannick.gouin@elico-corp.com>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it wil    l be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from osv import osv, fields
from openerp import tools
from tools.translate import _
import openerp.addons.decimal_precision as dp

class product_supplierinfo(osv.osv):
    _inherit = 'product.supplierinfo'

    def _calc_products(self, cr, uid, ids, field_names, arg, context=None):
        result = {}
        prod_obj = self.pool.get('product.product')
        for supplier_info in self.browse(cr, uid, ids, context=context):
            result[supplier_info.id] = {}.fromkeys(field_names, 0.0)
            prod_ids = prod_obj.search(cr, uid, [('product_tmpl_id','=',supplier_info.product_id.id)],context=context)
            if len(prod_ids) > 0:
                result[supplier_info.id]['product_product_id'] = prod_ids[0]
            
        return result    
    def _get_product_tmpl_id(self, cr, uid, product_id, context=None):
        if not product_id:
            return False
        prod = self.pool.get('product.product').browse(cr, uid, product_id, context=context)
        return prod.product_tmpl_id.id
        
    def _product_product_write(self, cr, uid, id, name, value, arg, context=None):
        if not value:
            return
        prod_tmpl_id = self._get_product_tmpl_id(cr,uid,value,context=context)
        return self.write(cr, uid, id, {'product_id': prod_tmpl_id}, context=context)
    
    def create(self, cr, uid, data, context=None):
        if 'product_product_id' in data and data['product_product_id'] > 0:
            data['product_id'] = self._get_product_tmpl_id(cr, uid, data['product_product_id'], context=context)
        return super(product_supplierinfo, self).create(cr, uid, data, context)
            
    def onchange_product_product_id(self, cr, uid, ids, product_product_id, context=None):
        prod = self.pool.get('product.product').browse(cr, uid, product_product_id, context=context)
        return {'value': {'product_id': prod.product_tmpl_id.id}}
    
    _columns={
        'name' : fields.many2one('res.partner', 'Supplier', required=False,domain = [('supplier','=',True)], ondelete='cascade', help="Supplier of this product"),              
        'product_id' : fields.many2one('product.template', 'Product', select=1, ondelete='cascade', required=True),
        'product_product_id' : fields.function(_calc_products, type='many2one', relation='product.product', 
                                               string='Product', multi="product_info", store=True,fnct_inv=_product_product_write,),
        'product_product_default_code' : fields.related('product_product_id','default_code',type='char',string='Default Code'),
        'product_product_cn_name' : fields.related('product_product_id','cn_name',type='char',string='Chinese Name'),
        'qty_available' : fields.related('product_product_id','qty_available',type='float',string='Quantity On Hand'),
        'virtual_available' : fields.related('product_product_id','virtual_available',type='float',string='Forecasted Quantity'),
        'min_qty': fields.float('Minimal Quantity', required=True, digits_compute=dp.get_precision('Product Unit of Measure'), 
                                help="The minimal quantity to purchase to this supplier, expressed in the supplier Product Unit of Measure if not empty, in the default unit of measure of the product otherwise."),
    }
product_supplierinfo()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
