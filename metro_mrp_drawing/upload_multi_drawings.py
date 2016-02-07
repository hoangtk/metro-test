# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from openerp.osv import fields, osv
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp

class upload_multi_drawings(osv.osv_memory):
    _name = "upload.multi.drawings"
    _description = "Upload multi drawings"

    _columns = {
        'product_id': fields.many2one('product.product','Product'),
        'step_ids': fields.many2many('drawing.step', string='Working Steps'),
        'attachment_ids': fields.many2many('ir.attachment','upload_multi_drawings_ir_attachments_rel','upload_drawing_id', 'attachment_id', 'Drawings'),
    }

    def do_add(self, cr, uid, ids, context=None):
        """ To create drawings lines
        @param self: The object pointer.
        @param cr: A database cursor
        @param uid: ID of the user currently logged in
        @param ids: the ID or list of IDs if we want more than one
        @param context: A standard dictionary
        @return:
        """
        if context is None:
            context = {}
        order_id = context.get('active_id')
        if not order_id:
            return False
        data = self.browse(cr, uid, ids[0], context=context)
        #+++ HoangTK - 11/19/2015: Add drawing_order_obj,product_obj
        drawing_order_obj = self.pool.get('drawing.order')
        drawing_order = drawing_order_obj.browse(cr, uid, order_id)
        mfg_ids = []
        for mfg_id in drawing_order.sale_product_ids:
            mfg_ids.append("ID" + str(mfg_id.name))
        mfg_name = "_".join(mfg_ids)        
        product_obj = self.pool.get('product.product')
        #--- HoangTK - 11/19/2015
        drawing_line_obj = self.pool.get('drawing.order.line')
        attachment_obj = self.pool.get('ir.attachment')
        #+++ HoangTK - 11/19/2015: Don't need step_ids anymore, use work_steps
        #step_ids = [(4,step.id) for step in data.step_ids]
        #--- HoangTK - 11/19/2015
        for attachment in data.attachment_ids:
            #+++ HoangTK - 11/19/2015: Automatically add attachment to drawing order line
            file_parts = attachment.name.split('.') 
            file_name = file_parts[0]
            file_ext = ""
            if len(file_parts) > 1:
                file_ext = file_parts[1]
            new_file_name = file_name + "-" + mfg_name
            if file_ext:
                new_file_name = new_file_name + "." + file_ext                
            product_ids = product_obj.search(cr, uid, [
                                                       ('name','=',file_name),
                                                       ])
            if not product_ids:
                continue
            product_id = product_ids[0]
            #drawing_line_val = {'order_id':order_id, 'product_id':data.product_id.id, 'drawing_file_name':attachment.name, 'step_ids': step_ids, 'state':'draft'}
            drawing_line_val = {
                                'order_id': order_id,
                                'product_id': product_id,
                                'drawing_file_name': new_file_name,
                                }
            #Search if this product_id exists in drawing order?
            drawing_line_ids = drawing_line_obj.search(cr, uid, [
                                                                 ('order_id','=',order_id),
                                                                 ('product_id','=',product_id)
                                                                 ])
            if drawing_line_ids:
                new_id = drawing_line_ids[0]
                drawing_line_obj.write(cr, uid, new_id, {
                                                           'drawing_file_name' : new_file_name,
                                                           })
            else:
                new_id = drawing_line_obj.create(cr, uid, drawing_line_val, context=context)
            #--- HoangTK - 11/19/2015
            #+++ HoangTK - 11/19/2015: Update attachment with new id and name
            #attachment_obj.write(cr, uid, attachment.id, {'res_id':new_id, 'res_model':'drawing.order.line', 'name':'drawing_file'})
            attachment_obj.write(cr, uid, attachment.id, {
                                                          'res_id':new_id, 
                                                          'res_model':'drawing.order.line', 
                                                          'res_name': new_file_name,
                                                          'name':'drawing_file'
                                                        })
            #--- HoangTK - 11/19/2015
        
        return {'type': 'ir.actions.act_window_close'}   
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
