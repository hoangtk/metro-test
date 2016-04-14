# -*- encoding: utf-8 -*-
from osv import fields, osv
from openerp.tools.translate import _
from openerp import netsvc
import time
from datetime import datetime
from openerp.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT,DEFAULT_SERVER_DATE_FORMAT
from openerp.report.pyPdf import PdfFileWriter, PdfFileReader
from reportlab.pdfgen import canvas
from openerp.addons.metro import utils
import zipfile
import random
import os
from openerp import SUPERUSER_ID
import xlrd
from xlrd import XLRDError
import StringIO
from decimal import *
try:
    import json
except ImportError:
    import simplejson as json
import tempfile
from lxml import etree

PART_TYPE_SELECTION = [('PRODUCED', 'PRODUCED'),
                       ('PURCH-M', 'PURCH-M'),
                       ('PURCH-MC', 'PURCH-MC'),
                       ('PURCH-MS', 'PURCH-MS'),
                       ('PURCH-ML', 'PURCH-ML'),
                       ('PURCH-S', 'PURCH-S'),
                       ('PURCH-OEM', 'PURCH-OEM')]
WORK_STEP_LIST = ['P', 'Fc', 'B', 'Ma', 'D', 'Mi', 'W', 'A', 'Ct', 'Bt', 'Ps', 'G', 'K']

class missing_erpno(osv.osv):
    _name = "missing.erpno"
    _description = "Missing ERP No"
    _columns = {
        'order_id': fields.many2one('drawing.order', string='Drawing Order', readonly=True),
        'lines': fields.one2many('missing.erp.line','missing_id', string='Missing Lines', ondelete="cascade"),
    }
missing_erpno()

class missing_erpno_line(osv.osv):
    _name = "missing.erpno.line"
    _description = "Missing ERP Lines"
    _columns = {
        'missing_id': fields.many2one('missing.order','Missing ERP No'),
        'product_id': fields.many2one('product.product', string='Product'),
        'item_no': fields.char('Item No', readonly=True),
        'name': fields.char('Part Number', size=128, readonly=True),
        'description': fields.char('Description', size=128, readonly=True),
    }

class drawing_order_history(osv.osv):
    _name = "drawing.order.history"
    _description = "Drawing Order History"
    _columns = {
        'date': fields.datetime('Modified Date', readonly=True),
        'drawing_order_id': fields.many2one('drawing.order', 'Drawing Order', readonly=True),
        'user_id': fields.many2one('res.users', 'User', readonly=True),
        'content': fields.char('Content', readonly=True),
        'vals': fields.char('Update Values', readonly=True, size=256),
    }


drawing_order_history()


