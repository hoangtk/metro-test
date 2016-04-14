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
        active_model = context.get('active_model')
        drawing_order_obj = self.pool.get('drawing.order')
        drawing_order_line_obj = self.pool.get('drawing.order.line')
        drawing_order = False
        drawing_order_line = False
        if active_model == 'drawing.order':
            drawing_order = drawing_order_obj.browse(cr, uid, order_id)
        elif active_model == 'drawing.order.line':
            drawing_order_line = drawing_order_line_obj.browse(cr, uid, order_id)
            drawing_order = drawing_order_line.order_id
        else:
            return False
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
        #+++ HoangTK - 03/03/2016: Add procedure to display drawing pdfs cant link to order line
        cant_link_attachments = []
        #--- HoangTK - 03/03/2016: Add procedure to display drawing pdfs cant link to order line
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
            if drawing_order_line:
                #if drawing_order_line.product_id.name == file_name:
                if drawing_order_line.erp_no == file_name:
                    drawing_line_obj.write(cr, uid, [drawing_order_line.id],{
                        'drawing_file_name' : new_file_name,
                    })
                    #Remove old attachment if any:
                    old_attachment_ids = attachment_obj.search(cr, uid, [
                        ('res_id','=', drawing_order_line.id),
                        ('res_model','=','drawing.order.line'),
                        ('res_name','=', new_file_name),
                        ('name','=','drawing_file')]
                    )
                    attachment_obj.unlink(cr, uid, old_attachment_ids)
                    attachment_obj.write(cr, uid, attachment.id, {
                                                          'res_id':drawing_order_line.id,
                                                          'res_model':'drawing.order.line',
                                                          'res_name': new_file_name,
                                                          'name':'drawing_file'
                                                        })
                    break
                else:
                    cant_link_attachments.append(attachment)
                continue
            #product_ids = product_obj.search(cr, uid, [
            #                                           ('name','=',file_name),
            #                                           ])
            #if not product_ids:
                #+++ HoangTK - 03/03/2016: Save the attachment cant linked to order line
                #cant_link_attachments.append(attachment)
                #--- HoangTK - 03/03/2016: Save the attachment cant linked to order line
                #continue
            #product_id = product_ids[0]
            #drawing_line_val = {'order_id':order_id, 'product_id':data.product_id.id, 'drawing_file_name':attachment.name, 'step_ids': step_ids, 'state':'draft'}
            #drawing_line_val = {
            #                    'order_id': order_id,
            #                    'product_id': product_id,
            #                    'drawing_file_name': new_file_name,
            #                    }
            #Search if this product_id exists in drawing order?
            drawing_line_ids = drawing_line_obj.search(cr, uid, [
                                                                 ('order_id','=',order_id),
                                                                #('product_id','=',product_id)
                                                                 ('erp_no', '=', file_name)
                                                                 ])
            if drawing_line_ids:
                #TODO: Need to check if duplicate ERP #
                new_id = drawing_line_ids[0]
                drawing_line_obj.write(cr, uid, drawing_line_ids, {
                                                           'drawing_file_name' : new_file_name,
                                                           })

            #+++ HoangTK - 02/08/2016 : Not create order line anymore
            #else:
            #    new_id = drawing_line_obj.create(cr, uid, drawing_line_val, context=context)
            #--- HoangTK - 02/08/2016 : Not create order line anymore
            #--- HoangTK - 11/19/2015
            #+++ HoangTK - 11/19/2015: Update attachment with new id and name
            #attachment_obj.write(cr, uid, attachment.id, {'res_id':new_id, 'res_model':'drawing.order.line', 'name':'drawing_file'})
                attachment_obj.write(cr, uid, attachment.id, {
                                                          'res_id':new_id, 
                                                          'res_model':'drawing.order.line', 
                                                          'res_name': new_file_name,
                                                          'name':'drawing_file'
                                                        })
            else:
                #+++ HoangTK - 03/03/2016: Save the attachment cant linked to order line
                cant_link_attachments.append(attachment)
                #--- HoangTK - 03/03/2016: Save the attachment cant linked to order line
            #--- HoangTK - 11/19/2015
        #+++ HoangTK - 03/03/2016: Notify users about attachment cant be linked
        if len(cant_link_attachments):
            attachment_name = ','.join(file.name for file in cant_link_attachments)
            if drawing_order_line:
                result = self.pool.get('warning').info(cr, uid, title='Warning', message= _("Attachments %s can not be linked to drawing order line !")% (attachment_name,))
            else:
                result = self.pool.get('warning').info(cr, uid, title='Warning', message= _("Attachments %s can not be linked to drawing order !")% (attachment_name,))
        #--- HoangTK - 03/03/2016: Notify users about attachment cant be linked
        else:
            result = {'type': 'ir.actions.act_window_close'}
        return result
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
