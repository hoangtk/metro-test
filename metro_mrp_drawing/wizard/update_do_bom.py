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
        drawing_order = update_do_bom.do_id
        if drawing_order.state in ['draft','cancel']:
            raise osv.except_osv(_('Error!'), _('Drawing order is in draft or cancel state. Please edit it to update BOM File!.'))
            return False
        old_bom_values = {}
        old_bigsubassembly_name = drawing_order.name
        new_bom_values = {}
        new_bigsubassembly_name = ''
        modify_parts = []
        if update_do_bom.bom_file_name != drawing_order.bom_file_name:
            raise osv.except_osv(_('Error!'), _('New BOM file name not match old BOM file name!.'))
            return False
        for line in drawing_order.order_lines:
            old_bom_values[line.product_id.name] = {
                'line_id': line.id,
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
        new_bigsubassembly_name = worksheet.cell(0,0).value
        if new_bigsubassembly_name == xlrd.empty_cell.value or new_bigsubassembly_name != old_bigsubassembly_name:
            raise osv.except_osv(_('Error!'), _('Assembly name in bom file not match with current drawing order!.'))
            return False
        else:
            row = 2
            while row < worksheet.nrows:
                #Read part name
                part_name = worksheet.cell(row,1).value.strip('\t').strip().replace('\n', ' ').replace('\r', '')
                if part_name != '':
                    bom_qty = worksheet.cell(row,8).value
                    try:
                        bom_qty = int(bom_qty)
                    except ValueError:
                        raise osv.except_osv(_("Error!"),_('Bom Qty of part %s is not a number(%s). Please check the bom quantity in bom file') % (part_name,bom_qty))
                        return False
                    part_type = worksheet.cell(row,7).value
                    part_types = [type[0] for type in PART_TYPE_SELECTION ]
                    if not part_type in part_types:
                        raise osv.except_osv(_("Error!"),_('Part type of part %s is not valid. Please check the part type in bom file') % (part_name,))
                        return False
                    work_steps = worksheet.cell(row,6).value.strip()
                    steps = drawing_order_obj._split_work_steps(work_steps)
                    department_ids = department_obj.search(cr, uid, [
                                                                     ('code','in',steps),
                                                                     ])
                    #Check if work steps are correct ?
                    if len(department_ids) != len(steps) or len(steps) == 0:
                        raise osv.except_osv(_("Error!"),_('Work steps of part %s are not right. Please check the work steps in bom file') % (part_name,))
                        return False
                    #Update need qty, bom qty, worksteps of this product
                    new_bom_values[part_name] = {
                            'part_number': part_name,
                            'part_type': part_type,
                            'work_steps': work_steps,
                            'bom_qty': bom_qty,
                            }
                    #Check if this part exist in old bom
                    if part_name not in old_bom_values:
                        raise osv.except_osv(_("Error!"),_('You are not allow to add new part: %s to bom!') % (part_name,))
                        return False
                    old_part_values = old_bom_values[part_name]
                    if part_type != old_part_values['part_type'] or \
                        work_steps != old_part_values['work_steps']:
                        raise osv.except_osv(_("Error!"),_('Part type and work steps of part %s not match the old one') % (part_name,))
                        return False
                    if bom_qty < old_part_values['bom_qty']:
                        raise osv.except_osv(_("Error!"),_('You are not allow to decrease the quantity of part: %s') % (part_name,))
                        return False
                    elif bom_qty > old_part_values['bom_qty']:
                        modify_parts.append(part_name)
                row += 1
            for old_part_name in old_bom_values:
                if old_part_name not in new_bom_values:
                    raise osv.except_osv(_("Error!"),_('Old part: %s not exists in new bom file') % (old_part_name,))
                    return False
        #2. Update this bom file to DO
        big_assembly_qty = 1
        big_assembly_bom_ids = bom_obj.search(cr, uid, [
                                                        ('bom_id','=',drawing_order.mo_id.bom_id.id),
                                                        ('product_id','=',drawing_order.product_id.id),
                                                        ])
        if len(big_assembly_bom_ids) > 0 :
            big_assembly_boms = bom_obj.browse(cr, uid, big_assembly_bom_ids)
            if drawing_order.mo_id.bom_id.product_qty > 0:
                big_assembly_qty = big_assembly_boms[0].product_qty /drawing_order.mo_id.bom_id.product_qty
        for modify_part in modify_parts:
            new_bom_qty = new_bom_values[modify_part]['bom_qty']
            need_qty = bom_qty * big_assembly_qty
            steps = drawing_order_obj._split_work_steps(work_steps)
            vals = {'status': _('On Working')}
            for step in steps:
                if step == 'P':
                    vals.update({'P_need_qty': need_qty})
                if step == 'Fc':
                    vals.update({'Fc_need_qty': need_qty})
                if step == 'B':
                    vals.update({'B_need_qty': need_qty})
                if step == 'Ma':
                    vals.update({'Ma_need_qty': need_qty})
                if step == 'D':
                    vals.update({'D_need_qty': need_qty})
                if step == 'Mi':
                    vals.update({'Mi_need_qty': need_qty})
                if step == 'W':
                    vals.update({'W_need_qty': need_qty})
                if step == 'A':
                    vals.update({'A_need_qty': need_qty})
                if step == 'Ct':
                    vals.update({'Ct_need_qty': need_qty})
                if step == 'Bt':
                    vals.update({'Bt_need_qty': need_qty})
                if step == 'Ps':
                    vals.update({'Ps_need_qty': need_qty})
                if step == 'G':
                    vals.update({'G_need_qty': need_qty})
                first_step = steps[0]
                if 'P' == first_step:
                    vals.update({'P_prepare_qty': need_qty})
                if 'Fc' == first_step:
                    vals.update({'Fc_prepare_qty': need_qty})
                if 'B' == first_step:
                    vals.update({'B_prepare_qty': need_qty})
                if 'Ma' == first_step:
                    vals.update({'Ma_prepare_qty': need_qty})
                if 'D' == first_step:
                    vals.update({'D_prepare_qty': need_qty})
                if 'Mi' == first_step:
                    vals.update({'Mi_prepare_qty': need_qty})
                if 'W' == first_step:
                    vals.update({'W_prepare_qty': need_qty})
                if 'A' == first_step:
                    vals.update({'A_prepare_qty': need_qty})
                if 'Ct' == first_step:
                    vals.update({'Ct_prepare_qty': need_qty})
                if 'Bt' == first_step:
                    vals.update({'Bt_prepare_qty': need_qty})
                if 'Ps' == first_step:
                    vals.update({'Ps_prepare_qty': need_qty})
                if 'G' == first_step:
                    vals.update({'G_prepare_qty': need_qty})
            drawing_order_line_obj.write(cr, uid, [old_bom_values[modify_part]['line_id']], vals)
            task_ids = task_obj.search(cr, uid, [('drawing_order_id','=',drawing_order.id),
                                                 ('dept_code','in',steps)])
            task_line_ids = task_line_obj.search(cr, uid, [('task_id','in',task_ids),
                                                           ('product_id','=',old_bom_values[modify_part]['product_id'])])
            task_line_obj.write(cr, uid, task_line_ids, {
                'need_qty': need_qty,
            })
            #TODO: Check first steps
            first_step_task_ids = task_obj.search(cr, uid, [('drawing_order_id','=',drawing_order.id),
                                                 ('dept_code','=',steps[0])])
            first_step_task_line_ids = task_line_obj.search(cr, uid, [('task_id','in',first_step_task_ids),
                                                           ('product_id','=',old_bom_values[modify_part]['product_id'])])
            task_line_obj.write(cr, uid, first_step_task_line_ids, {
                'prepare_qty': need_qty,
            })
            task_obj.update_task_qty(cr, uid, task_ids,open_task=True)
        drawing_order_obj.write(cr, uid, [drawing_order.id],{
            'bom_file': update_do_bom.bom_file
        })
        return True
update_do_bom()