class drawing_order(osv.osv):
    _name = "drawing.order"
    _inherit = ['mail.thread']
    _description = "Drawing Order"
    _order = 'id desc'

    def _get_product_ids_from_mo(self, cr, uid, mo):
        product_ids = []
        if mo.bom_id:
            for bom_line in mo.bom_id.bom_lines:
                product_ids.append(bom_line.product_id.id)
        return product_ids

    def _get_product_ids(self, cr, uid, order):
        product_ids = []
        if order.mo_id :
            product_ids = self._get_product_ids_from_mo(cr, uid, order.mo_id)
        return product_ids

    def _get_mo_bigsubassembly(self, cr, uid, ids, name, args, context=None):
        result = {}
        for order in self.browse(cr, uid, ids):
            result[order.id] = self._get_product_ids(cr, uid, order)
        return result

    def _is_bom_error(self, cr, uid, ids, name, args, context=None):
        result = {}
        for order in self.browse(cr, uid, ids):
            result[order.id] = ''
            if order.bom_log:
                result[order.id] = _('Please check the Bom Log!')
        return result

    _columns = {
        'name': fields.char('Name', size=64, readonly=True,
                            states={'draft': [('readonly', False)], 'rejected': [('readonly', False)]}),
        'note': fields.text('Description', required=False),
        # +++ HoangTK - 11/17/2015: Change sale_product_ids to related field of mo_id
        # 'sale_product_ids': fields.many2many('sale.product','drawing_order_id_rel','drawing_order_id','id_id',
        #                                     string="MFG IDs",readonly=True, states={'draft':[('readonly',False)],'rejected':[('readonly',False)]}),
        'sale_product_ids': fields.related('mo_id', 'mfg_ids', type="many2many", relation="sale.product",
                                           string="MFG IDs", readonly=True),
        # --- HoangTK - 11/17/2015
        'order_lines': fields.one2many('drawing.order.line', 'order_id', 'Drawing Order Lines', readonly=True,
                                       states={'draft': [('readonly', False)], 'rejected': [('readonly', False)]}),
        'state': fields.selection(
            [('draft', 'Draft'), ('ready', 'Ready'), ('confirmed', 'Confirmed'), ('approved', 'Approved'),
             ('rejected', 'Rejected'), ('cancel', 'Cancelled')],
            'Status', track_visibility='onchange', required=True),
        'reject_message': fields.text('Rejection Message', track_visibility='onchange'),
        'create_uid': fields.many2one('res.users', 'Creator', readonly=True),
        'create_date': fields.datetime('Creation Date', readonly=True),
        #        'date_finished': fields.datetime('Finished Date', readonly=True),
        'company_id': fields.many2one('res.company', 'Company', readonly=True),
        # +++ HoangTK 11/17/2015: Replace product_id below
        # 'product_id': fields.related('order_lines','product_id', type='many2one', relation='product.product', string='Product'),
        # --- HoangTK 11/17/2015
        'main_part_id': fields.many2one('product.product', 'Main Product', readonly=True,
                                        states={'draft': [('readonly', False)], 'rejected': [('readonly', False)]}),
        'bom_file_name': fields.char('BOM File Name', size=64),
        'bom_file': fields.function(utils.field_get_file, fnct_inv=utils.field_set_file, string="BOM File",
                                    type="binary", multi="_get_file", filters='*.xls,*.xlsx'),
        # +++ HoangTK - 11/16/2015: Attach drawing order to MO
        'mo_id': fields.many2one('mrp.production', 'Manufacturer Order'),
        'product_id': fields.many2one('product.product', 'Big Sub Assembly', required=True),
        'prepare_qty': fields.integer('Prepare Qty', readonly=True),
        'done_qty': fields.integer('Done Qty', readonly=True),
        'need_qty': fields.integer('Need Qty', readonly=True),
        'history_ids': fields.one2many('drawing.order.history', 'drawing_order_id', 'History', readonly=True),
        'bom_log': fields.text('BOM Log',readonly=True),
        'bom_error': fields.function(_is_bom_error,string='Bom error',type="char",size=100,method=True),
        'mo_bigsubassembly_ids': fields.function(_get_mo_bigsubassembly,string='MO Big Subassembly',type="many2many",relation="product.product"),
        'confirm_date': fields.date(string='Confirm Date',readonly=True),
        # --- HoangTK - 11/16/2015
    }
    _defaults = {
        'company_id': lambda self, cr, uid, c: self.pool.get('res.company')._company_default_get(cr, uid,
                                                                                                 'drawing.order',
                                                                                                 context=c),
        'state': 'draft',
    }

    def _set_state(self, cr, uid, ids, state, context=None):
        self.write(cr, uid, ids, {'state': state}, context=context)
        line_ids = []
        for order in self.browse(cr, uid, ids, context=context):
            for line in order.order_lines:
                if not line.state == 'done':
                    line_ids.append(line.id)
        self.pool.get('drawing.order.line').write(cr, uid, line_ids, {'state': state})

    @staticmethod
    def _check_done_lines(cr, uid, ids, context=None):
        #        for wo in self.browse(cr,uid,ids,context=context):
        #            for line in wo.wo_cnc_lines:
        #                if line.state == 'done':
        #                    raise osv.except_osv(_('Invalid Action!'), _('Action was blocked, there are done work order lines!'))
        return True

    def _email_notify(self, cr, uid, ids, action_name, group_params, context=None):
        for order in self.browse(cr, uid, ids, context=context):
            for group_param in group_params:
                email_group_id = self.pool.get('ir.config_parameter').get_param(cr, uid, group_param, context=context)
                if email_group_id:
                    email_subject = 'Drawing reminder: %s %s' % (order.name, action_name)
                    mfg_id_names = ','.join([mfg_id.name for mfg_id in order.sale_product_ids])
                    # [(id1,name1),(id2,name2),...(idn,namen)]
                    main_part_name = ''
                    if order.main_part_id:
                        main_part_name = \
                        self.pool.get('product.product').name_get(cr, uid, [order.main_part_id.id], context=context)[0][
                            1]
                    email_body = '%s %s %s, MFG IDs:%s' % (order.name, main_part_name, action_name, mfg_id_names)
                    email_from = self.pool.get("res.users").read(cr, uid, uid, ['email'], context=context)['email']
                    utils.email_send_group(cr, uid, email_from, None, email_subject, email_body, email_group_id,
                                           context=context)

    def action_ready(self, cr, uid, ids, context=None):
        # +++ HoangTK - 12/14/2015 : Check if drawing order ready
        if not self._is_ready(cr, uid, ids, context=context):
            return False
        # +++ HoangTK - 12/14/2015 : Check if drawing order ready
        # set the ready state
        self._set_state(cr, uid, ids, 'ready', context)
        # send email to the user group that can confirm
        self._email_notify(cr, uid, ids, 'need your confirmation', ['mrp_cnc_wo_group_confirm'], context)
        return True

    # +++ HoangTK - 12/14/2015 : Add check drawing order lines into a separate function
    def _is_ready(self, cr, uid, ids, context=None):
        for order in self.browse(cr, uid, ids, context=context):
            # must have cnc lines
            if not order.order_lines:
                raise osv.except_osv(_('Error!'), _('Please add lines for order [%s]%s') % (order.id, order.name))
            for line in order.order_lines:
                if line.part_type == 'PRODUCED' and not line.drawing_file_name:
                    raise osv.except_osv(_('Error!'), _('All produced parts must have drawing PDFs!'))
        return True

    # --- HoangTK - 12/14/2015
    def action_confirm(self, cr, uid, ids, context=None):
        # +++ HoangTK - 12/14/2015 : Move to action_ready
        #         for order in self.browse(cr, uid, ids, context=context):
        #             #must have cnc lines
        #             if not order.order_lines:
        #                 raise osv.except_osv(_('Error!'), _('Please add lines for order [%s]%s')%(order.id, order.name))
        #             for line in order.order_lines:
        #                 if not line.drawing_file_name:
        #                     raise osv.except_osv(_('Invalid Action!'), _('The line''s "Drawing PDF" file is required!'))
        # --- HoangTK - 12/14/2015 : Move to action_ready
        if not self._is_ready(cr, uid, ids, context=context):
            return False
        self._set_state(cr, uid, ids, 'confirmed', context)
        self.write(cr, uid, ids, {
            'confirm_date': datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT)
        })
        # send email to the user group that can approve
        self._email_notify(cr, uid, ids, 'need your approval', ['mrp_cnc_wo_group_approve'], context)
        return True

    def action_cancel(self, cr, uid, ids, context=None):
        self._check_done_lines(cr, uid, ids, context)
        # set the cancel state
        self._set_state(cr, uid, ids, 'cancel', context)
        return True

    def action_draft(self, cr, uid, ids, context=None):
        # set the cancel state
        self._set_state(cr, uid, ids, 'draft', context)
        return True

    def action_approve(self, cr, uid, ids, context=None):
        if not self._is_ready(cr, uid, ids, context=context):
            return False
        self._set_state(cr, uid, ids, 'approved', context)
        # send email to the user group that can CNC done
        self._email_notify(cr, uid, ids, 'was approved', ['mrp_cnc_wo_group_cnc_mgr'], context)
        return True

    def action_reject_callback(self, cr, uid, ids, message, context=None):
        # set the draft state
        self._set_state(cr, uid, ids, 'rejected', context)
        self.write(cr, uid, ids, {'reject_message': message})
        # send email to the user for the rejection message
        email_from = self.pool.get("res.users").read(cr, uid, uid, ['email'], context=context)['email']
        for order in self.browse(cr, uid, ids, context=context):
            if order.create_uid.email:
                email_content = 'CNC reminder: %s was rejected' % order.name
                utils.email_send_group(cr, uid, email_from, order.create_uid.email, email_content, email_content,
                                       context=context)
        return True

    def action_reject(self, cr, uid, ids, context=None):
        ctx = dict(context)
        ctx.update({'confirm_title': 'Confirm rejection message',
                    'src_model': 'drawing.order',
                    "model_callback": 'action_reject_callback',})
        return self.pool.get('confirm.message').open(cr, uid, ids, ctx)

    def unlink(self, cr, uid, ids, context=None):
        orders = self.read(cr, uid, ids, ['state'], context=context)
        for s in orders:
            if s['state'] not in ['draft', 'cancel']:
                raise osv.except_osv(_('Invalid Action!'), _('Only the orders in draft or cancel state can be delete.'))
        self._check_done_lines(cr, uid, ids, context)
        return super(drawing_order, self).unlink(cr, uid, ids, context=context)

    def copy(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}
        old_data = self.read(cr, uid, id, ['name'], context=context)
        default.update({
            'name': '%s (copy)' % old_data['name'],
            'mfg_task_id': None,
            'sale_product_ids': None,
            'reject_message': None,
        })
        return super(drawing_order, self).copy(cr, uid, id, default, context)
        # +++ HoangTK - 11/17/2015: Add update_parts function

    @staticmethod
    def split_work_steps(work_steps):
        steps = []
        if work_steps:
            steps = work_steps.split(' ')
        return steps

    def generate_pr(self, cr, uid, ids, context):
        mod_obj = self.pool.get('ir.model.data')
        res = mod_obj.get_object_reference(cr, uid, 'metro_mrp_drawing', 'view_generate_pr_wizard')
        res_id = res and res[1] or False
        return {
            'name': 'Purchase Requisition Generator',
            'res_model': 'generate.pr.wizard',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': [res_id],
            'context': {'drawing_order_ids': ids},
            'target': 'new'
        }

    def generate_tasks(self, cr, uid, ids, context):
        workcenter_line_obj = self.pool.get('mrp.production.workcenter.line')
        production_obj = self.pool.get('mrp.production')
        project_task_obj = self.pool.get('project.task')
        project_task_line_obj = self.pool.get('project.task.line')
        dept_obj = self.pool.get('hr.department')
        drawing_order_obj = self.pool.get('drawing.order')
        drawing_order_line_obj = self.pool.get('drawing.order.line')
        project_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'metro_project', 'project_mfg')[1]
        for order in self.browse(cr, uid, ids):
            if order.state in ['draft', 'rejected', 'cancel']:
                raise osv.except_osv(_('Error!'),
                                     _('Can not generate tasks for draft, cancel or rejected drawing orders!'))
            # Check if work order exists ? if not create it
            product = order.product_id
            mo = order.mo_id
            wo_line_ids = workcenter_line_obj.search(cr, uid, [
                ('production_id', '=', mo.id),
                ('big_subassembly_id', '=', product.id)
            ])
            if not wo_line_ids:
                production_obj.action_compute_an_assembly(cr, uid, [mo.id], assembly_id=product.id)
            wo_line_ids = workcenter_line_obj.search(cr, uid, [
                ('production_id', '=', mo.id),
                ('big_subassembly_id', '=', product.id)
            ])
            if not wo_line_ids:
                raise osv.except_osv(_('Error!'), _('Can not create work order for assembly %s !') % (product.name,))
            if len(wo_line_ids) != 1:
                raise osv.except_osv(_('Error!'),
                                     _('There are more than 2 work orders for assembly %s !') % (product.name,))
            wo = workcenter_line_obj.browse(cr, uid, wo_line_ids)[0]
            # if wo.state != 'draft':
            #    raise osv.except_osv(_('Error!'), _('Can not generate tasks for work order not in draft state !'))
            # Remove all current tasks
            old_task_ids = project_task_obj.search(cr, uid, [('workorder_id', '=', wo.id)])
            project_task_obj.unlink(cr, uid, old_task_ids)
            # Create all new tasks
            all_drawing_steps = []
            all_steps = {}
            for order_line in order.order_lines:
                steps = drawing_order_obj.split_work_steps(order_line.work_steps)
                for step in steps:
                    if not step in all_steps:
                        all_drawing_steps.append(step)
                        all_steps.update({step: True})
            for step in all_drawing_steps:
                dept_ids = dept_obj.search(cr, uid, [
                    ('code', '=', step)
                ])
                if dept_ids:
                    dept = dept_obj.browse(cr, uid, dept_ids[0])
                    task_vals = {
                        'name': dept.name,
                        'workorder_id': wo.id,
                        'user_id': uid,
                        'dept_id': dept.id,
                        'dept_mgr_id': dept.manager_id.id,
                        'drawing_order_id': order.id,
                        'project_id': project_id,
                    }
                    project_task_obj.create(cr, uid, task_vals)
                    # Add product and qty to task
            wo = workcenter_line_obj.browse(cr, uid, wo_line_ids)[0]
            for task_id in wo.task_ids:
                prepare_qty = 0
                need_qty = 0
                sequence = 1
                drawing_order_line_ids = []
                for order_line in task_id.drawing_order_lines:
                    drawing_order_line_ids.append(order_line.id)
                drawing_order_line_ids = drawing_order_line_obj.search(cr, uid, [
                    ('id', 'in', drawing_order_line_ids)
                ], order='item_no asc')
                for order_line in drawing_order_line_obj.browse(cr, uid, drawing_order_line_ids):
                    steps = drawing_order_obj.split_work_steps(order_line.work_steps)
                    if task_id.dept_code not in steps:
                        continue
                    task_line_vals = {
                        'task_id': task_id.id,
                        'order_line_id': order_line.id,
                        'product_id': order_line.product_id.id,
                        'next_step': '',
                        'sequence': sequence,
                        'item_no': order_line.item_no,
                        'prepare_qty': getattr(order_line, "%s_prepare_qty" % task_id.dept_code, 0),
                        'done_qty': 0,
                        'need_qty': getattr(order_line, "%s_need_qty" % task_id.dept_code, 0),
                    }
                    sequence = sequence + 1
                    prepare_qty += getattr(order_line, "%s_prepare_qty" % task_id.dept_code, 0)
                    need_qty += getattr(order_line, "%s_need_qty" % task_id.dept_code, 0)
                    done_qty_vals = {}
                    for work_step in WORK_STEP_LIST:
                        done_qty_vals.update({
                            '%s_done_qty' % work_step: 0,
                        })
                    drawing_order_line_obj.write(cr, uid, [order_line.id], done_qty_vals)

                    next_step = ""
                    if task_id.dept_code != order_line.last_step:
                        for index, step in enumerate(steps):
                            if step == task_id.dept_code:
                                next_step = steps[index + 1]
                                break
                    if task_line_vals["need_qty"] == 0 and next_step == "":
                        next_step = order_line.work_steps
                    task_line_vals.update({
                        'next_step': next_step,
                    })
                    project_task_line_obj.create(cr, uid, task_line_vals)
                # project_task_obj._update_task_line_sequence(cr, uid, [task_id.id])
                project_task_obj.write(cr, uid, [task_id.id], {
                    'prepare_qty': prepare_qty,
                    'need_qty': need_qty,
                })
            if wo.state == 'startworking':
                workcenter_line_obj.action_start_working(cr, uid, [wo.id])
        return True

    @staticmethod
    def get_string_from_xls_cell(cell_value):
        value = False
        if cell_value == xlrd.empty_cell.value:
            return value
        value = '%s' % cell_value
        value = value.strip('\t').strip().replace('\n', ' ').replace('\r', '')
        return value
    def read_bom_line(self, worksheet, row):
        return {
        'item_no' : self.get_string_from_xls_cell(worksheet.cell(row, 0).value),
        'part_name' : self.get_string_from_xls_cell(worksheet.cell(row, 1).value),
        'description': self.get_string_from_xls_cell(worksheet.cell(row, 2).value),
        'erp_no' : self.get_string_from_xls_cell(worksheet.cell(row, 3).value),
        'standard': self.get_string_from_xls_cell(worksheet.cell(row, 4).value),
        'material': self.get_string_from_xls_cell(worksheet.cell(row, 5).value),
        'thickness': self.get_string_from_xls_cell(worksheet.cell(row, 6).value),
        'work_steps': self.get_string_from_xls_cell(worksheet.cell(row, 7).value),
        'part_type': self.get_string_from_xls_cell(worksheet.cell(row, 8).value),
        'bom_qty': worksheet.cell(row, 9).value,
        }
    def check_bom_file_content(self, cr, uid, order_name, bom_file_name, bom_content, old_bom_content=False):
        logs = []
        department_obj = self.pool.get('hr.department')
        product_obj = self.pool.get('product.product')
        # Rule 1: Check if valid XLS file
        inputStr = StringIO.StringIO()
        inputStr.write(bom_content.decode('base64'))
        workbook = False
        try:
            workbook = xlrd.open_workbook(file_contents=inputStr.getvalue())
        except XLRDError:
            logs.append(_('Invalid file type'))
        if workbook:
            worksheet = workbook.sheet_by_index(0)
            # Rule 2: File name, A1 cell in BOM File = Order name
            a1_cell = self.get_string_from_xls_cell(worksheet.cell(0, 0).value)
            if bom_file_name != order_name or a1_cell != order_name:
                logs.append(_('Bom file name (%s) and A1 cell (%s) not match drawing order name (%s)' % (
                bom_file_name, a1_cell, order_name)))
            row = 2
            while row < worksheet.nrows:
                row_logs = []
                bom_line = self.read_bom_line(worksheet=worksheet, row=row)
                if bom_line['part_name']:
                    # Rule 3: Check missing erp_no and exists in database
                    if not bom_line['erp_no']:
                        row_logs.append('ERP # is missing')
                    else:
                        product_ids = product_obj.search(cr, uid, [
                            ('default_code', '=', bom_line['erp_no'])
                        ])
                        if not product_ids:
                            row_logs.append('ERP # (%s) is invalid' % bom_line['erp_no'])
                    try:
                        bom_qty = int(bom_line['bom_qty'])

                    # Rule 4: Check bom quantity
                    except ValueError:
                        row_logs.append('Bom quantity (%s) is invalid' % bom_line['bom_qty'])
                    # Rule 5: Check part type
                    part_types = [type[0] for type in PART_TYPE_SELECTION]
                    if not bom_line['part_type'] in part_types:
                        row_logs.append('Part type (%s) must in %s' % (bom_line['part_type'], PART_TYPE_SELECTION))
                    # Rule 6: Check work steps
                    steps = self.split_work_steps(bom_line['work_steps'])
                    department_ids = department_obj.search(cr, uid, [
                        ('code', 'in', steps),
                        ('code', 'in', WORK_STEP_LIST)
                    ])
                    if len(department_ids) != len(steps) or len(steps) == 0:
                        row_logs.append(
                            'Work steps (%s) must in %s and not empty' % (bom_line['work_steps'], WORK_STEP_LIST))
                    if len(row_logs) > 0:
                        logs.append('-------------%s-%s-------------' % (bom_line['item_no'], bom_line['part_name']))
                        logs.extend(row_logs)
        return logs
    def check_bom_file(self, cr, uid, ids):
        error_logs = {}
        for order in self.browse(cr, uid, ids):
            logs = []
            if order.bom_file:
                bom_file_name = order.bom_file_name.split('.')[0]
                logs = self.check_bom_file_content(cr, uid, order.name, bom_file_name, order.bom_file)
                if len(logs)> 0:
                    error_logs.update({order.id : logs})
            if len(logs) > 0:
                super(drawing_order,self).write(cr, uid, [order.id],{'bom_log': '\n'.join(logs)})
            else:
                super(drawing_order, self).write(cr, uid, [order.id], {'bom_log': ''})
        return error_logs

    def update_parts(self, cr, uid, ids, context=None):
        """ Read the bom file and add/update part and quantity to drawing order line.
        """
        result = True
        error_logs = self.check_bom_file(cr, uid, ids)
        if len(error_logs) > 0:
            raise osv.except_osv(_('Error!'),
                                 _('Bom file errors, please check the log tab!.'))
        product_obj = self.pool.get('product.product')
        drawing_order_line_obj = self.pool.get('drawing.order.line')
        bom_obj = self.pool.get('mrp.bom')
        department_obj = self.pool.get('hr.department')
        for order in self.browse(cr, uid, ids):
            if order.bom_file:
                mo_qty = order.mo_id.product_qty
                big_assembly_qty = 1
                big_assembly_bom_ids = bom_obj.search(cr, uid, [
                    ('bom_id', '=', order.mo_id.bom_id.id),
                    ('product_id', '=', order.product_id.id),
                ])
                if len(big_assembly_bom_ids) > 0:
                    big_assembly_boms = bom_obj.browse(cr, uid, big_assembly_bom_ids)
                    if order.mo_id.bom_id.product_qty > 0:
                        big_assembly_qty = big_assembly_boms[0].product_qty / order.mo_id.bom_id.product_qty
                big_assembly_qty = mo_qty * big_assembly_qty
                # Remove old drawing order lines
                old_drawing_order_line_ids = drawing_order_line_obj.search(cr, uid, [
                    ('order_id', '=', order.id)
                ])
                drawing_order_line_obj.unlink(cr, uid, old_drawing_order_line_ids)
                # Read the bom file and add parts
                inputStr = StringIO.StringIO()
                inputStr.write(order.bom_file.decode('base64'))
                workbook = xlrd.open_workbook(file_contents=inputStr.getvalue())
                worksheet = workbook.sheet_by_index(0)
                row = 2
                while row < worksheet.nrows:
                    bom_line = self.read_bom_line(worksheet=worksheet, row=row)
                    if bom_line['part_name']:
                        item_no = bom_line['item_no']
                        part_name = bom_line['part_name']
                        erp_no = bom_line['erp_no']
                        description = bom_line['description']
                        bom_qty = int(bom_line['bom_qty'])
                        standard = bom_line['standard']
                        material = bom_line['material']
                        thickness = bom_line['thickness']
                        need_qty = bom_qty * big_assembly_qty
                        part_type = bom_line['part_type']
                        work_steps = bom_line['work_steps']
                        steps = self.split_work_steps(work_steps)
                        if part_name:
                            product_ids = product_obj.search(cr, uid, [
                                ('default_code', '=', erp_no)
                            ])
                            product_id = product_ids[0]
                            first_step = steps[0]
                            last_step = steps[len(steps) - 1]
                            # Check if drawing order line exits ?
                            order_line_ids = drawing_order_line_obj.search(cr, uid, [
                                ('order_id', '=', order.id),
                                ('product_id', '=', product_id),
                                ('work_steps', '=', work_steps)
                            ])
                            order_line_id = False
                            if order_line_ids:
                                order_line_id = order_line_ids[0]
                            else:
                                order_line_id = drawing_order_line_obj.create(cr, uid, {
                                    'order_id': order.id,
                                    'product_id': product_id,
                                })
                            order_line = drawing_order_line_obj.browse(cr, uid, order_line_id)
                            vals = {
                                'item_no': item_no,
                                'bom_qty': bom_qty,
                                'work_steps': work_steps,
                                'first_step': first_step,
                                'last_step': last_step,
                                'part_type': part_type,
                                'description': description,
                                'erp_no': erp_no,
                                'material': material,
                                'standard': standard,
                                'thickness': thickness,
                            }
                            for step in steps:
                                vals.update({
                                    '%s_need_qty' % (step,): need_qty + getattr(order_line, "%s_need_qty" % step, 0),
                                    '%s_prepare_qty' % (step,): 0,
                                    '%s_done_qty' % (step,): 0,
                                })
                            vals.update({'%s_prepare_qty' % (first_step,): need_qty + getattr(order_line,
                                                                                              "%s_prepare_qty" % first_step,
                                                                                              0)})
                            drawing_order_line_obj.write(cr, uid, order_line_id, vals)
                    row += 1
        return result

    # --- HoangTK - 11/17/2015
    # +++ HoangTK - 12/08/2015: Override write method to update drawing order quantity
    def update_qty(self, cr, uid, ids):
        for order in self.browse(cr, uid, ids):
            prepare_qty = 0
            done_qty = 0
            need_qty = 0
            for order_line in order.order_lines:
                prepare_qty += getattr(order_line, "%s_prepare_qty" % order_line.last_step, 0)
                done_qty += getattr(order_line, "%s_done_qty" % order_line.last_step, 0)
                need_qty += getattr(order_line, "%s_need_qty" % order_line.last_step, 0)
            super(drawing_order, self).write(cr, uid, [order.id], {
                'prepare_qty': prepare_qty,
                'need_qty': need_qty,
                'done_qty': done_qty
            })

    def _generate_name(self, cr, uid, ids, context=None):
        for order in self.browse(cr, uid, ids, context=context):
            mo_id = order.mo_id
            product_id = order.product_id
            if mo_id and product_id:
                name = product_id.name
                mfg_ids = []
                for mfg_id in mo_id.mfg_ids:
                    mfg_ids.append("ID" + str(mfg_id.name))
                mfg_name = "_".join(mfg_ids)
                if mfg_name:
                    name += "-" + mfg_name
                super(drawing_order, self).write(cr, uid, [order.id], {'name': name})

    def create(self, cr, uid, vals, context=None):
        result = super(drawing_order, self).create(cr, uid, vals, context)
        order_history_obj = self.pool.get('drawing.order.history')
        if result:
            self._generate_name(cr, uid, [result], context=context)
            order_history_obj.create(cr, uid, {
                'drawing_order_id': result,
                'user_id': uid,
                'date': datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                'content': _('Create Drawing Order'),
                'vals': '%s' % vals,
            })
        if vals.get('bom_file',False):
            error_logs = self.check_bom_file(cr, uid, [result])
        return result

    def write(self, cr, uid, ids, vals, context=None):
        result = super(drawing_order, self).write(cr, uid, ids, vals, context=context)
        if vals.get('mo_id',False) or vals.get('product_id',False):
            self._generate_name(cr, uid, ids, context=context)
        self.update_qty(cr, uid, ids)
        order_history_obj = self.pool.get('drawing.order.history')
        for order_id in ids:
            order_history_obj.create(cr, uid, {
                'drawing_order_id': order_id,
                'user_id': uid,
                'date': datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                'content': _('Update Drawing Order'),
                'vals': '%s' % vals,
            })
        if vals.get('bom_file', False):
            error_logs = self.check_bom_file(cr, uid, ids)
        return result

    def get_missing_erpno_parts(self, cr, uid, bom_file_content):
        missing_parts = []
        if bom_file_content:
            inputStr = StringIO.StringIO()
            inputStr.write(bom_file_content.decode('base64'))
            workbook = xlrd.open_workbook(file_contents=inputStr.getvalue())
            worksheet = workbook.sheet_by_index(0)
            row = 2
            while row < worksheet.nrows:
                bom_line = self.read_bom_line(worksheet=worksheet, row=row)
                if bom_line['part_name'] and not bom_line['erp_no']:
                    missing_parts.append(bom_line)
                row += 1
        return missing_parts

    def create_missing_erpno(self, cr, uid, ids, context=None):
        missing_erpno_obj = self.pool.get('missing.erpno')
        missing_erpno_line_obj = self.pool.get('missing.erpno.line')
        for order in self.browse(cr, uid, ids):
            missing_id = missing_erpno_obj.create(cr, uid, {'order_id': order.id})
            missing_erpno_parts = self.get_missing_erpno_parts(cr, uid, order.bom_file)
            for part in missing_erpno_parts:
                missing_erpno_line_obj.create(cr, uid, {
                    'missing_id': missing_id,
                    'item_no': part['item_no'],
                    'name': part['part_number'],
                    'description': part['description'],
                })
        return True

    # --- HoangTK - 12/08/2015: Override write method to update drawing order quantity
    def print_pdf(self, cr, uid, ids, context=None):
        order_line_ids = []
        for id in ids:
            order = self.read(cr, uid, id, ['name', 'order_lines'], context=context)
            if len(ids) == 1:
                context['order_name'] = order['name']
            order_line_ids += order['order_lines']

        return self.pool.get('drawing.order.line').print_pdf(cr, uid, order_line_ids, context=context)

    def onchange_mo_id_product_id(self, cr, uid, ids, mo_id, product_id, context=None):
        vals = {}
        if mo_id:
            mo = self.pool.get('mrp.production').browse(cr, uid, mo_id)
            vals.update({'mo_bigsubassembly_ids': self._get_product_ids_from_mo(cr, uid, mo)})
        if mo_id and product_id:
            duplicate_do_ids = self.search(cr, uid, [
                ('mo_id','=',mo_id),
                ('product_id','=',product_id),
                ('state','not in',['rejected','cancel'])
            ])
            if len(duplicate_do_ids) > 1:
                return self.pool.get('warning').info(cr, uid, title='Warning', message=_("There is another DO with the same MO and Big Subassembly, consider to revise it!"))
        return {'value': vals}

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        if view_type == 'form' and not view_id:
            view_name = 'view_drawing_order_form'
            view_obj = self.pool.get('ir.ui.view')
            view_ids = view_obj.search(cr, uid, [('name', '=', view_name)])
            if view_ids:
                view = view_obj.browse(cr, uid, view_ids[0])
                department_obj = self.pool.get('hr.department')
                department_ids = department_obj.search(cr, uid, [('code', 'in', WORK_STEP_LIST)], order='sequence asc')
                departments = department_obj.browse(cr, uid, department_ids)
                work_step_fields = ''
                for department in departments:
                    work_step_fields = work_step_fields + \
                                       "<field name='%s_prepare_qty' attrs=\"{'invisible':[('%s_prepare_qty', '==', 0)]}\" readonly='1'/> \
                                       <field name='%s_done_qty' attrs=\"{'invisible':[('%s_done_qty', '==', 0)]}\" readonly='1'/> \
                                       <field name='%s_need_qty' attrs=\"{'invisible':[('%s_need_qty', '==', 0)]}\" readonly='1'/>" % (
                                       department.code, department.code, department.code, department.code,
                                       department.code, department.code)
                arch_parts = view.arch.split('<!--DYNAMIC WORKSTEPS DO NOT DELETE-->')
                if len(arch_parts) == 3:
                    view_arch = arch_parts[0] + '<!--DYNAMIC WORKSTEPS DO NOT DELETE-->' + \
                                work_step_fields + '<!--DYNAMIC WORKSTEPS DO NOT DELETE-->' + \
                                arch_parts[2]
                    view_obj.write(cr, SUPERUSER_ID, [view_ids[0]], {
                        'arch': view_arch
                    })
        res = super(drawing_order, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
        return res


class drawing_step(osv.osv):
    _name = "drawing.step"
    _description = "Drawing Step"
    _columns = {
        'name': fields.char('Name', size=32),
    }
    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Name must be unique!'),
    ]


