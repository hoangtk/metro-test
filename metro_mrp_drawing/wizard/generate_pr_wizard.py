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

    def _get_bom_line(self, cr, uid, order_line):
        return {
            'item_no': order_line.item_no,
            'part_name': order_line.name,
            'description': order_line.description,
            'erp_no': order_line.erp_no,
            'standard': order_line.standard,
            'material': order_line.material,
            'thickness': order_line.thickness,
            'work_steps': order_line.work_steps,
            'part_type': order_line.part_type,
            'bom_qty': order_line.bom_qty,
            'quantity': getattr(order_line,
                                    "%s_need_qty" % order_line.last_step, 0),
            'product_id': order_line.product_id,
        }

    def _create_pr(self, cr, uid, pr_vals):
        pur_req_obj = self.pool.get('pur.req')
        return pur_req_obj.create(cr, uid, pr_vals)

    def _create_pr_line(self, cr, uid, pr_id, bom_line, sequence, delivery_date, drawing_order_id = False,):
        pr_line_obj = self.pool.get('pur.req.line')
        po_line_obj = self.pool.get('purchase.order.line')
        if bom_line['part_type'] != 'PRODUCED':
            product = bom_line['product_id']
            uom = product.uom_id or product.uom_po_id
            pur_req_line_vals = {
                'product_id': product.id,
                'product_uom_id': uom.id,
                'uom_categ_id': product.uom_id.category_id.id,
                'date_required': delivery_date,
                'inv_qty': product.qty_available,
                'req_id': pr_id,
            }
            if drawing_order_id:
                pur_req_line_vals.update({'drawing_order_id': drawing_order_id,})
            #Check if this product already in pr lines
            exist_pr_line_ids = pr_line_obj.search(cr, uid, [
                ('req_id','=',pr_id),
                ('product_id','=',product.id),
            ])
            quantity = bom_line['quantity']
            if exist_pr_line_ids:
                pr_line = pr_line_obj.browse(cr, uid, exist_pr_line_ids[0])
                quantity += pr_line.product_qty
                need_to_order = 0
                if quantity > product.qty_available:
                    need_to_order = quantity - product.qty_available
                pr_line_obj.write(cr, uid, [pr_line.id],{
                    'product_qty' : quantity,
                    'need_order_quantity': need_to_order,
                })
            else:
                need_to_order = 0
                if quantity > product.qty_available:
                    need_to_order = quantity - product.qty_available
                pur_req_line_vals.update({
                    'product_qty': quantity,
                    'sequence': sequence,
                    'erp_no': bom_line['erp_no'],
                    'item_no': bom_line['item_no'],
                    'name': bom_line["description"],
                    'material': bom_line["material"],
                    'standard': bom_line["standard"],
                    'quantity_per_unit': bom_line["bom_qty"],
                    'inv_qty': product.qty_available,
                    'reserved_quantity': 0,
                    'need_order_quantity': need_to_order,
                    'note': '',
                    'price': product.uom_po_price,
                })
                purchase_order_line_ids = po_line_obj.search(cr, uid,
                                                                         [('product_id', '=', product.id),
                                                                          ('state', 'in',
                                                                           ['confirmed', 'approved',
                                                                            'done'])],
                                                                         order="date_planned desc")
                if purchase_order_line_ids:
                    purchase_order_line = po_line_obj.browse(cr, uid, purchase_order_line_ids)[
                        0]
                    pur_req_line_vals.update({'supplier_id': purchase_order_line.order_id.partner_id.id})
                pr_line_obj.create(cr, uid, pur_req_line_vals)
        return True

    def do_generate(self, cr, uid, ids, context=None):
        generate_pr = self.browse(cr, uid, ids, context)[0]
        drawing_order_ids = context.get('drawing_order_ids', False)
        drawing_order_obj = self.pool.get('drawing.order')
        pur_req_obj = self.pool.get('pur.req')
        if drawing_order_ids:
            for order in drawing_order_obj.browse(cr, uid, drawing_order_ids):
                pur_req_ids = pur_req_obj.search(cr, uid, [
                    ('drawing_order_id', '=', order.id)
                ])
                if pur_req_ids:
                    raise osv.except_osv(_("Error!"),
                                         _('A Purchase Requisition of this drawing order is already exist!'))
                pur_req_id = self._create_pr(cr, uid, {
                    'warehouse_id': generate_pr.warehouse_id.id,
                    'drawing_order_id': order.id,
                    'pr_type': 'mfg',
                    'unit': order.product_id.id,
                    'delivery_date': generate_pr.delivery_date,
                    'engineer': uid,
                })
                sequence = 1
                for order_line in order.order_lines:
                    bom_line = self._get_bom_line(cr, uid, order_line)
                    self._create_pr_line(cr, uid, pur_req_id,bom_line,sequence,generate_pr.delivery_date,order.id)
                    sequence += 1
        return True


generate_pr_wizard()
