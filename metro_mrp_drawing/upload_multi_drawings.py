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

    def link_attachment(self, cr, uid, drawing_order_line, attachment, drawing_file_name):
        drawing_line_obj = self.pool.get('drawing.order.line')
        attachment_obj = self.pool.get('ir.attachment')
        drawing_line_obj.write(cr, uid, [drawing_order_line.id], {
            'drawing_file_name': drawing_file_name,
        })
        # Remove old attachment if any:
        old_attachment_ids = attachment_obj.search(cr, uid, [
            ('res_id', '=', drawing_order_line.id),
            ('res_model', '=', 'drawing.order.line')])
        attachment_obj.unlink(cr, uid, old_attachment_ids)
        attachment_obj.write(cr, uid, [attachment.id], {
            'res_id': drawing_order_line.id,
            'res_model': 'drawing.order.line',
            'res_name': drawing_file_name,
            'name': drawing_file_name,
        })
        return True

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
        active_model = context.get('active_model')
        drawing_order_obj = self.pool.get('drawing.order')
        drawing_order_line_obj = self.pool.get('drawing.order.line')
        order = False
        order_line = False
        if active_model == 'drawing.order':
            order = drawing_order_obj.browse(cr, uid, order_id)
        elif active_model == 'drawing.order.line':
            order_line = drawing_order_line_obj.browse(cr, uid, order_id)
            order = order_line.order_id
        else:
            return False
        mfg_ids = []
        for mfg_id in order.sale_product_ids:
            mfg_ids.append("ID" + str(mfg_id.name))
        mfg_name = "_".join(mfg_ids)        
        product_obj = self.pool.get('product.product')
        cant_link_attachments = []
        for attachment in data.attachment_ids:
            file_parts = attachment.name.split('.')
            file_name = file_parts[0]
            file_ext = ""
            if len(file_parts) > 1:
                file_ext = file_parts[1]
            new_file_name = file_name + "-" + mfg_name
            if file_ext:
                new_file_name = new_file_name + "." + file_ext
            if order_line:
                if order_line.product_id.name == file_name:
                    self.link_attachment(cr, uid, order_line, attachment, new_file_name)
                    break
                else:
                    cant_link_attachments.append(attachment)
                continue
            product_ids = product_obj.search(cr, uid, [
                                                       ('name','=',file_name),
                                                       ])
            if not product_ids:
                cant_link_attachments.append(attachment)
                continue
            drawing_line_ids = drawing_order_line_obj.search(cr, uid, [
                                                                 ('order_id','=',order_id),
                                                                 ('product_id','in',product_ids)
                                                                 #('name', '=', file_name)
                                                                 ])
            if not drawing_line_ids:
                cant_link_attachments.append(attachment)
            for line in drawing_order_line_obj.browse(cr, uid, drawing_line_ids):
                #TODO: Need to check if duplicate ERP #
                self.link_attachment(cr, uid, line, attachment, new_file_name)

        if len(cant_link_attachments):
            attachment_name = ','.join(file.name for file in cant_link_attachments)
            if order_line:
                result = self.pool.get('warning').info(cr, uid, title='Warning', message= _("Attachments %s can not be linked to drawing order line !")% (attachment_name,))
            else:
                result = self.pool.get('warning').info(cr, uid, title='Warning', message= _("Attachments %s can not be linked to drawing order !")% (attachment_name,))
        else:
            result = {'type': 'ir.actions.act_window_close'}
        return result
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