class drawing_order_line(osv.osv):
    _name = "drawing.order.line"
    _description = "Drawing Order Line"
    _rec_name = "drawing_file_name"
    # +++ HoangTK - 11/06/2015: Order by Drawing PDF Name asc
    _order = "item_no asc"

    # --- HoangTK
    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        if view_type == 'form' and not view_id:
            view_name = 'view_drawing_order_line_form'
            view_obj = self.pool.get('ir.ui.view')
            view_ids = view_obj.search(cr, uid, [('name', '=', view_name)])
            if view_ids:
                view = view_obj.browse(cr, uid, view_ids[0])
                department_obj = self.pool.get('hr.department')
                department_ids = department_obj.search(cr, uid, [('code', 'in', WORK_STEP_LIST)], order='sequence asc')
                departments = department_obj.browse(cr, uid, department_ids)
                work_step_fields = '<group colspan="4" col="72">'
                for department in departments:
                    work_step_fields = work_step_fields + \
                                       "<label string='%s P' colspan='2' class='metro_header_label'/> \
                                       <label string='%s D' colspan='2' class='metro_header_label'/> \
                                       <label string='%s N' colspan='2' class='metro_header_label'/>" % (
                                       department.code, department.code, department.code)
                for department in departments:
                    work_step_fields = work_step_fields + \
                                       "<field name='%s_prepare_qty' nolabel='1' colspan='2'/> \
                                       <field name='%s_done_qty' nolabel='1' colspan='2'/> \
                                       <field name='%s_need_qty' nolabel='1' colspan='2'/>" % (
                                       department.code, department.code, department.code)
                work_step_fields = work_step_fields + '</group>'
                arch_parts = view.arch.split('<!--DYNAMIC WORKSTEPS DO NOT DELETE-->')
                if len(arch_parts) == 3:
                    view_arch = arch_parts[0] + '<!--DYNAMIC WORKSTEPS DO NOT DELETE-->' + \
                                work_step_fields + '<!--DYNAMIC WORKSTEPS DO NOT DELETE-->' + \
                                arch_parts[2]
                    view_obj.write(cr, SUPERUSER_ID, [view_ids[0]], {
                        'arch': view_arch
                    })
        res = super(drawing_order_line, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
        return res

    _columns = {
        'order_id': fields.many2one('drawing.order', 'Drawing Order'),
        # +++ HoangTK - 11/17/2015: Change name to Part
        # 'product_id': fields.many2one('product.product','Sub Product'),
        'product_id': fields.many2one('product.product', 'Part'),
        # --- HoangTK - 11/17/2015
        'drawing_file_name': fields.char('Drawing PDF Name', size=64),
        'drawing_file': fields.function(utils.field_get_file, fnct_inv=utils.field_set_file, string="Drawing PDF",
                                        type="binary", multi="_get_file", ),
        'step_ids': fields.many2many('drawing.step', string='Working Steps'),
        'company_id': fields.related('order_id', 'company_id', type='many2one', relation='res.company',
                                     string='Company'),
        'create_uid': fields.many2one('res.users', 'Creator', readonly=True),
        'create_date': fields.datetime('Creation Date', readonly=True),
        'state': fields.selection(
            [('draft', 'Draft'), ('ready', 'Ready'), ('confirmed', 'Confirmed'), ('approved', 'Approved'),
             ('rejected', 'Rejected'), ('cancel', 'Cancelled')], 'Status', required=True, readonly=True),
        # order fields to show in the drawing files view
        'sale_product_ids': fields.related('order_id', 'sale_product_ids', type='many2many', relation='sale.product',
                                           rel='drawing_order_id_rel', id1='drawing_order_id', id2='id_id',
                                           string="MFG IDs", readonly=True,
                                           states={'draft': [('readonly', False)], 'rejected': [('readonly', False)]}),
        'main_part_id': fields.related('order_id', 'main_part_id', type='many2one', relation='product.product',
                                       string='Main Product'),
        # +++ HoangTK - 11/17/2015: Add quantity and work steps to drawing order lines
        'name': fields.related('product_id', 'name', string="Name", type="string", readonly=True),
        'bom_qty': fields.integer('BOM Qty', readonly=True),
        'P_prepare_qty': fields.integer('P P', readonly=True),
        'P_done_qty': fields.integer('P D'),
        'P_need_qty': fields.integer('P N', readonly=True),
        'Fc_prepare_qty': fields.integer('Fc P', readonly=True),
        'Fc_done_qty': fields.integer('Fc D'),
        'Fc_need_qty': fields.integer('Fc N', readonly=True),
        'B_prepare_qty': fields.integer('B P', readonly=True),
        'B_done_qty': fields.integer('B D'),
        'B_need_qty': fields.integer('B N', readonly=True),
        'Ma_prepare_qty': fields.integer('Ma P', readonly=True),
        'Ma_done_qty': fields.integer('Ma D'),
        'Ma_need_qty': fields.integer('Ma N', readonly=True),
        'D_prepare_qty': fields.integer('D P', readonly=True),
        'D_done_qty': fields.integer('D D'),
        'D_need_qty': fields.integer('D N', readonly=True),
        'Mi_prepare_qty': fields.integer('Mi P', readonly=True),
        'Mi_done_qty': fields.integer('Mi D'),
        'Mi_need_qty': fields.integer('Mi N', readonly=True),
        'W_prepare_qty': fields.integer('W P', readonly=True),
        'W_done_qty': fields.integer('W D'),
        'W_need_qty': fields.integer('W N', readonly=True),
        'A_prepare_qty': fields.integer('A P', readonly=True),
        'A_done_qty': fields.integer('A D'),
        'A_need_qty': fields.integer('A N', readonly=True),
        'Ct_prepare_qty': fields.integer('Ct P', readonly=True),
        'Ct_done_qty': fields.integer('Ct D'),
        'Ct_need_qty': fields.integer('Ct N', readonly=True),
        'Bt_prepare_qty': fields.integer('Bt P', readonly=True),
        'Bt_done_qty': fields.integer('Bt D'),
        'Bt_need_qty': fields.integer('Bt N', readonly=True),
        'Ps_prepare_qty': fields.integer('Ps P', readonly=True),
        'Ps_done_qty': fields.integer('Ps D'),
        'Ps_need_qty': fields.integer('Ps N', readonly=True),
        'G_prepare_qty': fields.integer('G P', readonly=True),
        'G_done_qty': fields.integer('G D'),
        'G_need_qty': fields.integer('G N', readonly=True),
        'K_prepare_qty': fields.integer('K P', readonly=True),
        'K_done_qty': fields.integer('K D'),
        'K_need_qty': fields.integer('K N', readonly=True),
        'work_steps': fields.char('Work Steps', size=128, readonly=True),
        'last_step': fields.char('Last Step', size=128, readonly=True),
        'first_step': fields.char('Last Step', size=128, readonly=True),
        'status': fields.char('Status', size=50, readonly=True),
        'part_type': fields.selection(PART_TYPE_SELECTION, string='Part Type', readonly=True),
        'item_no': fields.char('Item No.', size=50, readonly=True),
        'description': fields.char('Description', size=128, readonly=True),
        'erp_no': fields.char('ERP #', size=128, readonly=True),
        'material': fields.char('Material', size=128, readonly=True),
        'standard': fields.char('Standard', size=128, readonly=True),
        'thickness': fields.char('Thickness', size=128, readonly=True),
        # --- HoangTK - 11/17/2015
    }

    _defaults = {
        'state': 'draft',
    }

    @staticmethod
    def _format_file_name(file_name):
        file_reserved_char = ('/', '\\', '<', '>', '*', '?')
        new_file_name = file_name
        for char in file_reserved_char:
            new_file_name = new_file_name.replace(char, '-')
        return new_file_name

    def print_pdf(self, cr, uid, ids, context):
        attachment_obj = self.pool.get('ir.attachment')
        output = PdfFileWriter()
        page_cnt = 0
        order = self.browse(cr, uid, ids[0], context=context)
        lines = self.browse(cr, uid, ids, context=context)
        for line in lines:
            if line.drawing_file_name and line.drawing_file_name.lower().endswith('.pdf'):
                file_ids = attachment_obj.search(
                    cr, uid, [('name', '=', 'drawing_file'),
                              ('res_id', '=', line.id),
                              ('res_model', '=', 'drawing.order.line')])
                if file_ids:
                    attach_file = attachment_obj.file_get(cr, uid, file_ids[0], context=context)
                    input = PdfFileReader(attach_file)
                    if line.order_id.state == 'confirmed' and line.order_id.company_id.stamp:
                        watermark_file = tempfile.NamedTemporaryFile(delete=False)
                        watermark_file_name = watermark_file.name
                        watermark_file.close()
                        outputStr = file(watermark_file_name, "wb")
                        outputStr.write(line.order_id.company_id.stamp.decode('base64'))
                        outputStr.close()
                        #inputStr = StringIO.StringIO()
                        #inputStr.write(line.order_id.company_id.stamp_landscape.decode('base64'))
                        #watermark = PdfFileReader(inputStr)

                        for page in input.pages:
                            imgTemp = StringIO.StringIO()
                            imgDoc = canvas.Canvas(imgTemp)
                            imgDoc.setPageSize((page.mediaBox.getLowerRight_x(),
                                                page.mediaBox.getUpperRight_y()))
                            # Draw image on Canvas and save PDF in buffer
                            imgDoc.drawImage(watermark_file_name,
                                             float(page.mediaBox.getLowerRight_x()) - 200,
                                             170,
                                             110, 110, mask='auto')
                            imgDoc.drawString(float(page.mediaBox.getLowerRight_x()) - 175,200,line.order_id.confirm_date)
                            imgDoc.save()

                            # Use PyPDF to merge the image-PDF into the template
                            watermark = PdfFileReader(StringIO.StringIO(imgTemp.getvalue()))
                            page.mergePage(watermark.getPage(0))
                            output.addPage(page)
                            page_cnt += 1
                    else:
                        for page in input.pages:
                            output.addPage(page)
                            page_cnt += 1
        if page_cnt > 0:
            # +++ HoangTK - 12/10/2015: Use system temp file
            file_name = "Drawing"
            if context.get('order_name'):
                file_name = u'%s-%s.pdf' % (file_name, self._format_file_name(context.get('order_name')))
            temp_drawing_pdf_file = tempfile.NamedTemporaryFile(delete=False)
            temp_drawing_pdf_file_name = temp_drawing_pdf_file.name
            temp_drawing_pdf_file.close()
            outputStream = file(temp_drawing_pdf_file_name, "wb")
            output.write(outputStream)
            outputStream.close()
            #             full_path_temp = attachment_obj.full_path(cr, uid, 'temp')
            # #            file_name = self._format_file_name(order.name)
            #             file_name = "Drawing"
            #             if context.get('order_name'):
            #                 file_name = '%s-%s'%(file_name, self._format_file_name(context.get('order_name')))
            #             full_file_name =  '%s/%s.pdf'%(full_path_temp, file_name,)
            #             outputStream = file(full_file_name, "wb")
            #             output.write(outputStream)
            #             outputStream.close()
            #             filedata = open(full_file_name,'rb').read().encode('base64')
            #             os.remove(full_file_name)
            # --- HoangTK - 12/10/2015: Use system temp file
            # +++ HoangTK - 12/10/2015: Replace print_pdf to fix memory error when pdf is too large
            return {
                'type': 'ir.actions.act_url',
                # 'url': '/web/export/print_pdf?filename=%s&filedata=%s'%(file_name, filedata),
                'url': '/web/export/drawing_order_print_pdf?file_name=%s&file_data=%s' % (
                file_name, temp_drawing_pdf_file_name),
                'target': 'self',
            }

            # return self.pool.get('file.down').download_data(cr, uid, "%s.pdf"%(file_name,), filedata, context)
            # --- HoangTK - 12/10/2015: Replace print_pdf to fix memory error when pdf is too large
        else:
            raise osv.except_osv(_("Error!"), _('No PDF files were found!'))

    def unlink(self, cr, uid, ids, context=None):
        # delete the attachments
        for id in ids:
            utils.field_set_file(self, cr, uid, id, 'drawing_file', None, {'unlink': True}, context=None)
        resu = super(drawing_order_line, self).unlink(cr, uid, ids, context=context)
        return resu

    def _check_file_name(self, cr, uid, ids, context=None):
        for record in self.browse(cr, uid, ids, context=context):
            # +++ HoangTK - 11/18/2015: Allow file name is null
            if not record.drawing_file_name:
                continue
            # --- HoangTK - 11/18/2015
            same_file_name_ids = self.search(cr, uid, [('order_id', '=', record.order_id.id), ('id', '!=', record.id),
                                                       ('drawing_file_name', '=', record.drawing_file_name)],
                                             context=context)
            if same_file_name_ids:
                # +++ HoangTK - 11/18/2015: Fix bug file_name not found in drawing_order_line
                # raise osv.except_osv(_('Error'), _('Drawring file "%s" is duplicated under same order!')% (record.file_name,))
                raise osv.except_osv(_('Error'), _('Drawing file "%s" is duplicated under same order!') % (
                record.drawing_file_name,))
                # --- HoangTK - 11/18/2015

        return True

    _constraints = [
        (_check_file_name,
         'Drawing file name is duplicated under same order!',
         ['file_name'])
    ]

    def copy_data(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}
        line_data = self.browse(cr, uid, id, context=context)
        default.update({
            'drawing_file': line_data.drawing_file
        })

        return super(drawing_order_line, self).copy_data(cr, uid, id, default, context)

    def create(self, cr, uid, vals, context=None):
        result = super(drawing_order_line, self).create(cr, uid, vals, context)
        order_history_obj = self.pool.get('drawing.order.history')
        if result:
            order_line = self.browse(cr, uid, result)
            order_history_obj.create(cr, uid, {
                'po_id': order_line.order_id.id,
                'user_id': uid,
                'date': datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                'content': _('Create Drawing Order Line'),
                'vals': '%s' % vals,
            })
        return result

    # +++ HoangTK - 12/08/2015: Override write method to update drawing order quantity
    def write(self, cr, uid, ids, vals, context=None):
        if not isinstance(ids, list):
            ids = [ids]
        result = super(drawing_order_line, self).write(cr, uid, ids, vals, context=context)
        order_line_vals = self.read(cr, uid, ids, ['order_id'])
        drawing_ids = []
        for value in order_line_vals:
            if value['order_id'][0] not in drawing_ids:
                drawing_ids.append(value['order_id'][0])
        drawing_order_obj = self.pool.get('drawing.order')
        drawing_order_obj.update_qty(cr, uid, drawing_ids)
        order_history_obj = self.pool.get('drawing.order.history')
        for order_line in self.browse(cr, uid, ids):
            order_history_obj.create(cr, uid, {
                'po_id': order_line.order_id.id,
                'user_id': uid,
                'date': datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                'content': _('Update Drawing Order Line'),
                'vals': '%s' % vals,
            })
        return result
        # --- HoangTK - 12/08/2015: Override write method to update drawing order quantity
