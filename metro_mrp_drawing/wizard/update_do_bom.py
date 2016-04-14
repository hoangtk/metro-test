# -*- coding: utf-8 -*-
import time
from openerp.osv import fields, osv
from openerp.osv.orm import browse_record, browse_null
from openerp.tools.translate import _
import datetime
import openerp.tools as tools
from openerp.addons.metro import utils
from openerp.addons.metro_mrp_drawing.drawing_order import PART_TYPE_SELECTION
import xlrd
import StringIO

class update_do_bom(osv.osv_memory):
    _name = 'update.do.bom'
    _description = 'Update DO BOM'
    _columns = {
        'do_id': fields.many2one('drawing.order','Drawing Order',required=True),
        'bom_file_name': fields.char('BOM File Name', size=64),
        'bom_file': fields.function(utils.field_get_file, fnct_inv=utils.field_set_file, string="BOM File", type="binary", multi="_get_file",required=True),
    }
    def do_update(self, cr, uid, ids, context=None):
        update_do_bom = self.browse(cr, uid, ids, context)[0]
        #1. Check if can update this bom file
        department_obj = self.pool.get('hr.department')
        bom_obj = self.pool.get('mrp.bom')
        drawing_order_obj = self.pool.get('drawing.order')
        drawing_order_line_obj = self.pool.get('drawing.order.line')
        task_obj = self.pool.get('project.task')
        task_line_obj = self.pool.get('project.task.line')
        order = update_do_bom.do_id
        if order.state in ['draft','cancel']:
            raise osv.except_osv(_('Error!'), _('Drawing order is in draft or cancel state. Please edit it to update BOM File!.'))
        new_name = update_do_bom.bom_file_name.split('.')[0]
        error_logs = drawing_order_obj.check_bom_file_content(cr, uid, order.name, new_name,
                                                              update_do_bom.bom_file)
        if len(error_logs) > 0:
            raise osv.except_osv(_('Error!'),
                                 _('BOM File error, please check bom file!.'))
        old_bom_values = {}
        new_bom_values = {}
        modify_erp_nos = []
        for line in order.order_lines:
            old_bom_values[line.erp_no] = {
                'line_id': line.id,
                'item_no': line.item_no,
                'erp_no': line.erp_no,
                'part_number':  line.product_id.name,
                'product_id': line.product_id.id,
                'part_type': line.part_type,
                'work_steps': line.work_steps,
                'bom_qty': line.bom_qty,
            }
        inputStr = StringIO.StringIO()
        inputStr.write(update_do_bom.bom_file.decode('base64'))
        workbook = xlrd.open_workbook(file_contents=inputStr.getvalue())
        worksheet = workbook.sheet_by_index(0)
        row = 2
        while row < worksheet.nrows:
            bom_line = self.read_bom_line(worksheet=worksheet, row=row)
            if bom_line['part_name']:
                item_no = bom_line['item_no']
                erp_no = bom_line['erp_no']
                part_name = bom_line['part_name']
                bom_qty = int(bom_line['bom_qty'])
                part_type = bom_line['part_type']
                work_steps = bom_line['work_steps']
                new_bom_values[erp_no] = {
                        'item_no': item_no,
                        'erp_no': erp_no,
                        'part_number': part_name,
                        'part_type': part_type,
                        'work_steps': work_steps,
                        'bom_qty': bom_qty,
                        }
                #Check if this part exist in old bom
                if erp_no not in old_bom_values:
                    raise osv.except_osv(_("Error!"),_('You are not allow to add new part: %s to bom!') % (part_name,))
                old_part_values = old_bom_values[erp_no]
                if part_type != old_part_values['part_type'] or \
                    work_steps != old_part_values['work_steps']:
                    raise osv.except_osv(_("Error!"),_('Part type and work steps of part %s not match the old one') % (part_name,))
                if bom_qty < old_part_values['bom_qty']:
                    raise osv.except_osv(_("Error!"),_('You are not allow to decrease the quantity of part: %s') % (part_name,))
                elif bom_qty > old_part_values['bom_qty']:
                    modify_erp_nos.append(erp_no)
            row += 1
        for old_erp_no in old_bom_values:
            if old_erp_no not in new_bom_values:
                raise osv.except_osv(_("Error!"),_('Old part: %s not exists in new bom file') % (old_erp_no,))
        #2. Update this bom file to DO
        big_assembly_qty = 1
        big_assembly_bom_ids = bom_obj.search(cr, uid, [
                                                        ('bom_id','=',order.mo_id.bom_id.id),
                                                        ('product_id','=',order.product_id.id),
                                                        ])
        if len(big_assembly_bom_ids) > 0 :
            big_assembly_boms = bom_obj.browse(cr, uid, big_assembly_bom_ids)
            if order.mo_id.bom_id.product_qty > 0:
                big_assembly_qty = big_assembly_boms[0].product_qty /order.mo_id.bom_id.product_qty
        for modify_erp_no in modify_erp_nos:
            new_bom_qty = new_bom_values[modify_erp_no]['bom_qty']
            need_qty = bom_qty * big_assembly_qty
            steps = drawing_order_obj._split_work_steps(work_steps)
            vals = {'status': _('On Working')}
            for step in steps:
                vals.update({'%s_need_qty' % step : need_qty})
            vals.update({'%s_prepare_qty' % step[0]: need_qty})
            drawing_order_line_obj.write(cr, uid, [old_bom_values[modify_erp_no]['line_id']], vals)
            task_ids = task_obj.search(cr, uid, [('drawing_order_id','=',order.id),
                                                 ('dept_code','in',steps)])
            task_line_ids = task_line_obj.search(cr, uid, [('task_id','in',task_ids),
                                                           ('product_id','=',old_bom_values[modify_erp_no]['product_id'])])
            task_line_obj.write(cr, uid, task_line_ids, {
                'need_qty': need_qty,
            })
            #TODO: Check first steps
            first_step_task_ids = task_obj.search(cr, uid, [('drawing_order_id','=',order.id),
                                                 ('dept_code','=',steps[0])])
            first_step_task_line_ids = task_line_obj.search(cr, uid, [('task_id','in',first_step_task_ids),
                                                           ('product_id','=',old_bom_values[modify_erp_no]['product_id'])])
            task_line_obj.write(cr, uid, first_step_task_line_ids, {
                'prepare_qty': need_qty,
            })
            task_obj.update_task_qty(cr, uid, task_ids,open_task=True)
        drawing_order_obj.write(cr, uid, [order.id],{
            'bom_file': update_do_bom.bom_file
        })
        return True
update_do_bom()