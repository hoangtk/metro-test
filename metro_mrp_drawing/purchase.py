# -*- encoding: utf-8 -*-
'''
Created on 24-11-2015

@author: Khai Hoang
'''
from openerp.osv import osv, fields
from openerp.tools.translate import _
from lxml import etree
from openerp.addons.metro import utils
from datetime import datetime
from openerp import tools
from openerp import tools, SUPERUSER_ID
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
from openerp.addons.metro_mrp_drawing.drawing_order import WORK_STEP_LIST
class purchase_order(osv.osv):
    _inherit = "purchase.order"
    def write(self, cr, uid, ids, vals, context=None):
        result = super(purchase_order, self).write(cr, uid, ids, vals, context=context)
        pur_req_obj = self.pool.get('pur.req')
        pur_req_obj.update_move_lines(cr, uid, ids, context=context)
        return result

    def create(self, cr, uid, vals, context=None):
        result = super(purchase_order, self).create(cr, uid, vals, context=context)
        if result:
            order = self.browse(cr, uid, result, context=context)
            if order.req_id:
                req_history_obj = self.pool.get('pur.req.history')
                req_history_obj.create(cr, uid, {
                    'pur_req_id': order.req_id.id,
                    'user_id': uid,
                    'date': datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                    'content': _('Create Purchase Order %s' % order.name),
                    'vals': '%s' % (vals),
                })
            pur_req_obj = self.pool.get('pur.req')
            pur_req_obj.update_move_lines(cr, uid, [result], context=context)
        return result

    def unlink(self, cr, uid, ids, context=None):
        result = super(purchase_order, self).unlink(cr, uid, ids, context=context)
        pur_req_obj = self.pool.get('pur.req')
        pur_req_obj.update_move_lines(cr, uid, ids, context=context)
        return result
purchase_order()
class purchase_order_line(osv.osv):
    _inherit = "purchase.order.line"
    def write(self, cr, uid, ids, vals, context=None):
        result = super(purchase_order_line, self).write(cr, uid, ids, vals, context=context)
        pur_req_obj = self.pool.get('pur.req')
        po_ids = []
        for line in self.browse(cr, uid, ids,context=context):
            if not line.order_id.id in po_ids:
                po_ids.append(line.order_id.id)
        pur_req_obj.update_move_lines(cr, uid, po_ids, context=context)
        return result

    def create(self, cr, uid, vals, context=None):
        result = super(purchase_order_line, self).create(cr, uid, vals, context=context)
        pur_req_obj = self.pool.get('pur.req')
        if result:
            line =  self.browse(cr, uid, result, context=context)
            po_ids = [line.order_id.id]
            pur_req_obj.update_move_lines(cr, uid, po_ids, context=context)
        return result

    def unlink(self, cr, uid, ids, context=None):
        po_ids = []
        for line in self.browse(cr, uid, ids, context=context):
            if not line.order_id.id in po_ids:
                po_ids.append(line.order_id.id)
        result = super(purchase_order_line, self).unlink(cr, uid, ids, context=context)
        pur_req_obj = self.pool.get('pur.req')
        pur_req_obj.update_move_lines(cr, uid, po_ids, context=context)
        return result
purchase_order_line()