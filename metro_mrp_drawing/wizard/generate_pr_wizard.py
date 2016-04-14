# -*- coding: utf-8 -*-
import time
from openerp.osv import fields, osv
from openerp.osv.orm import browse_record, browse_null
from openerp.tools.translate import _
import datetime
import openerp.tools as tools
from openerp.addons.metro_mrp_drawing.drawing_order import WORK_STEP_LIST


class generate_pr_wizard(osv.osv_memory):
    _name = 'generate.pr.wizard'
    _description = 'Generate PR Wizard'
    _columns = {
        'delivery_date': fields.date('Delivery Date', required=True),
        'warehouse_id': fields.many2one('stock.warehouse', 'Warehouse', required=True),
    }

    def do_generate(self, cr, uid, ids, context=None):
        generate_pr = self.browse(cr, uid, ids, context)[0]
        drawing_order_ids = context.get('drawing_order_ids', False)
        drawing_order_obj = self.pool.get('drawing.order')
        drawing_order_line_obj = self.pool.get('drawing.order.line')
        pur_req_obj = self.pool.get('pur.req')
        pur_req_line_obj = self.pool.get('pur.req.line')
        purchase_order_line_obj = self.pool.get('purchase.order.line')
        missing_erp_no = []
        if drawing_order_ids:
            for order in drawing_order_obj.browse(cr, uid, drawing_order_ids):
                pur_req_ids = pur_req_obj.search(cr, uid, [
                    ('drawing_order_id', '=', order.id)
                ])
                if pur_req_ids:
                    raise osv.except_osv(_("Error!"),
                                         _('A Purchase Requisition of this drawing order is already exist!'))
                pur_req_vals = {
                    'warehouse_id': generate_pr.warehouse_id.id,
                    'drawing_order_id': order.id,
                    'pr_type': 'mfg',
                    'unit': order.product_id.id,
                    'delivery_date': generate_pr.delivery_date,
                    'engineer': uid,
                }
                pur_req_id = pur_req_obj.create(cr, uid, pur_req_vals)
                sequence = 1
                erp_no_list = {}
                for line in order.order_lines:
                    if line.part_type != 'PRODUCED':
                        if not line.erp_no:
                            missing_erp_no.append(line.item_no)
                        if not line.erp_no in erp_no_list:
                            erp_no_list.update({line.erp_no: True})
                            product = line.product_id
                            uom = product.uom_id or product.uom_po_id
                            pur_req_line_vals = {
                                'product_id': product.id,
                                'product_uom_id': uom.id,
                                'drawing_order_id': order.id,
                                'uom_categ_id': product.uom_id.category_id.id,
                                'date_required': generate_pr.delivery_date,
                                'inv_qty': product.qty_available,
                                'req_id': pur_req_id,
                            }
                            duplicate_erp_no_line_ids = drawing_order_line_obj.search(cr, uid, [
                                ('order_id', '=', line.order_id.id),
                                ('product_id', '=', line.product_id.id),
                            ])
                            quantity = 0
                            for duplicate_erp_no_line in drawing_order_line_obj.browse(cr, uid,
                                                                                       duplicate_erp_no_line_ids):
                                quantity += getattr(duplicate_erp_no_line,
                                                    "%s_need_qty" % duplicate_erp_no_line.last_step, 0)
                            need_to_order = 0
                            if quantity > product.qty_available:
                                need_to_order = quantity - product.qty_available
                            pur_req_line_vals.update({
                                'product_qty': quantity,
                                'sequence': sequence,
                                'erp_no': line.erp_no,
                                'name': line.description,
                                'material': line.material,
                                'standard': '',
                                'quantity_per_unit': line.bom_qty,
                                'inv_qty': product.qty_available,
                                'reserved_quantity': 0,
                                'need_order_quantity': need_to_order,
                                'note': '',
                                'price': product.uom_po_price,
                            })
                            purchase_order_line_ids = purchase_order_line_obj.search(cr, uid,
                                                                                     [('product_id', '=', product.id),
                                                                                      ('state', 'in',
                                                                                       ['confirmed', 'approved',
                                                                                        'done'])],
                                                                                     order="date_planned desc")
                            if purchase_order_line_ids:
                                purchase_order_line = purchase_order_line_obj.browse(cr, uid, purchase_order_line_ids)[
                                    0]
                                pur_req_line_vals.update({'supplier_id': purchase_order_line.order_id.partner_id.id})
                            pur_req_line_obj.create(cr, uid, pur_req_line_vals)
                            sequence += 1
        if len(missing_erp_no) > 0:
            return self.pool.get('warning').info(cr, uid, title='Warning', message=_("Parts (%s) don't have erp #.")% ','.join(missing_erp_no))
        return True


generate_pr_wizard()
