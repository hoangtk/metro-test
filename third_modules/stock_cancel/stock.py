# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (c) 2012 Andrea Cometa All Rights Reserved.
#                       www.andreacometa.it
#                       openerp@andreacometa.it
#    Copyright (C) 2013 Agile Business Group sagl (<http://www.agilebg.com>)
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
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
# W gli spaghetti code!!!
##############################################################################


from osv import osv, fields
import netsvc
from tools.translate import _

class stock_picking(osv.osv):
    _inherit = 'stock.picking'
    
    def has_valuation_moves(self, cr, uid, picking, context):
        move_obj = self.pool.get('account.move')
        move_ids = move_obj.search(cr, uid, [('ref','=', picking.name),])
        unlink_ids = []
        for move in move_obj.browse(cr, uid, move_ids, context=context):
            if move.state == 'draft':
                unlink_ids.append(move.id)
                move_ids.remove(move.id)
        if len(move_ids) > 0:
            return True
        elif len(unlink_ids) > 0:
            move_obj.unlink(cr, uid, unlink_ids, context=context)
        return False
            
    def has_invoices(self, cr, uid, picking, context):
        source = (picking.name or '') + (picking.origin and (':' + picking.origin) or ''),
        invoice_obj = self.pool.get('account.invoice')
        invoice_ids = invoice_obj.search(cr, uid, [('origin','=', source),])
        unlink_ids = []
        for invoice in invoice_obj.browse(cr, uid, invoice_ids, context=context):
            if invoice.state in ('draft','cancel'):
                unlink_ids.append(invoice.id)
                invoice_ids.remove(invoice.id)
        if len(invoice_ids) > 0:
            return True
        elif len(unlink_ids) > 0:
            invoice_obj.unlink(cr, uid, unlink_ids, context=context)
        return False

    def has_stock_matching(self, cr, uid, picking, context):
        match_obj = self.pool.get('stock.move.matching')
        del_out_ids = []
        for move in picking.move_lines:
            #this is a stocking in order, and have related stock out picking
            in_ids = match_obj.search(cr, uid, [('move_in_id','=',move.id)])
            if len(in_ids) > 0:
                return True
            #this is a stock out order, then need delete the matching ids
            out_ids = match_obj.search(cr, uid, [('move_out_id','=',move.id)])
            if len(out_ids) > 0:
                del_out_ids.extend(out_ids)
        if len(del_out_ids) > 0:
            match_obj.unlink(cr, uid, del_out_ids, context=context)
            
        return False
    
    def action_revert_done(self, cr, uid, ids, context=None):
        if not len(ids):
            return False
        for picking in self.browse(cr, uid, ids, context):
            if self.has_invoices(cr, uid, picking, context):
                raise osv.except_osv(_('Error'),
                    _('Picking %s has invoices. Remove them first')
                    % (picking.name,))
            if self.has_valuation_moves(cr, uid, picking,context):
                raise osv.except_osv(_('Error'),
                    _('Picking %s has valuation moves. Remove them first')
                    % (picking.name,))
            if self.has_stock_matching(cr, uid, picking,context):
                raise osv.except_osv(_('Error'),
                    _('Picking %s has stocking out moves generated, can not reopen it.')
                    % (picking.name,))                
            for line in picking.move_lines:
                line.write({'state': 'draft'})                            
            self.write(cr, uid, [picking.id], {'state': 'draft'})
            if picking.invoice_state == 'invoiced':
                self.write(cr, uid, [picking.id], {'invoice_state': '2binvoiced'})
            wf_service = netsvc.LocalService("workflow")
            # Deleting the existing instance of workflow
            wf_service.trg_delete(uid, 'stock.picking', picking.id, cr)
            wf_service.trg_create(uid, 'stock.picking', picking.id, cr)
#        for (id,name) in self.name_get(cr, uid, ids):
#            message = _("The stock picking '%s' has been set in draft state.") %(name,)
#            self.log(cr, uid, id, message)
            #johnw,  09/26/2014, set po's shipped status to false
            if picking.purchase_id and picking.purchase_id.shipped:
                self.pool.get('purchase.order').write(cr, uid, [picking.purchase_id.id], {'shipped':False}, context=context)
                
        return True

class stock_picking_out(osv.osv):
    _inherit = 'stock.picking.out'
    def action_revert_done(self, cr, uid, ids, context=None):
        #override in order to redirect to stock.picking object
        return self.pool.get('stock.picking').action_revert_done(cr, uid, ids, context=context)

class stock_picking_in(osv.osv):
    _inherit = 'stock.picking.in'
    def action_revert_done(self, cr, uid, ids, context=None):
        #override in order to redirect to stock.picking object
        return self.pool.get('stock.picking').action_revert_done(cr, uid, ids, context=context)
