# -*- encoding: utf-8 -*-
from openerp.osv import fields,osv
from openerp.tools.translate import _
from openerp.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT,DEFAULT_SERVER_DATE_FORMAT
from datetime import datetime
from openerp import netsvc
PR_TYPES = [('normal', 'Normal PR'),
            ('sourcing', 'Sourcing PR'),
            ('procurement', 'Procurement PR'),
            ('mfg', 'MFG PR')]

class pur_req_history(osv.osv):
    _name = "pur.req.history"
    _description = "Purchase Request History"
    _columns = {
        'date': fields.datetime('Modified Date',readonly=True),
        'pur_req_id': fields.many2one('pur.req','Purchase Request',readonly=True),
        'user_id': fields.many2one('res.users','User',readonly=True),
        'content': fields.char('Content',readonly=True),
        'vals': fields.char('Update Values',readonly=True,size=256),
    }
pur_req_history()
class pur_req_move1(osv.osv):
    _name = "pur.req.move1"
    _description = "Purchase Request Move 1"
    _columns = {
        "pur_req_id": fields.many2one("pur.req","Purchase Request",readonly=True),
        "product_id": fields.many2one("product.product","Product",readonly=True),
        "erp_no": fields.char("ERP #",size=128,readonly=True),
        "quantity": fields.integer("Quantity",readonly=True),
    }
pur_req_move1()
class pur_req_move2(osv.osv):
    _name = "pur.req.move2"
    _description = "Purchase Request Move 2"
    _columns = {
        "pur_req_id": fields.many2one("pur.req","Purchase Request",readonly=True),
        "product_id": fields.many2one("product.product","Product",readonly=True),
        "erp_no": fields.char("ERP #",size=128,readonly=True),
        "quantity": fields.integer("Quantity",readonly=True),
    }
pur_req_move2()
class pur_req_move3(osv.osv):
    _name = "pur.req.move3"
    _description = "Purchase Request Move 3"
    _columns = {
        "pur_req_id": fields.many2one("pur.req","Purchase Request",readonly=True),
        "product_id": fields.many2one("product.product","Product",readonly=True),
        "erp_no": fields.char("ERP #",size=128,readonly=True),
        "quantity": fields.integer("Quantity",readonly=True),
    }
pur_req_move3()
class pur_req_line(osv.osv):
    _name = "pur.req.line"
    _inherit = "pur.req.line"
    _columns = {
        "sequence": fields.integer('#', readonly=True),
        "pr_type": fields.related('req_id', 'pr_type', type='selection',
                                  selection=PR_TYPES,
                                  string='PR Type', readonly=True, store=True, select=1),
        "erp_no": fields.char("ERP #", size=128,readonly=True),
        "item_no": fields.char("Item No", size=128, readonly=True),
        "name": fields.char("Name", size=128),
        "material": fields.char("Material", size=128, ),
        "standard": fields.char("Standard", size=128, readonly=True),
        "quantity_per_unit": fields.float("Quantity Per Unit", readonly=True),
        "total_quantity": fields.float("Total Quantity", readonly=True),
        "stock_quantity": fields.float("Stock Quantity", readonly=True),
        "reserved_quantity": fields.float("Reserved Quantity", readonly=True),
        "need_order_quantity": fields.float("Need to Order", readonly=True),
        "note": fields.char("Note", size=128, ),
        "price": fields.float("Price", readonly=True),
    }
    def create(self, cr, uid, vals, context=None):
        result = super(pur_req_line,self).create(cr, uid, vals,context=context)
        if result:
            line = self.browse(cr, uid, result,context=context)
            sequence = len(line.req_id.line_ids)
            super(pur_req_line,self).write(cr, uid, [result],{'sequence': sequence})
            req_history_obj = self.pool.get('pur.req.history')
            req_history_obj.create(cr, uid, {
                'pur_req_id': line.req_id.id,
                'user_id': uid,
                'date': datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                'content': _('Create Purchase Request Line'),
                'vals': '%s' % (vals),
            })
        return result
    def write(self, cr, uid, ids, vals, context=None):
        result = super(pur_req_line, self).write(cr, uid, ids, vals,context=context)
        req_history_obj = self.pool.get('pur.req.history')
        for line in self.browse(cr, uid, ids, context=context):
            req_history_obj.create(cr, uid, {
                'pur_req_id': line.req_id.id,
                'user_id': uid,
                'date': datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                'content': _('Update Purchase Request Line'),
                'vals': '%s' % (vals),
            })
    _order = "sequence asc"
