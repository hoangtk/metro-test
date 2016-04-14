# -*- coding: utf-8 -*-
import time
from openerp import netsvc
from openerp.osv import fields, osv
from openerp.osv.orm import browse_record, browse_null
from openerp.tools.translate import _
import datetime
from dateutil.relativedelta import relativedelta
import openerp.tools as tools
from openerp.addons.metro_mrp_drawing.drawing_order import WORK_STEP_LIST
import openerp.addons.decimal_precision as dp


class pr_generate_po_wizard(osv.osv_memory):
    _name = "pr.generate.po.wizard"
    _description = "PR Generate PO Wizard"
    _columns = {
        "pr_id": fields.many2one('pur.req', 'Purchase Request', readonly=True),
        "po_ids": fields.one2many('pr.generate.po.wizard.po', 'wizard_id', string="Purchase Order")
    }


    def default_get(self, cr, uid, fields, context=None):
        """
         To get default values for the object.
         @param self: The object pointer.
         @param cr: A database cursor
         @param uid: ID of the user currently logged in
         @param fields: List of fields for which we want default values
         @param context: A standard dictionary
         @return: A dictionary with default values for all field in ``fields``
        """
        line_data = []
        if context is None:
            context = {}
        res = super(pr_generate_po_wizard, self).default_get(cr, uid, fields, context=context)
        record_id = context and context.get('active_id', False) or False
        req_obj = self.pool.get('pur.req')
        req = req_obj.browse(cr, uid, record_id, context=context)
        if req:
            partner_obj = self.pool.get('res.partner')
            req_line_obj = self.pool.get('pur.req.line')
            supplier_ids = []
            supplier_quantity = {}
            for req_line in req.line_ids:
                if req_line.supplier_id:
                    if not req_line.supplier_id.id in supplier_ids:
                        supplier_ids.append(req_line.supplier_id.id)
                        supplier_quantity.update({req_line.supplier_id.id : req_line.product_qty_remain})
                    else:
                        supplier_quantity[req_line.supplier_id.id] += req_line.product_qty_remain
            po_vals = []
            for supplier in partner_obj.browse(cr, uid, supplier_ids):
                po_val = {
                    'supplier_id':supplier.id,
                    'total_quantity': supplier_quantity[supplier.id],
                }
                req_line_ids = req_line_obj.search(cr, uid, [
                    ('req_id','=',req.id),
                    ('supplier_id','=',supplier.id),
                ])
                req_lines = req_line_obj.browse(cr, uid, req_line_ids)
                po_line_vals = []
                for req_line in req_lines:
                    po_line_vals.append({
                        'product_id': req_line.product_id.id,
                        'quantity': req_line.product_qty_remain,
                        'price': req_line.price,
                        'uom_id': req_line.product_uom_id.id,
                        'req_line_id': req_line.id,
                        'date_required': req_line.date_required,
                    })
                po_val.update({'line_ids': po_line_vals})
                po_vals.append(po_val)
            res.update({'po_ids': po_vals})
        return res

    def view_init(self, cr, uid, fields_list, context=None):
        """
         Creates view dynamically and adding fields at runtime.
         @param self: The object pointer.
         @param cr: A database cursor
         @param uid: ID of the user currently logged in
         @param context: A standard dictionary
         @return: New arch of view with new columns.
        """
        if context is None:
            context = {}
        res = super(pr_generate_po_wizard, self).view_init(cr, uid, fields_list, context=context)
        record_id = context and context.get('active_id', False)
        if record_id:
            req_obj = self.pool.get('pur.req')
            req = req_obj.browse(cr, uid, record_id, context=context)
            if req.state == 'draft':
                raise osv.except_osv(_('Warning!'),
                                     _("You may only generate purchase orders based on confirmed requisitions!"))
            valid_lines = 0
            for line in req.line_ids:
                if not line.generated_po:
                    valid_lines += 1
            if not valid_lines:
                raise osv.except_osv(_('Warning!'), _("No available products need to generate purchase order!"))
        return res

    def do_generate(self, cr, uid, ids, context=None):
        record_id = context and context.get('active_id', False) or False
        wizard = self.browse(cr, uid, ids, context=context)[0]
        req = self.pool.get('pur.req').browse(cr, uid, record_id, context=None);
        result_po_ids = []
        for po_id in wizard.po_ids:
            po_data = {'origin': req.name,
                       'req_id': record_id,
                       'partner_id': po_id.supplier_id.id,
                       'warehouse_id': req.warehouse_id.id,
                       'notes': req.remark,
                       'company_id': req.company_id.id,
                       'lines': []}
            po_lines = []
            for line in po_id.line_ids:
                po_line = {'product_id': line.product_id.id,
                           'product_qty': line.quantity,
                           'product_uom': line.uom_id.id,
                           'req_line_id': line.req_line_id.id,
                           'date_planned': line.date_required,
                           'price_unit': line.price,
                           'name': (line.req_reason or ''),
                           'supplier_prod_id': line.supplier_prod_id,
                           'supplier_prod_name': line.supplier_prod_name,
                           'supplier_prod_code': line.supplier_prod_code,
                           'supplier_delay': line.supplier_delay
                           }
                mfg_ids = line.mfg_ids and [mfg_id.id for mfg_id in line.mfg_ids] or []
                procurement_id = line.req_line_id.procurement_ids and line.req_line_id.procurement_ids[0] or False
                if procurement_id:
                    if procurement_id.move_id:
                        # add the move_dest_id for the po_line
                        po_line.update({'move_dest_id': procurement_id.move_id.id})
                    if procurement_id.mfg_ids and len(procurement_id.mfg_ids) > 0:
                        mfg_ids.extend([mfg_id.id for mfg_id in procurement_id.mfg_ids])
                if mfg_ids:
                    po_line.update({'mfg_ids': [[6, False, mfg_ids]]})

                po_lines.append(po_line);
            po_data['lines'] = po_lines
            # call purchase.oder to generate order
            ret_po = self.pool.get('purchase.order').new_po(cr, uid, [po_data], context=context)
            # set req status to in_purchase
            wf_service = netsvc.LocalService("workflow")
            wf_service.trg_validate(uid, 'pur.req', record_id, 'pur_req_purchase', cr)
            # the 'po_id','po_line_id' should be pushed in the purchase.order.make_po() method
            result_po_ids.append(po_data['new_po_id'])
        return result_po_ids

    def do_generate_view(self, cr, uid, ids, context=None):
        record_id = context and context.get('active_id', False) or False
        po_ids = self.do_generate(cr, uid, ids, context=context)
        return {
            'domain': "[('req_id', 'in', [" + str(record_id) + "])]",
            'name': _('Purchase Order'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'purchase.order',
            'type': 'ir.actions.act_window',
            'context': context,
        }
pr_generate_po_wizard()


class pr_generate_po_wizard_po(osv.osv_memory):
    _name = "pr.generate.po.wizard.po"
    _description = "PR Wizard Purchase Order"
    _columns = {
        'wizard_id': fields.many2one('pr.generate.po.wizard', 'PR Wizard'),
        'supplier_id': fields.many2one('res.partner', 'Supplier', readonly=True),
        'total_quantity': fields.float('Total Quantity', readonly=True),
        'line_ids': fields.one2many('pr.generate.po.wizard.po.line', 'order_id', string='Purchase Order Lines',
                                    ),
    }


pr_generate_po_wizard_po()


class pr_generate_po_wizard_po_line(osv.osv_memory):
    _name = "pr.generate.po.wizard.po.line"
    _description = "PR Wizard Purchase Order Line"
    _columns = {
        'order_id': fields.many2one('pr.generate.po.wizard.po', 'Purchase Order', readonly=True),
        'product_id': fields.many2one('product.product', 'Product', required=True),
        'quantity': fields.float('Quantity', digits_compute=dp.get_precision('Product Unit of Measure'),
                                 required=True),
        'mfg_ids': fields.many2many('sale.product', string="MFG IDs"),
        'req_reason': fields.char('Reason and use', size=64),
        'price': fields.float('Unit Price', digits_compute=dp.get_precision('Product Price')),
        'uom_id': fields.many2one('product.uom', 'Unit of Measure', required=True, ),
        'date_required': fields.date('Date Required', required=True),
        'req_line_id': fields.many2one('pur.req.line', 'Purchase Requisition'),
        'supplier_prod_id': fields.integer(string='Supplier Product ID', required=False),
        'supplier_prod_name': fields.char(string='Supplier Product Name', required=True),
        'supplier_prod_code': fields.char(string='Supplier Product Code', required=False),
        'supplier_delay': fields.integer(string='Supplier Lead Time', required=False),
    }

    def do_generate(self, cr, uid, ids, context=None):
        return True


pr_generate_po_wizard_po_line()
