# -*- encoding: utf-8 -*-
from osv import fields,osv
from openerp.tools.translate import _
from openerp import netsvc
import time
import datetime
from openerp.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT
from openerp.report.pyPdf import PdfFileWriter, PdfFileReader
from openerp.addons.metro import utils
import zipfile
import random
import os
from openerp import SUPERUSER_ID
import xlrd
import StringIO
try:
    import json
except ImportError:
    import simplejson as json  
import tempfile
PART_TYPE_SELECTION = [('PRODUCED','PRODUCED'),
                       ('PURCH-M','PURCH-M'),
                       ('PURCH-S','PURCH-S'),
                       ('PURCH-OEM','PURCH-OEM')]
class drawing_order(osv.osv):
    _name = "drawing.order"
    _inherit = ['mail.thread']
    _description = "Drawing Order"
    _order = 'id desc'
    _columns = {
        'name': fields.char('Name', size=64, required=True,readonly=True, states={'draft':[('readonly',False)],'rejected':[('readonly',False)]}),
        'note': fields.text('Description', required=False),
        #+++ HoangTK - 11/17/2015: Change sale_product_ids to related field of mo_id
        #'sale_product_ids': fields.many2many('sale.product','drawing_order_id_rel','drawing_order_id','id_id',
        #                                     string="MFG IDs",readonly=True, states={'draft':[('readonly',False)],'rejected':[('readonly',False)]}),
        'sale_product_ids': fields.related('mo_id','mfg_ids',type="many2many",  relation="sale.product", string="MFG IDs",readonly=True),                
        #--- HoangTK - 11/17/2015
        'order_lines': fields.one2many('drawing.order.line','order_id','Drawing Order Lines',readonly=True, states={'draft':[('readonly',False)],'rejected':[('readonly',False)]}),
        'state': fields.selection([('draft','Draft'),('ready','Ready'),('confirmed','Confirmed'),('approved','Approved'),('rejected','Rejected'),('cancel','Cancelled')],
            'Status', track_visibility='onchange', required=True),
        'reject_message': fields.text('Rejection Message', track_visibility='onchange'),
        'create_uid': fields.many2one('res.users','Creator',readonly=True),
        'create_date': fields.datetime('Creation Date', readonly=True),   
#        'date_finished': fields.datetime('Finished Date', readonly=True),
        'company_id': fields.many2one('res.company', 'Company', readonly=True),
        #+++ HoangTK 11/17/2015: Replace product_id below     
        #'product_id': fields.related('order_lines','product_id', type='many2one', relation='product.product', string='Product'),
        #--- HoangTK 11/17/2015
        'main_part_id': fields.many2one('product.product','Main Product',readonly=True, states={'draft':[('readonly',False)],'rejected':[('readonly',False)]}),
        'bom_file_name': fields.char('BOM File Name', size=64),
        'bom_file': fields.function(utils.field_get_file, fnct_inv=utils.field_set_file, string="BOM File", type="binary", multi="_get_file",),
        #+++ HoangTK - 11/16/2015: Attach drawing order to MO
        'mo_id': fields.many2one('mrp.production','Manufacturer Order'),
        'product_id': fields.many2one('product.product','Big Sub Assembly',required=True),
        'prepare_qty': fields.integer('Prepare Qty',readonly=True),
        'done_qty': fields.integer('Done Qty',readonly=True),
        'need_qty': fields.integer('Need Qty',readonly=True),         
        #--- HoangTK - 11/16/2015
    }
    _defaults = {
        'company_id': lambda self, cr, uid, c: self.pool.get('res.company')._company_default_get(cr, uid, 'drawing.order', context=c),
        'state': 'draft',
    }
    _order = 'id desc'
    
    def _set_state(self,cr,uid,ids,state,context=None):
        self.write(cr,uid,ids,{'state':state},context=context)
        line_ids = []
        for order in self.browse(cr,uid,ids,context=context):
            for line in order.order_lines:
                if not line.state == 'done':
                    line_ids.append(line.id)
        self.pool.get('drawing.order.line').write(cr,uid,line_ids,{'state':state})

    def _check_done_lines(self,cr,uid,ids,context=None):
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
                    email_subject = 'Drawing reminder: %s %s'%(order.name,action_name)
                    mfg_id_names = ','.join([mfg_id.name for mfg_id in order.sale_product_ids])
                    #[(id1,name1),(id2,name2),...(idn,namen)]
                    main_part_name = ''
                    if order.main_part_id:
                        main_part_name = self.pool.get('product.product').name_get(cr, uid,  [order.main_part_id.id], context=context)[0][1]
                    email_body = '%s %s %s, MFG IDs:%s'%(order.name,main_part_name, action_name,mfg_id_names)
                    email_from = self.pool.get("res.users").read(cr, uid, uid, ['email'],context=context)['email']
                    utils.email_send_group(cr, uid, email_from, None,email_subject,email_body, email_group_id, context=context)
        
    def action_ready(self, cr, uid, ids, context=None):
        #+++ HoangTK - 12/14/2015 : Check if drawing order ready
        if not self._is_ready(cr, uid, ids, context=context):
            return False
        #+++ HoangTK - 12/14/2015 : Check if drawing order ready
        #set the ready state
        self._set_state(cr, uid, ids, 'ready',context)
        #send email to the user group that can confirm
        self._email_notify(cr, uid, ids, 'need your confirmation', ['mrp_cnc_wo_group_confirm'],context)     
        return True
        
    #+++ HoangTK - 12/14/2015 : Add check drawing order lines into a separate function
    def _is_ready(self, cr, uid, ids, context=None):
        for order in self.browse(cr, uid, ids, context=context):
            #must have cnc lines
            if not order.order_lines:
                raise osv.except_osv(_('Error!'), _('Please add lines for order [%s]%s')%(order.id, order.name))
            for line in order.order_lines:
                if line.part_type == 'PRODUCED' and not line.drawing_file_name:
                    raise osv.except_osv(_('Error!'), _('All produced parts must have drawing PDFs!'))
        return True
    #--- HoangTK - 12/14/2015
    def action_confirm(self, cr, uid, ids, context=None):
        #+++ HoangTK - 12/14/2015 : Move to action_ready