class pur_req(osv.osv):
    _name = "pur.req"
    _inherit = "pur.req"

    def _get_days_progress(self, cr, uid, ids, name, args, context=None):
        result = {}
        for req in self.browse(cr, uid, ids):
            result[req.id] = 0
            if req.date_confirm:
                date_now = date_now = datetime.now()
                date_confirm = datetime.strptime(req.date_confirm, DEFAULT_SERVER_DATETIME_FORMAT)
                delta = date_now - date_confirm
                result[req.id] = delta.days
        return result

    def reserved_products(self, cr, uid, pr_ids):
        pr_reserve_obj = self.pool.get('pur.req.reserve')
        pr_line_obj = self.pool.get('pur.req.line')
        for pr in self.browse(cr, uid, pr_ids):
            for line in pr.line_ids:
                reserve_vals = {
                    'req_id': pr.id,
                    'product_id': line.product_id.id,
                    'location_id': pr.warehouse_id.lot_stock_id.id,
                }
                if line.product_qty >= line.product_id.qty_available:
                    reserve_vals.update({
                        'product_qty': line.product_id.qty_available
                    })
                    pr_line_obj.write(cr, uid, [line.id], {
                        'reserved_quantity': line.product_id.qty_available,
                        'inv_qty': line.product_id.qty_available,
                    })
                else:
                    reserve_vals.update({
                        'product_qty': line.product_qty
                    })
                    pr_line_obj.write(cr, uid, [line.id], {
                        'reserved_quantity': line.product_qty,
                        'inv_qty': line.product_qty,
                    })
                pr_reserve_obj.create(cr, uid, reserve_vals)
        return True

    def unreserved_products(self, cr, uid, pr_ids):
        pr_reserve_obj = self.pool.get('pur.req.reserve')
        pr_reserve_ids = pr_reserve_obj.search(cr, uid, [('req_id', 'in', pr_ids)])
        pr_reserve_obj.unlink(cr, uid, pr_reserve_ids)

    def wkf_confirm_req(self, cr, uid, ids, context=None):
        res = super(pur_req,self).wkf_confirm_req(cr, uid, ids, context=context)
        self.reserved_products(cr, uid, ids)
        return res

    def wkf_cancel_req(self, cr, uid, ids, context=None):
        res = super(pur_req, self).wkf_cancel_req(cr, uid, ids, context=context)
        self.unreserved_products(cr, uid, ids)
        return res

    _columns = {
        'pr_type': fields.selection(PR_TYPES,string='PR Type'),
        'drawing_order_id': fields.many2one('drawing.order','Drawing Order',readonly=True),
        'date_create': fields.datetime('Creation Date', readonly=True),
        'date_confirm': fields.datetime('Confirm Date', readonly=True),
        'unit': fields.many2one('product.product','Unit',readonly=True),
        'is_full_pr': fields.boolean('Is Full PR or Sub-Assembly?'),
        'engineer': fields.many2one('res.users','Engineer',readonly=True),
        'assigned_to': fields.many2one('res.users','Assigned To',readonly=True),
        'delivery_date': fields.date('Delivery date (ETA)'),
        'progress': fields.float('Progress',readonly=True),
        'days_progress': fields.function(_get_days_progress,string='Days in progress',type="float",readony=True),
        'supplier_no': fields.integer('Supplier No',readonly=True),
        'history_ids': fields.one2many('pur.req.history','pur_req_id','History',ondelete='cascade',readonly=True),
        'move1_lines': fields.one2many('pur.req.move1','pur_req_id','Move1 Lines',ondelete='cascade',readonly=True),
        'move2_lines': fields.one2many('pur.req.move2','pur_req_id','Move2 Lines',ondelete='cascade',readonly=True),
        'move3_lines': fields.one2many('pur.req.move3','pur_req_id','Move3 Lines',ondelete='cascade',readonly=True),
    }
    _defaults = {
        'pr_type': 'normal',
        'date_create': lambda *a: datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
    }


    def print_pr_mfg(self, cr, uid, ids, context):
        mod_obj = self.pool.get('ir.model.data')
        res = mod_obj.get_object_reference(cr, uid, 'metro_mrp_drawing', 'view_print_pr_mfg_wizard')
        res_id = res and res[1] or False
        return {
            'name': 'Print PR List',
            'res_model': 'print.pr.mfg.wizard',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': [res_id],
            'context': {'pr_ids': ids},
            'target': 'new'
        }
    def create(self, cr, uid, vals, context=None):
        result = super(pur_req, self).create(cr, uid, vals, context=context)
        req_history_obj = self.pool.get('pur.req.history')
        if result:
            req_history_obj.create(cr, uid, {
                'pur_req_id': result,
                'user_id': uid,
                'date': datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                'content': _('Create Purchase Request'),
                'vals': '%s' % (vals),
            })
        return result
    def write(self, cr, uid, ids, vals, context=None):
        if vals.get('state',False) == 'confirmed':
            vals.update({'date_confirm': datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT)})
        result = super(pur_req, self).write(cr, uid, ids, vals, context=context)
        if 'state' in vals:
            req_history_obj = self.pool.get('pur.req.history')
            for req in self.browse(cr, uid, ids, context=context):
                req_history_obj.create(cr, uid, {
                    'pur_req_id': req.id,
                    'user_id': uid,
                    'date': datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                    'content': _('State Changed to %s') % vals['state'],
                    'vals': '%s' % (vals),
                })
            if vals['state'] == 'done':
                self.unreserved_products(cr, uid, ids)
        return result

    def update_move_lines(self, cr, uid, po_ids, context=None):
        req_ids = []
        purchase_order_obj = self.pool.get('purchase.order')
        for order in purchase_order_obj.browse(cr, uid, po_ids, context=context):
            if order.req_id:
                if not order.req_id.id in req_ids:
                    req_ids.append(order.req_id.id)
        req_move1_obj = self.pool.get('pur.req.move1')
        req_move2_obj = self.pool.get('pur.req.move2')
        req_move3_obj = self.pool.get('pur.req.move3')
        purchase_order_line_obj = self.pool.get('purchase.order.line')
        for req in self.browse(cr, uid, req_ids, context=context):
            req_po_ids = [req_po.id for req_po in req.po_ids]
            for req_line in req.line_ids:
                move1_qty = 0
                move2_qty = 0
                move3_qty = 0
                po_line_ids = purchase_order_line_obj.search(cr, uid, [
                    ('order_id','in',req_po_ids),
                    ('product_id','=',req_line.product_id.id)
                ])
                for po_line in purchase_order_line_obj.browse(cr, uid, po_line_ids, context=context):
                    if po_line.state in ['draft','sent']:
                        move1_qty += po_line.product_qty
                    if po_line.state in ['confirmed']:
                        move2_qty += po_line.product_qty
                    if po_line.state in ['approved']:
                        move3_qty += po_line.product_qty - po_line.receive_qty
                move1_ids = req_move1_obj.search(cr, uid, [('pur_req_id','=',req.id),
                                                           ('product_id','=',req_line.product_id.id)])
                if move1_ids:
                    if move1_qty > 0:
                        req_move1_obj.write(cr, uid, move1_ids, {'quantity': move1_qty})
                    else:
                        req_move1_obj.unlink(cr, uid, move1_ids)
                elif move1_qty > 0:
                    req_move1_obj.create(cr, uid, {
                        'pur_req_id': req.id,
                        'quantity': move1_qty,
                        'erp_no': req_line.product_id.default_code,
                        'product_id': req_line.product_id.id,
                    })
                move2_ids = req_move2_obj.search(cr, uid, [('pur_req_id', '=', req.id),
                                                           ('product_id', '=', req_line.product_id.id)])
                if move2_ids:
                    if move2_qty > 0:
                        req_move2_obj.write(cr, uid, move2_ids, {'quantity': move2_qty})
                    else:
                        req_move2_obj.unlink(cr, uid, move2_ids)
                elif move2_qty > 0:
                    req_move2_obj.create(cr, uid, {
                        'pur_req_id': req.id,
                        'quantity': move2_qty,
                        'erp_no': req_line.product_id.default_code,
                        'product_id': req_line.product_id.id,
                    })
                move3_ids = req_move3_obj.search(cr, uid, [('pur_req_id', '=', req.id),
                                                           ('product_id', '=', req_line.product_id.id)])
                if move3_ids:
                    if move3_qty > 0:
                        req_move3_obj.write(cr, uid, move3_ids, {'quantity': move3_qty})
                    else:
                        req_move3_obj.unlink(cr, uid, move3_ids)
                elif move3_qty > 0:
                    req_move3_obj.create(cr, uid, {
                        'pur_req_id': req.id,
                        'quantity': move3_qty,
                        'erp_no': req_line.product_id.default_code,
                        'product_id': req_line.product_id.id,
                    })

pur_req()