#         for order in self.browse(cr, uid, ids, context=context):
#             #must have cnc lines
#             if not order.order_lines:
#                 raise osv.except_osv(_('Error!'), _('Please add lines for order [%s]%s')%(order.id, order.name))
#             for line in order.order_lines:
#                 if not line.drawing_file_name:
#                     raise osv.except_osv(_('Invalid Action!'), _('The line''s "Drawing PDF" file is required!'))
        #--- HoangTK - 12/14/2015 : Move to action_ready
        #set state to done
        self._set_state(cr, uid, ids, 'confirmed',context)
        #send email to the user group that can approve
        self._email_notify(cr, uid, ids, 'need your approval', ['mrp_cnc_wo_group_approve'],context)           
        return True

    def action_cancel(self, cr, uid, ids, context=None):
        self._check_done_lines(cr,uid,ids,context)
        #set the cancel state
        self._set_state(cr, uid, ids, 'cancel',context)
        return True
    
    def action_draft(self, cr, uid, ids, context=None):
        #set the cancel state
        self._set_state(cr, uid, ids, 'draft',context)
        return True

    def action_approve(self, cr, uid, ids, context=None):
        #set the cancel state
        self._set_state(cr, uid, ids, 'approved',context)
        #send email to the user group that can CNC done
        self._email_notify(cr, uid, ids, 'was approved', ['mrp_cnc_wo_group_cnc_mgr'],context) 
        return True

    def action_reject_callback(self, cr, uid, ids, message, context=None):
        #set the draft state
        self._set_state(cr, uid, ids, 'rejected',context)
        self.write(cr,uid,ids,{'reject_message':message})
        #send email to the user for the rejection message
        email_from = self.pool.get("res.users").read(cr, uid, uid, ['email'],context=context)['email']
        for order in self.browse(cr, uid, ids, context=context):
            if order.create_uid.email:
                email_content = 'CNC reminder: %s was rejected'%(order.name)
                utils.email_send_group(cr, uid, email_from, order.create_uid.email,email_content,email_content, context = context) 
        return True
                    
    def action_reject(self, cr, uid, ids, context=None):     
        ctx = dict(context)
        ctx.update({'confirm_title':'Confirm rejection message',
                    'src_model':'drawing.order',
                    "model_callback":'action_reject_callback',})
        return self.pool.get('confirm.message').open(cr, uid, ids, ctx)
                
    def unlink(self, cr, uid, ids, context=None):
        orders = self.read(cr, uid, ids, ['state'], context=context)
        for s in orders:
            if s['state'] not in ['draft','cancel']:
                raise osv.except_osv(_('Invalid Action!'), _('Only the orders in draft or cancel state can be delete.'))
        self._check_done_lines(cr,uid,ids,context)
        return super(drawing_order, self).unlink(cr, uid, ids, context=context)
    
    def copy(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}
        old_data = self.read(cr,uid,id,['name'],context=context)
        default.update({
            'name': '%s (copy)'%old_data['name'],
            'mfg_task_id': None,
            'sale_product_ids': None,
            'reject_message':None,
        })
        return super(drawing_order, self).copy(cr, uid, id, default, context)    
    #+++ HoangTK - 11/17/2015: Add update_parts function
    def _split_work_steps(self, work_steps):
        steps = []
        if work_steps:
            steps = work_steps.split(' ')
        return steps
    def generate_pr(self, cr, uid, ids, context):
        mod_obj = self.pool.get('ir.model.data')
        res = mod_obj.get_object_reference(cr, uid, 'metro_mrp_drawing', 'view_generate_pr_wizard')
        res_id = res and res[1] or False
        return{
            'name':'Purchase Requisition Generator',
            'res_model':'generate.pr.wizard',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': [res_id],
            'context':{'drawing_order_ids': ids},
            'target':'new'
             }
    def generate_tasks(self, cr, uid, ids, context):
        workcenter_line_obj = self.pool.get('mrp.production.workcenter.line')
        production_obj = self.pool.get('mrp.production')
        project_task_obj = self.pool.get('project.task')
        project_task_line_obj = self.pool.get('project.task.line')
        dept_obj = self.pool.get('hr.department')
        drawing_order_obj = self.pool.get('drawing.order')
        project_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'metro_project', 'project_mfg')[1]
        for order in self.browse(cr, uid, ids):
            #Check if work order exists ? if not create it
            product = order.product_id
            mo = order.mo_id
            wo_line_ids = workcenter_line_obj.search(cr, uid, [
                                                               ('production_id','=',mo.id),
                                                               ('big_subassembly_id','=',product.id)
                                                               ]) 
            if not wo_line_ids:
                production_obj.action_compute_an_assembly(cr, uid, [mo.id],assembly_id = product.id)
            wo_line_ids = workcenter_line_obj.search(cr, uid, [
                                                               ('production_id','=',mo.id),
                                                               ('big_subassembly_id','=',product.id)
                                                               ]) 
            if not wo_line_ids:
                raise osv.except_osv(_('Error!'), _('Can not create work order for assembly %s !') % (product.name,))
            if len(wo_line_ids) != 1:
                raise osv.except_osv(_('Error!'), _('There are more than 2 work orders for assembly %s !') % (product.name,))
            wo = workcenter_line_obj.browse(cr, uid, wo_line_ids)[0]
            if wo.state != 'draft':
                raise osv.except_osv(_('Error!'), _('Can not generate tasks for work order not in draft state !'))
            #Remove all current tasks
            old_task_ids = project_task_obj.search(cr, uid, [('workorder_id','=',wo.id)])
            project_task_obj.unlink(cr, uid, old_task_ids)
            #Create all new tasks
            all_drawing_steps = []    
            all_steps = {}        
            for order_line in order.order_lines:
                steps = drawing_order_obj._split_work_steps(order_line.work_steps)
                for step in steps:
                    if not step in all_steps:
                        all_drawing_steps.append(step)
                        all_steps.update({step: True})
            for step in all_drawing_steps:
                dept_ids = dept_obj.search(cr, uid, [
                                                     ('code','=',step)
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
            #Add product and qty to task
            wo = workcenter_line_obj.browse(cr, uid, wo_line_ids)[0]
            for task_id in wo.task_ids:
                prepare_qty = 0
                need_qty = 0
                for order_line in task_id.drawing_order_lines:
                    task_line_vals = {
                                      'task_id': task_id.id,
                                      'product_id': order_line.product_id.id,
                                      'prepare_qty': 0,
                                      'done_qty': 0,
                                      'need_qty': 0,
                                      'next_step': '',
                                      }
                    
                    if task_id.dept_code == "P":
                        task_line_vals.update({
                                               'prepare_qty': order_line.P_prepare_qty,
                                               'done_qty': order_line.P_done_qty,
                                               'need_qty': order_line.P_need_qty,
                                               })
                        prepare_qty += order_line.P_prepare_qty
                        need_qty += order_line.P_need_qty
                    if task_id.dept_code == "Fc":
                        task_line_vals.update({
                                               'prepare_qty': order_line.Fc_prepare_qty,
                                               'done_qty': order_line.Fc_done_qty,
                                               'need_qty': order_line.Fc_need_qty,
                                               })
                        prepare_qty += order_line.Fc_prepare_qty
                        need_qty += order_line.Fc_need_qty                            
                    if task_id.dept_code == "B":
                        task_line_vals.update({
                                               'prepare_qty': order_line.B_prepare_qty,
                                               'done_qty': order_line.B_done_qty,
                                               'need_qty': order_line.B_need_qty,
                                               })
                        prepare_qty += order_line.B_prepare_qty
                        need_qty += order_line.B_need_qty                                
                    if task_id.dept_code == "Ma":
                        task_line_vals.update({
                                               'prepare_qty': order_line.Ma_prepare_qty,
                                               'done_qty': order_line.Ma_done_qty,
                                               'need_qty': order_line.Ma_need_qty,
                                               })
                        prepare_qty += order_line.Ma_prepare_qty
                        need_qty += order_line.Ma_need_qty                            
                    if task_id.dept_code == "D":
                        task_line_vals.update({
                                               'prepare_qty': order_line.D_prepare_qty,
                                               'done_qty': order_line.D_done_qty,
                                               'need_qty': order_line.D_need_qty,
                                               })
                        prepare_qty += order_line.D_prepare_qty
                        need_qty += order_line.D_need_qty                            
                    if task_id.dept_code == "Mi":
                        task_line_vals.update({
                                               'prepare_qty': order_line.Mi_prepare_qty,
                                               'done_qty': order_line.Mi_done_qty,
                                               'need_qty': order_line.Mi_need_qty,
                                               }) 
                        prepare_qty += order_line.Mi_prepare_qty
                        need_qty += order_line.Mi_need_qty                            
                    if task_id.dept_code == "W":
                        task_line_vals.update({
                                               'prepare_qty': order_line.W_prepare_qty,
                                               'done_qty': order_line.W_done_qty,
                                               'need_qty': order_line.W_need_qty,
                                               })
                        prepare_qty += order_line.W_prepare_qty
                        need_qty += order_line.W_need_qty                            
                    if task_id.dept_code == "A":
                        task_line_vals.update({
                                               'prepare_qty': order_line.A_prepare_qty,
                                               'done_qty': order_line.A_done_qty,
                                               'need_qty': order_line.A_need_qty,
                                               })
                        prepare_qty += order_line.A_prepare_qty
                        need_qty += order_line.A_need_qty                            
                    if task_id.dept_code == "Ct":
                        task_line_vals.update({
                                               'prepare_qty': order_line.Ct_prepare_qty,
                                               'done_qty': order_line.Ct_done_qty,
                                               'need_qty': order_line.Ct_need_qty,
                                               })
                        prepare_qty += order_line.Ct_prepare_qty
                        need_qty += order_line.Ct_need_qty                             
                    if task_id.dept_code == "Ps":
                        task_line_vals.update({
                                               'prepare_qty': order_line.Ps_prepare_qty,
                                               'done_qty': order_line.Ps_done_qty,
                                               'need_qty': order_line.Ps_need_qty,
                                               })
                        prepare_qty += order_line.Ps_prepare_qty
                        need_qty += order_line.Ps_need_qty                            
                    if task_id.dept_code == "G":
                        task_line_vals.update({
                                               'prepare_qty': order_line.G_prepare_qty,
                                               'done_qty': order_line.G_done_qty,
                                               'need_qty': order_line.G_need_qty,
                                               })
                        prepare_qty += order_line.G_prepare_qty
                        need_qty += order_line.G_need_qty    
                    steps = drawing_order_obj._split_work_steps(order_line.work_steps)
                    next_step = ""
                    if task_id.dept_code != order_line.last_step:
                        for index, step in enumerate(steps):
                            if step == task_id.dept_code:
                                next_step = steps[index+1]
                                break
                    if task_line_vals["need_qty"] == 0 and next_step == "":
                        next_step = order_line.work_steps                              
                    task_line_vals.update({
                                           'next_step': next_step, 
                                           })                             
                    project_task_line_obj.create(cr, uid, task_line_vals)                     
                project_task_obj.write(cr, uid, [task_id.id], {
                                           'prepare_qty' : prepare_qty,
                                           'need_qty' : need_qty, 
                                             })            
        return True
    def update_parts(self, cr, uid, ids, context):
        """ Read the bom file and add/update part and quantity to drawing order line.
        """        
        result = True
        product_obj = self.pool.get('product.product')
        drawing_order_line_obj = self.pool.get('drawing.order.line')
        bom_obj = self.pool.get('mrp.bom')
        department_obj = self.pool.get('hr.department')
        for drawing_order in self.browse(cr, uid, ids):
            if drawing_order.bom_file:
                mo_qty = drawing_order.mo_id.product_qty
#                 mfg_id_qty = 1
#                 if drawing_order.sale_product_ids:
#                     mfg_id_qty = len(drawing_order.sale_product_ids)
                big_assembly_qty = 1
                big_assembly_bom_ids = bom_obj.search(cr, uid, [
                                                                ('bom_id','=',drawing_order.mo_id.bom_id.id),
                                                                ('product_id','=',drawing_order.product_id.id),
                                                                ])
                if len(big_assembly_bom_ids) > 0 :
                    big_assembly_boms = bom_obj.browse(cr, uid, big_assembly_bom_ids)
                    if drawing_order.mo_id.bom_id.product_qty > 0:
                        big_assembly_qty = big_assembly_boms[0].product_qty /drawing_order.mo_id.bom_id.product_qty
                big_assembly_qty = mo_qty * big_assembly_qty
                #Remove old drawing order lines
                old_drawing_order_line_ids = drawing_order_line_obj.search(cr, uid, [
                                                                                     ('order_id','=',drawing_order.id)
                                                                                     ])
                drawing_order_line_obj.unlink(cr, uid, old_drawing_order_line_ids)
                #Read the bom file and add parts
                inputStr = StringIO.StringIO()
                inputStr.write(drawing_order.bom_file.decode('base64'))   
                workbook = xlrd.open_workbook(file_contents=inputStr.getvalue())
                worksheet = workbook.sheet_by_index(0)
                #Get big sub assembly name
                bigsubassembly_name = worksheet.cell(0,0).value
                if bigsubassembly_name == xlrd.empty_cell.value or bigsubassembly_name != drawing_order.name:
                    raise osv.except_osv(_('Warning!'), _('Assembly name in bom file not match with current drawing order!.'))
                else:
                    row = 2
                    while row < worksheet.nrows:
                        #Read part name
                        part_name = worksheet.cell(row,1).value.strip(' \t').replace('\n', ' ').replace('\r', '')
                        if part_name:
                            #Check if this part is exits
                            product_ids = product_obj.search(cr, uid, [
                                                                       ('name','=',part_name)
                                                                       ])
                            if not product_ids:
                                product_id = product_obj.create(cr, uid, {
                                                                          'name': part_name
                                                                          })
                            else:
                                product_id = product_ids[0]
                            bom_qty = worksheet.cell(row,8).value
                            try:
                                bom_qty = int(bom_qty)
                            except ValueError:
                                raise osv.except_osv(_("Error!"),_('Bom Qty of part %s is not a number. Please check the bom quantity in bom file') % (part_name,))
                                return False
                            need_qty = bom_qty * big_assembly_qty
                            part_type = worksheet.cell(row,7).value
                            part_types = [type[0] for type in PART_TYPE_SELECTION ]
                            if not part_type in part_types:
                                raise osv.except_osv(_("Error!"),_('Part type of part %s is not valid. Please check the part type in bom file') % (part_name,))
                                return False
                            work_steps = worksheet.cell(row,6).value.strip()
                            steps = self._split_work_steps(work_steps)
                            department_ids = department_obj.search(cr, uid, [
                                                                             ('code','in',steps),
                                                                             ])
                            #Check if work steps are correct ?
                            if len(department_ids) != len(steps) or len(steps) == 0:
                                raise osv.except_osv(_("Error!"),_('Work steps of part %s are not right. Please check the work steps in bom file') % (part_name,))
                                return False                                                    
                            first_step = ""
                            last_step = ""
                            if len(steps) > 1:
                                first_step = steps[0]
                                last_step = steps[len(steps)-1]
                            elif len(steps) == 1:
                                first_step = steps[0]
                                last_step = steps[0]
                            #Check if drawing order line exits ?
                            drawing_order_line_ids = drawing_order_line_obj.search(cr, uid, [
                                                                                             ('order_id','=',drawing_order.id),
                                                                                             ('product_id','=',product_id)
                                                                                             ])
                            drawing_order_line_id = False
                            if drawing_order_line_ids:
                                drawing_order_line_id = drawing_order_line_ids[0]
                            else:
                                drawing_order_line_id = drawing_order_line_obj.create(cr, uid, {
                                                                        'order_id': drawing_order.id,
                                                                        'product_id': product_id,
                                                                        })
                            #Update need qty, bom qty, worksteps of this product
                            vals = {
                                    'bom_qty': bom_qty,
                                    'work_steps': work_steps,
                                    'first_step': first_step,
                                    'last_step': last_step,
                                    'part_type': part_type,
                                    }
                            for step in steps:
                                if step == 'P':
                                    vals.update({'P_need_qty': need_qty})
                                    vals.update({'P_prepare_qty': 0})
                                    vals.update({'P_done_qty': 0})
                                if step == 'Fc':
                                    vals.update({'Fc_need_qty': need_qty})
                                    vals.update({'Fc_prepare_qty': 0})
                                    vals.update({'Fc_done_qty': 0})    
                                if step == 'B':
                                    vals.update({'B_need_qty': need_qty})
                                    vals.update({'B_prepare_qty': 0})
                                    vals.update({'B_done_qty': 0})   
                                if step == 'Ma':
                                    vals.update({'Ma_need_qty': need_qty})
                                    vals.update({'Ma_prepare_qty': 0})
                                    vals.update({'Ma_done_qty': 0})     
                                if step == 'D':
                                    vals.update({'D_need_qty': need_qty})
                                    vals.update({'D_prepare_qty': 0})
                                    vals.update({'D_done_qty': 0})
                                if step == 'Mi':
                                    vals.update({'Mi_need_qty': need_qty})
                                    vals.update({'Mi_prepare_qty': 0})
                                    vals.update({'Mi_done_qty': 0}) 
                                if step == 'W':
                                    vals.update({'W_need_qty': need_qty})
                                    vals.update({'W_prepare_qty': 0})
                                    vals.update({'W_done_qty': 0}) 
                                if step == 'A':
                                    vals.update({'A_need_qty': need_qty})
                                    vals.update({'A_prepare_qty': 0})
                                    vals.update({'A_done_qty': 0})
                                if step == 'Ct':
                                    vals.update({'Ct_need_qty': need_qty})
                                    vals.update({'Ct_prepare_qty': 0})
                                    vals.update({'Ct_done_qty': 0}) 
                                if step == 'Bt':
                                    vals.update({'Bt_need_qty': need_qty})
                                    vals.update({'Bt_prepare_qty': 0})
                                    vals.update({'Bt_done_qty': 0}) 
                                if step == 'Ps':
                                    vals.update({'Ps_need_qty': need_qty})
                                    vals.update({'Ps_prepare_qty': 0})
                                    vals.update({'Ps_done_qty': 0})
                                if step == 'G':
                                    vals.update({'G_need_qty': need_qty})
                                    vals.update({'G_prepare_qty': 0})
                                    vals.update({'G_done_qty': 0}) 
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
                            drawing_order_line_obj.write(cr, uid, drawing_order_line_id,vals)                                                                                                                                                                                                                          
                        row += 1
        return result
    #--- HoangTK - 11/17/2015    
    #+++ HoangTK - 12/08/2015: Override write method to update drawing order quantity
    def update_qty(self, cr, uid, ids):
        for order in self.browse(cr, uid, ids):
            prepare_qty = 0
            done_qty = 0
            need_qty = 0
            for order_line in order.order_lines:
                if order_line.last_step == "P":
                    prepare_qty +=  order_line.P_prepare_qty
                    done_qty += order_line.P_done_qty
                    need_qty += order_line.P_need_qty
                if order_line.last_step == "Fc":
                    prepare_qty +=  order_line.Fc_prepare_qty
                    done_qty += order_line.Fc_done_qty
                    need_qty += order_line.Fc_need_qty
                if order_line.last_step == "B":
                    prepare_qty +=  order_line.B_prepare_qty
                    done_qty += order_line.B_done_qty
                    need_qty += order_line.B_need_qty   
                if order_line.last_step == "Ma":
                    prepare_qty +=  order_line.Ma_prepare_qty
                    done_qty += order_line.Ma_done_qty
                    need_qty += order_line.Ma_need_qty
                if order_line.last_step == "D":
                    prepare_qty +=  order_line.D_prepare_qty
                    done_qty += order_line.D_done_qty
                    need_qty += order_line.D_need_qty
                if order_line.last_step == "Mi":
                    prepare_qty +=  order_line.Mi_prepare_qty
                    done_qty += order_line.Mi_done_qty
                    need_qty += order_line.Mi_need_qty
                if order_line.last_step == "W":
                    prepare_qty +=  order_line.W_prepare_qty
                    done_qty += order_line.W_done_qty
                    need_qty += order_line.W_need_qty
                if order_line.last_step == "A":
                    prepare_qty +=  order_line.A_prepare_qty
                    done_qty += order_line.A_done_qty
                    need_qty += order_line.A_need_qty
                if order_line.last_step == "Ct":
                    prepare_qty +=  order_line.Ct_prepare_qty
                    done_qty += order_line.Ct_done_qty
                    need_qty += order_line.Ct_need_qty
                if order_line.last_step == "Ps":
                    prepare_qty +=  order_line.Ps_prepare_qty
                    done_qty += order_line.Ps_done_qty
                    need_qty += order_line.Ps_need_qty
                if order_line.last_step == "G":
                    prepare_qty +=  order_line.G_prepare_qty
                    done_qty += order_line.G_done_qty
                    need_qty += order_line.G_need_qty 
            super(drawing_order,self).write(cr, uid, [order.id],{
                                                                 'prepare_qty': prepare_qty,
                                                                 'need_qty': need_qty,
                                                                 'done_qty': done_qty
                                                                 })                                                                                                                                                                    
        
    def write(self, cr, uid, ids, vals, context=None):
        result = super(drawing_order,self).write(cr, uid, ids, vals, context=context)
        self.update_qty(cr, uid, ids)
        return result    
    #--- HoangTK - 12/08/2015: Override write method to update drawing order quantity
    def print_pdf(self, cr, uid, ids, context):
        order_line_ids = []
        for id in ids:
            order = self.read(cr, uid, id, ['name','order_lines'],context=context)
            if len(ids) == 1:
                context['order_name'] = order['name']
            order_line_ids += order['order_lines']
             
        return self.pool.get('drawing.order.line').print_pdf(cr, uid, order_line_ids, context=context)
    def onchange_mo_id_product_id(self, cr, uid, ids, mo_id, product_id, context=None):
        vals = {}
        if mo_id and product_id:
            mo_id = self.pool.get('mrp.production').browse(cr, uid, mo_id)
            product_id = self.pool.get('product.product').browse(cr, uid, product_id)
            if mo_id and product_id:
                name = product_id.name
                mfg_ids = []
                for mfg_id in mo_id.mfg_ids:
                    mfg_ids.append("ID" + str(mfg_id.name))
                mfg_name = "_".join(mfg_ids)
                if mfg_name:
                    name += "-" + mfg_name 
                vals['name'] = name
        return  {'value': vals} 
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
    #+++ HoangTK - 11/06/2015: Ordery by Drawing PDF Name asc
    _order = "drawing_file_name asc"
    #--- HoangTK
    _columns = {
        'order_id': fields.many2one('drawing.order','Drawing Order'),
        #+++ HoangTK - 11/17/2015: Change name to Part
        #'product_id': fields.many2one('product.product','Sub Product'),
        'product_id': fields.many2one('product.product','Part'),
        #--- HoangTK - 11/17/2015
        'drawing_file_name': fields.char('Drawing PDF Name', size=64),
        'drawing_file': fields.function(utils.field_get_file, fnct_inv=utils.field_set_file, string="Drawing PDF", type="binary", multi="_get_file",),
        'step_ids': fields.many2many('drawing.step', string='Working Steps'),
        'company_id': fields.related('order_id','company_id',type='many2one',relation='res.company',string='Company'),
        'create_uid': fields.many2one('res.users','Creator',readonly=True),
        'create_date': fields.datetime('Creation Date', readonly=True),        
        'state': fields.selection([('draft','Draft'),('ready','Ready'),('confirmed','Confirmed'),('approved','Approved'),('rejected','Rejected'),('cancel','Cancelled')], 'Status', required=True, readonly=True),
        #order fields to show in the drawing files view
        'sale_product_ids': fields.related('order_id','sale_product_ids',type='many2many',relation='sale.product',rel='drawing_order_id_rel',id1='drawing_order_id',id2='id_id',
                                             string="MFG IDs",readonly=True, states={'draft':[('readonly',False)],'rejected':[('readonly',False)]}),
        'main_part_id': fields.related('order_id','main_part_id',type='many2one',relation='product.product',string='Main Product'),
        #+++ HoangTK - 11/17/2015: Add quantity and work steps to drawing order lines
        'name': fields.related('product_id','name',string="Name",type="string",readonly=True),
        'bom_qty': fields.integer('BOM Qty',readonly=True),
        'P_prepare_qty': fields.integer('P P',readonly=True),
        'P_done_qty': fields.integer('P D'),
        'P_need_qty': fields.integer('P N',readonly=True),
        'Fc_prepare_qty': fields.integer('Fc P',readonly=True),
        'Fc_done_qty': fields.integer('Fc D'),
        'Fc_need_qty': fields.integer('Fc N',readonly=True),
        'B_prepare_qty': fields.integer('B P',readonly=True),
        'B_done_qty': fields.integer('B D'),
        'B_need_qty': fields.integer('B N',readonly=True),
        'Ma_prepare_qty': fields.integer('Ma P',readonly=True),
        'Ma_done_qty': fields.integer('Ma D'),
        'Ma_need_qty': fields.integer('Ma N',readonly=True),
        'D_prepare_qty': fields.integer('D P',readonly=True),
        'D_done_qty': fields.integer('D D'),
        'D_need_qty': fields.integer('D N',readonly=True),
        'Mi_prepare_qty': fields.integer('Mi P',readonly=True),
        'Mi_done_qty': fields.integer('Mi D'),
        'Mi_need_qty': fields.integer('Mi N',readonly=True),
        'W_prepare_qty': fields.integer('W P',readonly=True),
        'W_done_qty': fields.integer('W D'),
        'W_need_qty': fields.integer('W N',readonly=True),
        'A_prepare_qty': fields.integer('A P',readonly=True),
        'A_done_qty': fields.integer('A D'),
        'A_need_qty': fields.integer('A N',readonly=True),
        'Ct_prepare_qty': fields.integer('Ct P',readonly=True),
        'Ct_done_qty': fields.integer('Ct D'),
        'Ct_need_qty': fields.integer('Ct N',readonly=True),
        'Bt_prepare_qty': fields.integer('Bt P',readonly=True),
        'Bt_done_qty': fields.integer('Bt D'),
        'Bt_need_qty': fields.integer('Bt N',readonly=True),
        'Ps_prepare_qty': fields.integer('Ps P',readonly=True),
        'Ps_done_qty': fields.integer('Ps D'),
        'Ps_need_qty': fields.integer('Ps N',readonly=True),
        'G_prepare_qty': fields.integer('G P',readonly=True),
        'G_done_qty': fields.integer('G D'),
        'G_need_qty': fields.integer('G N',readonly=True),
        'work_steps': fields.char('Work Steps',size=128,readonly=True),
        'last_step': fields.char('Last Step',size=128,readonly=True),
        'first_step': fields.char('Last Step',size=128,readonly=True),  
        'status': fields.char('Status',size=50,readonly=True),
        'part_type': fields.selection(PART_TYPE_SELECTION,string='Part Type'),
        #--- HoangTK - 11/17/2015     
    }
    
    _defaults = {
        'state': 'draft',
    }
   
    def _format_file_name(self, file_name):
        file_reserved_char = ('/','\\','<','>','*','?')
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
                    attach_file = attachment_obj.file_get(cr, uid, file_ids[0],context=context)
                    input = PdfFileReader(attach_file)
                    for page in input.pages: 
                        output.addPage(page)
                        page_cnt += 1
        if page_cnt > 0:
            #+++ HoangTK - 12/10/2015: Use system temp file
            file_name = "Drawing"
            if context.get('order_name'):
                file_name = '%s-%s'%(file_name, self._format_file_name(context.get('order_name')))            
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
            #--- HoangTK - 12/10/2015: Use system temp file
            #TODO: Return file direct to user not user file.down because of memory limit
            #+++ HoangTK - 12/10/2015: Replace print_pdf to fix memory error when pdf is too large
            return {
                    'type' : 'ir.actions.act_url',
                    #'url': '/web/export/print_pdf?filename=%s&filedata=%s'%(file_name, filedata),
                    'url': '/web/export/drawing_order_print_pdf?file_name=%s&file_data=%s'%(file_name, temp_drawing_pdf_file_name),
                    'target': 'self', 
                    }       
            
            #return self.pool.get('file.down').download_data(cr, uid, "%s.pdf"%(file_name,), filedata, context)
            #--- HoangTK - 12/10/2015: Replace print_pdf to fix memory error when pdf is too large
        else:
            raise osv.except_osv(_("Error!"),_('No PDF files were found!'))
            return False
        
    def unlink(self, cr, uid, ids, context=None):
        #delete the attachments
        for id in ids:
            utils.field_set_file(self, cr, uid, id, 'drawing_file', None, {'unlink':True}, context=None)
        resu = super(drawing_order_line, self).unlink(cr, uid, ids, context=context)
        return resu

    def _check_file_name(self,cr,uid,ids,context=None):
        for record in self.browse(cr, uid, ids, context=context):
            #+++ HoangTK - 11/18/2015: Allow file name is null
            if not record.drawing_file_name:
                continue
            #--- HoangTK - 11/18/2015
            same_file_name_ids = self.search(cr, uid, [('order_id','=',record.order_id.id),('id','!=',record.id),('drawing_file_name','=',record.drawing_file_name)],context=context)
            if same_file_name_ids:
                #+++ HoangTK - 11/18/2015: Fix bug file_name not found in drawing_order_line 
                #raise osv.except_osv(_('Error'), _('Drawring file "%s" is duplicated under same order!')% (record.file_name,))
                raise osv.except_osv(_('Error'), _('Drawing file "%s" is duplicated under same order!')% (record.drawing_file_name,))
                #--- HoangTK - 11/18/2015
            
        return True
    
    _constraints = [
        (_check_file_name,
            'Drawing file name is duplicated under same order!',
            ['file_name'])
        ]

    def copy_data(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}
        line_data = self.browse(cr,uid,id,context=context)
        default.update({
            'drawing_file':line_data.drawing_file
        })
                
        return super(drawing_order_line, self).copy_data(cr, uid, id, default, context)
    #+++ HoangTK - 12/08/2015: Override write method to update drawing order quantity
    def write(self, cr, uid, ids, vals, context=None):
        if not isinstance(ids, list):
            ids = [ids]
        result = super(drawing_order_line,self).write(cr, uid, ids, vals, context=context)
        order_line_vals = self.read(cr, uid, ids, ['order_id'])
        drawing_ids = []
        for value in order_line_vals:
            if value['order_id'][0] not in drawing_ids:
                drawing_ids.append(value['order_id'][0])
        drawing_order_obj = self.pool.get('drawing.order')
        drawing_order_obj.update_qty(cr, uid, drawing_ids)
        return result    
    #--- HoangTK - 12/08/2015: Override write method to update drawing order quantity            