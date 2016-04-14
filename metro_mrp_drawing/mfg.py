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
def ceiling(f, r):
    if not r:
        return f
    return tools.float_round(f, precision_rounding=r, rounding_method='UP')
class project_task_modifyhistory(osv.osv):
    _name = "project.task.modifyhistory"
    _description = "Project Task Modify History"
    _columns = {
        'date': fields.datetime('Modified Date',readonly=True),
        'task_id': fields.many2one('project.task','Project Task',readonly=True),
        'user_id': fields.many2one('res.users','User',readonly=True),
        'content': fields.char('Content',readonly=True),
        'vals': fields.char('Update Values',readonly=True,size=256),
    }
project_task_modifyhistory()
class project_task_completion(osv.osv):
    _name = "project.task.completion"
    _description = "Project Task Completion"
    def _get_total_qty(self, cr, uid, ids, name, arg, context=None):
        result = {}
        for completion in self.browse(cr, uid, ids):
            total = 0
            for line in completion.completion_lines:
                total = total + line.done_qty
            result[completion.id] = total
        return result
    _columns = {
        'name': fields.char('Name',type="char",size=128,readonly=True),
        'task_id': fields.many2one('project.task','Task',ondelete="cascade",required=True,states={'draft': [('readonly', False)]},readonly=True),
        'date': fields.date('Date',required=True,states={'draft': [('readonly', False)]},readonly=True),
        'dept_id': fields.many2one('hr.department','Team',required=True,states={'draft': [('readonly', False)]},readonly=True),
        'big_subassembly_id': fields.many2one('product.product','Big Sub Assembly',required=True,states={'draft': [('readonly', False)]},readonly=True),
        'mo_id': fields.many2one('mrp.production','Manufacturer Order',required=True,states={'draft': [('readonly', False)]},readonly=True),
        'completion_lines': fields.one2many('project.task.completion.line','completion_id',string='Completion Lines',states={'draft': [('readonly', False)]},readonly=True),
        'total_qty': fields.function(_get_total_qty,method=True,type="integer",string='Total Quantity',readonly=True),
        'date_create': fields.datetime('Create Date',readonly=True),
        'user_id': fields.many2one('res.users','Create User',readonly=True),
        'state': fields.selection([('draft','Draft'),
                                   ('confirmed','Confirm'),
                                   ('cancelled','Cancelled')],string='State',readonly=True)
    }
    _sql_constraints = [
        ('task_id_date_uniq', 'unique(task_id,date)', _('You are not allow to create 2 dispatch for a task in one day!')),
    ]
    def _check_duplicate_completion(self, cr, uid, ids, context=None):
        for completion in  self.browse(cr, uid, ids):
            duplicate_ids = self.search(cr, uid, [
                ('task_id','=',completion.task_id.id),
                ('date','=',completion.date)
            ])
            if len(duplicate_ids) >= 2:
                return False
        return True
    _constraints = [
        (_check_duplicate_completion, _('You are not allow to create 2 dispatch for a task in one day!'), ['task_id','date']),
        ]

    def unlink(self, cr, uid, ids, context=None):
        confirmed_ids = self.search(cr, uid, [('id','in',ids),
                                             ('state','=','confirmed')])
        if len(confirmed_ids) > 0:
            raise osv.except_osv(_('Error!'), _('Can not delete confirmed task completions !'))
            return False
        return super(project_task_completion,self).unlink(cr, uid, ids, context=context)
    def onchange_mo_dept_big_subassembly(self, cr, uid, ids, mo_id, dept_id, big_subassembly_id, context=None):
        values = {}
        if mo_id and dept_id and big_subassembly_id:
            project_task_obj = self.pool.get('project.task')
            task_ids = project_task_obj.search(cr, uid, [('production_id','=',mo_id),
                                                         ('dept_id','=',dept_id),
                                                         ('big_subassembly_id','=',big_subassembly_id)])
            if task_ids:
                task = project_task_obj.browse(cr, uid, task_ids[0])
                values.update({'task_id': task_ids[0],'name': '%s-%s-%s'%(task.production_id.name,
                                                                          task.dept_id.name,
                                                                          task.big_subassembly_id.name)})
        return {'value': values}
    def onchange_task_id(self, cr, uid, ids, task_id, context=None):
        task_obj = self.pool.get('project.task')
        task_line_obj = self.pool.get('project.task.line')
        task_completion_line_obj = self.pool.get('project.task.completion.line')
        task = task_obj.browse(cr, uid, task_id)
        completion_line_ids = []
        if task:
            old_completion_line_ids = task_completion_line_obj.search(cr, uid, [('completion_id','in',ids)])
            task_completion_line_obj.unlink(cr, uid, old_completion_line_ids)
            task_line_ids  = task_line_obj.search(cr, uid, [('task_id','=',task.id),
                                                            ('need_qty','>',0)],order="sequence asc")
            sequence = 1
            for line in task_line_obj.browse(cr, uid, task_line_ids):
                vals = {
                    'sequence': sequence,
                    'task_line_id': line.id,
                    'item_no': line.item_no,
                    'product_id': line.product_id.id,
                    'task_done_qty': line.done_qty,
                    'task_need_qty': line.need_qty,
                    'task_prepare_qty': line.prepare_qty,
                    'need_qty': line.need_qty - line.done_qty,
                    'prepare_qty': line.prepare_qty - line.done_qty,
                    'done_qty': 0,
                }
                #completion_line_id = task_completion_line_obj.create(cr, uid, vals)
                #completion_line_ids.append(completion_line_id)
                completion_line_ids.append(vals)
                sequence = sequence + 1
        return {'value': {'completion_lines': completion_line_ids}}

    def _set_state(self,cr,uid,ids,state,context=None):
        self.write(cr,uid,ids,{'state':state},context=context)

    def update_quantity_to_task(self,cr, uid, ids, context=None):
        task_line_obj = self.pool.get('project.task.line')
        project_task_obj = self.pool.get('project.task')
        updated_task_line_ids = []
        updated_task_ids = []
        for completion in self.browse(cr, uid, ids):
            for line in completion.completion_lines:
                new_done_qty = line.done_qty + line.task_done_qty
                if new_done_qty > line.task_prepare_qty or new_done_qty > line.task_need_qty:
                    raise osv.except_osv(_('Error!'), _('%s : done quantity is not correct !')%(line.product_id.name,))
                    return False
                task_line_obj.write(cr, uid, [line.task_line_id.id],{
                    'done_qty': new_done_qty,
                })
                updated_task_line_ids.append(line.task_line_id.id)
            updated_task_ids.append(completion.task_id.id)
        project_task_obj.move_part_when_task_line_updated(cr, uid, updated_task_ids, updated_task_line_ids)
        return True
    def cancel_quantity_to_task(self, cr, uid, ids, context=None):
        return True
    def action_confirm(self, cr, uid, ids, context=None):
        for completion in self.browse(cr, uid, ids, context=context):
            if completion.task_id.state in ['draft','cancelled','done']:
                raise osv.except_osv(_('Error!'), _('Can not confirm! Task is not in working states!'))
                return False
        #Update done quantity to project task
        result = self.update_quantity_to_task(cr, uid, ids, context=context)
        if not result:
            raise osv.except_osv(_('Error!'), _('Can not confirm task completion!'))
            return False
        self._set_state(cr, uid, ids, 'confirmed',context)
        return True
    def action_cancel(self, cr, uid, ids, context=None):
        result = self.cancel_quantity_to_task(cr, uid, ids, context=context)
        if not result:
            raise osv.except_osv(_('Error!'), _('Can not cancel task completion!'))
            return False
        self._set_state(cr, uid, ids, 'cancelled',context)
        return True

    def action_draft(self, cr, uid, ids, context=None):
        self._set_state(cr, uid, ids, 'draft',context)
        return True

    _defaults = {
        'state': 'draft',
        'date': fields.date.context_today,
        'date_create': lambda *a: datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
        'user_id': lambda obj, cr, uid, context: uid,
    }
project_task_completion()
class project_task_completion_line(osv.osv):
    _name = "project.task.completion.line"
    _description = "Project Task Completion Line"
    def _get_remain_need_qty(self, cr, uid, ids, name, args, context=None):
        result = {}
        for line in self.browse(cr, uid, ids):
            result[line.id] = 0
            if line.task_line_id:
                result[line.id] = line.task_need_qty - line.task_done_qty
        return result
    def _get_remain_prepare_qty(self, cr, uid, ids, name, args, context=None):
        result = {}
        for line in self.browse(cr, uid, ids):
            result[line.id] = 0
            if line.task_line_id:
                result[line.id] = line.task_prepare_qty - line.task_done_qty
        return result
    _columns = {
        'sequence': fields.integer('Sequence',readonly=True),
        'completion_id': fields.many2one('project.task.completion','Task Compeltion',readonly=True),
        'task_line_id': fields.many2one('project.task.line',readonly=True),
        'item_no': fields.related('task_line_id','item_no',type='char',size=50,string='Item No.',store=True,readonly=True),
        'product_id': fields.related('task_line_id','product_id',type='many2one', relation='product.product',string='Product',readonly=True),
        'task_done_qty':fields.related('task_line_id','done_qty',type='integer',string='Total Done Quantity',readonly=True),
        'task_need_qty':fields.related('task_line_id','need_qty',type='integer',string='Total Need Quantity',readonly=True),
        'task_prepare_qty':fields.related('task_line_id','prepare_qty',type='integer',string='Total Prepare Quantity',readonly=True),
        'done_qty': fields.integer('Done Quantity'),
        'need_qty': fields.function(_get_remain_need_qty, string='Remain Need Quantity', type="integer",method=True,readonly=True),
        'prepare_qty': fields.function(_get_remain_prepare_qty,string='Remain Prepare Quantity', type="integer",method=True,readonly=True)
    }
    def write(self, cr, uid, ids, vals, context=None):
        if 'done_qty' in vals:
            for line in self.browse(cr, uid, ids):
                if vals['done_qty'] > line.need_qty:
                    raise osv.except_osv(_('Error!'), _('%s : done quantity must <= need quantity!')%(line.product_id.name,))
                    return False
        result = super(project_task_completion_line,self).write(cr, uid, ids, vals, context=context)
        return result
project_task_completion_line()
class project_task_line(osv.osv):
    _name = "project.task.line"
    _description = "Project Task Line"
    _columns = {
                'sequence': fields.integer('Sequence',readonly=True),
                'order_line_id': fields.many2one('drawing.order.line','Drawing Order Line',readonly=True),
                'drawing_file_name': fields.related('order_line_id','drawing_file_name',string='Drawing PDF Name', type='char', size=64, readonly=True),
                'drawing_file': fields.related('order_line_id','drawing_file', string="Drawing PDF", type="binary",readonly=True),
                'item_no': fields.char('Item No.',size=50,readonly=True),
                'task_id': fields.many2one('project.task','Task',ondelete="cascade"),
                'product_id': fields.many2one('product.product','Product'),
                'prepare_qty': fields.integer('Prepare Qty',readonly=True),
                'done_qty': fields.integer('Done Qty'),
                'need_qty': fields.integer('Need Qty',readonly=True),
                'next_step': fields.char('Next Step',size=128,readonly=True),
                'state': fields.selection([('created','Created'),
                                            ('on_working','On Working'),
                                            ('done','Done')],string='State',readonly=True),
                }
    def write(self, cr, uid, ids, vals, context=None):
        if 'done_qty' in vals:
            for line in self.browse(cr, uid, ids):
                if vals['done_qty'] > line.need_qty:
                    raise osv.except_osv(_('Error!'), _('%s : done quantity must <= need quantity!')%(line.product_id.name,))
                    return False
        if 'prepare_qty' in vals:
            for line in self.browse(cr, uid, ids):
                if vals['prepare_qty'] < line.done_qty:
                    raise osv.except_osv(_('Error!'), _('%s : prepare quantity must >= done quantity!')%(line.product_id.name, ))
                    return False
        result = super(project_task_line,self).write(cr, uid, ids, vals, context=context)
        for line in self.browse(cr, uid, ids):
            if line.need_qty > 0:
                if line.done_qty == line.need_qty:
                    super(project_task_line,self).write(cr, uid, [line.id], {'state': 'done'}, context=context)
                elif line.task_id.state not in ['draft','cancelled','done']:
                    super(project_task_line,self).write(cr, uid, [line.id], {'state': 'on_working'}, context=context)
                else:
                    super(project_task_line,self).write(cr, uid, [line.id], {'state': ''}, context=context)
        return result
    _defaults = {
        'sequence': 0,
                }
    _order = "sequence"
project_task_line()
def rounding(f, r):
    import math
    if not r:
        return f
    return math.ceil(f / r) * r
class mrp_bom(osv.osv):
    _name = 'mrp.bom'
    _inherit = 'mrp.bom'
    def _bom_explode_an_assembly(self, cr, uid, bom, factor, properties=None, addthis=False, level=0, routing_id=False,assembly_id = False):
        """ Finds Products and Work Centers for related BoM for manufacturing order.
        @param bom: BoM of particular product.
        @param factor: Factor of product UoM.
        @param properties: A List of properties Ids.
        @param addthis: If BoM found then True else False.
        @param level: Depth level to find BoM lines starts from 10.
        @return: result: List of dictionaries containing product details.
                 result2: List of dictionaries containing Work Center details.
        """
        routing_obj = self.pool.get('mrp.routing')
        factor = factor / (bom.product_efficiency or 1.0)
        factor = rounding(factor, bom.product_rounding)
        if factor < bom.product_rounding:
            factor = bom.product_rounding
        result = []
        result2 = []
        phantom = False
        if bom.type == 'phantom' and not bom.bom_lines:
            newbom = self._bom_find(cr, uid, bom.product_id.id, bom.product_uom.id, properties)

            if newbom:
                res = self._bom_explode(cr, uid, self.browse(cr, uid, [newbom])[0], factor*bom.product_qty, properties, addthis=True, level=level+10)
                result = result + res[0]
                result2 = result2 + res[1]
                phantom = True
            else:
                phantom = False
        if not phantom:
            if addthis and not bom.bom_lines:
                result.append(
                {
                    'name': bom.product_id.name,
                    'product_id': bom.product_id.id,
                    'product_qty': bom.product_qty * factor,
                    'product_uom': bom.product_uom.id,
                    'product_uos_qty': bom.product_uos and bom.product_uos_qty * factor or False,
                    'product_uos': bom.product_uos and bom.product_uos.id or False,
                })
            routing = (routing_id and routing_obj.browse(cr, uid, routing_id)) or bom.routing_id or False
            if routing:
                for wc_use in routing.workcenter_lines:
                    wc = wc_use.workcenter_id
                    d, m = divmod(factor, wc_use.workcenter_id.capacity_per_cycle)
                    mult = (d + (m and 1.0 or 0.0))
                    cycle = mult * wc_use.cycle_nbr
                    result2.append({
                        'name': tools.ustr(wc_use.name) + ' - '  + tools.ustr(bom.product_id.name),
                        'workcenter_id': wc.id,
                        'sequence': level+(wc_use.sequence or 0),
                        'cycle': cycle,
                        'hour': float(wc_use.hour_nbr*mult + ((wc.time_start or 0.0)+(wc.time_stop or 0.0)+cycle*(wc.time_cycle or 0.0)) * (wc.time_efficiency or 1.0)),
                    })
            for bom2 in bom.bom_lines:
                if bom2.product_id.id == assembly_id:
                    res = self._bom_explode(cr, uid, bom2, factor, properties, addthis=True, level=level+10)
                    result = result + res[0]
                    result2 = result2 + res[1]
        return result, result2
mrp_bom()
class mrp_production(osv.osv):
    _inherit = 'mrp.production'
    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        if view_type == 'form' and not view_id:
            view_name = 'metro_mrp_production_with_drawing_order_form_view'
            view_obj = self.pool.get('ir.ui.view')
            view_ids = view_obj.search(cr, uid, [('name','=',view_name)])
            if view_ids:
                view = view_obj.browse(cr, uid, view_ids[0])
                department_obj = self.pool.get('hr.department')
                department_ids = department_obj.search(cr, uid, [('code','in',WORK_STEP_LIST)],order = 'sequence asc')
                departments = department_obj.browse(cr, uid, department_ids)
                work_step_fields = ''
                for department in departments:
                    work_step_fields = work_step_fields + \
                                       "<field name='%s_prepare_qty' attrs=\"{'invisible':[('%s_prepare_qty', '==', 0)]}\" readonly='1'/> \
                                       <field name='%s_done_qty' attrs=\"{'invisible':[('%s_done_qty', '==', 0)]}\" readonly='1'/> \
                                       <field name='%s_need_qty' attrs=\"{'invisible':[('%s_need_qty', '==', 0)]}\" readonly='1'/>" % (department.code,department.code,department.code,department.code,department.code,department.code)
                arch_parts = view.arch.split('<!--DYNAMIC WORKSTEPS DO NOT DELETE-->')
                if len(arch_parts) == 3:
                    view_arch = arch_parts[0] + '<!--DYNAMIC WORKSTEPS DO NOT DELETE-->' + \
                                work_step_fields + '<!--DYNAMIC WORKSTEPS DO NOT DELETE-->' + \
                                arch_parts[2]
                    view_obj.write(cr, SUPERUSER_ID, [view_ids[0]],{
                        'arch': view_arch
                    })
        res = super(mrp_production,self).fields_view_get(cr,uid,view_id,view_type,context,toolbar,submenu)
        return res
    def action_drawing_order_generate(self, cr, uid, ids, properties=None, context=None):
        drawing_order_obj = self.pool.get('drawing.order')
        for mo in self.browse(cr, uid, ids):
            #Remove all drawing orders of this mo
            old_drawing_order_ids = drawing_order_obj.search(cr, uid,[
                                                                      ('mo_id','=',mo.id)
                                                                      ])
            drawing_order_obj.unlink(cr, uid, old_drawing_order_ids)
            mfg_ids = []
            for mfg_id in mo.mfg_ids:
                mfg_ids.append("ID" + str(mfg_id.name))
            mfg_name = "_".join(mfg_ids)
            for bom_line in mo.bom_id.bom_lines:
                drawing_order_name = bom_line.product_id.name
                if mfg_name:
                    drawing_order_name += "-" + mfg_name
                drawing_order_vals = {  'mo_id': mo.id,
                                        'product_id' : bom_line.product_id.id,
                                        'name':drawing_order_name,
                                        'state': 'draft',
                                        'bom_file_name': False}
                drawing_order_obj.create(cr, uid, drawing_order_vals)
        return True
    def action_compute_an_assembly(self, cr, uid, ids, properties=None, context=None, assembly_id=False):
        """ Computes bills of material of a product.
        @param properties: List containing dictionaries of properties.
        @return: No. of products.
        """
        if properties is None:
            properties = []
        results = []
        bom_obj = self.pool.get('mrp.bom')
        uom_obj = self.pool.get('product.uom')
        prod_line_obj = self.pool.get('mrp.production.product.line')
        workcenter_line_obj = self.pool.get('mrp.production.workcenter.line')
        for production in self.browse(cr, uid, ids):
            #cr.execute('delete from mrp_production_product_line where production_id=%s', (production.id,))
            #cr.execute('delete from mrp_production_workcenter_line where production_id=%s', (production.id,))
            bom_point = production.bom_id
            bom_id = production.bom_id.id
            if not bom_point:
                bom_id = bom_obj._bom_find(cr, uid, production.product_id.id, production.product_uom.id, properties)
                if bom_id:
                    bom_point = bom_obj.browse(cr, uid, bom_id)
                    routing_id = bom_point.routing_id.id or False
                    self.write(cr, uid, [production.id], {'bom_id': bom_id, 'routing_id': routing_id})

            if not bom_id:
                raise osv.except_osv(_('Error!'), _("Cannot find a bill of material for this product."))
            factor = uom_obj._compute_qty(cr, uid, production.product_uom.id, production.product_qty, bom_point.product_uom.id)
            res = bom_obj._bom_explode_an_assembly(cr, uid, bom_point, factor / bom_point.product_qty, properties, routing_id=production.routing_id.id,assembly_id = assembly_id)
            results = res[0]
            results2 = res[1]
            for line in results:
                line['production_id'] = production.id
                prod_line_obj.create(cr, uid, line)
            for line in results2:
                line['production_id'] = production.id
                workcenter_line_obj.create(cr, uid, line)
        return len(results)

    def action_compute(self, cr, uid, ids, properties=None, context=None):
        result = super(mrp_production,self).action_compute(cr, uid, ids, properties, context)
        drawing_order_obj = self.pool.get('drawing.order')
        drawing_order_line_obj = self.pool.get('drawing.order.line')
        workcenter_line_obj = self.pool.get('mrp.production.workcenter.line')
        project_task_obj = self.pool.get('project.task')
        project_task_line_obj = self.pool.get('project.task.line')
        dept_obj = self.pool.get('hr.department')
        project_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'metro_project', 'project_mfg')[1]

        for mo in self.browse(cr, uid ,ids):
            #Remove work order not has sub assembly not in drawing order list
            remove_workcenter_line_ids = []
            duplicate_task_ids = []
            for line in mo.workcenter_lines:
                remove_task_ids = []
                big_subassembly_id = line.bom_id.product_id.id
                drawing_order_ids = drawing_order_obj.search(cr, uid, [
                                                                       ('mo_id','=',mo.id),
                                                                       ('product_id','=',big_subassembly_id)
                                                                       ])
                if not drawing_order_ids:
                    remove_workcenter_line_ids.append(line.id)
                    continue
                #Remove task not in drawing order line work steps
                all_drawing_steps = []
                all_steps = {}
                drawing_order = drawing_order_obj.browse(cr, uid, drawing_order_ids[0])
                for order_line in drawing_order.order_lines:
                    steps = drawing_order_obj._split_work_steps(order_line.work_steps)
                    for step in steps:
                        if not step in all_steps:
                            all_drawing_steps.append(step)
                            all_steps.update({step: True})
                remove_task_ids = project_task_obj.search(cr, uid,[
                                                               ('workorder_id','=',line.id),
                                                               ('dept_code','not in',all_drawing_steps)
                                                               ] )
                project_task_obj.unlink(cr, uid, remove_task_ids)
                #Create task that have in work steps but not in project task
                for step in all_drawing_steps:
                    step_task_ids = project_task_obj.search(cr, uid, [
                                                                      ('workorder_id','=',line.id),
                                                                      ('dept_code','=',step),
                                                                      ])
                    if not step_task_ids:
                        dept_ids = dept_obj.search(cr, uid, [
                                                             ('code','=',step)
                                                             ])
                        if dept_ids:
                            dept = dept_obj.browse(cr, uid, dept_ids[0])
                            task_vals = {
                                     'name': dept.name,
                                     'workorder_id': line.id,
                                     'user_id': uid,
                                     'dept_id': dept.id,
                                     'dept_mgr_id': dept.manager_id.id,
                                     'drawing_order_id': drawing_order.id,
                                     'project_id': project_id,
                                     }
                            task_id = project_task_obj.create(cr, uid, task_vals)
                    elif len(step_task_ids) > 1:
                        for i in range(1,len(step_task_ids)):
                            duplicate_task_ids.append(step_task_ids[i])
                #Update status all steps in part to Created
                for order_line in drawing_order.order_lines:
                    order_vals = {}
                    steps = drawing_order_obj._split_work_steps(order_line.work_steps)
                    order_vals.update({'status': 'Created'})
                    drawing_order_line_obj.write(cr, uid, [order_line.id], order_vals)
            project_task_obj.unlink(cr, uid, duplicate_task_ids)
            workcenter_line_obj.unlink(cr, uid, remove_workcenter_line_ids)
            #Add product and qty to task
            for line in mo.workcenter_lines:
                for task_id in line.task_ids:
                    prepare_qty = 0
                    need_qty = 0
                    sequence = 1
                    drawing_order_line_ids = []
                    for order_line in task_id.drawing_order_lines:
                        drawing_order_line_ids.append(order_line.id)
                    drawing_order_line_ids = drawing_order_line_obj.search(cr, uid, [
                        ('id','in',drawing_order_line_ids)
                    ],order = 'item_no asc')
                    for order_line in drawing_order_line_obj.browse(cr, uid, drawing_order_line_ids):
                        steps = drawing_order_obj._split_work_steps(order_line.work_steps)
                        if task_id.dept_code not in steps:
                            continue
                        task_line_vals = {
                                            'task_id': task_id.id,
                                            'order_line_id': order_line.id,
                                            'product_id': order_line.product_id.id,
                                            'prepare_qty': 0,
                                            'done_qty': 0,
                                            'need_qty': 0,
                                            'next_step': '',
                                            'sequence': sequence,
                                            'item_no': order_line.item_no,
                                            'prepare_qty': getattr(order_line,"%s_prepare_qty" % task_id.dept_code, 0),
                                            'done_qty': getattr(order_line,"%s_done_qty" % task_id.dept_code, 0),
                                            'need_qty': getattr(order_line,"%s_need_qty" % task_id.dept_code, 0),
                                        }
                        sequence = sequence + 1
                        prepare_qty += getattr(order_line,"%s_prepare_qty" % task_id.dept_code, 0)
                        need_qty += getattr(order_line,"%s_prepare_qty" % task_id.dept_code, 0)
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
        return result
class project_task(osv.osv):
    _inherit = "project.task"
    _name = "project.task"
    _order = "priority asc, sequence asc, production_id desc"
    def _hours_get(self, cr, uid, ids, field_names, args, context=None):
        res = super(project_task,self)._hours_get(cr, uid, ids, field_names, args, context=context)
        for task in self.browse(cr, uid, ids, context=context):
            if task.project_type == 'mfg' and task.need_qty > 0 :
                res[task.id]['progress'] = task.done_qty * 100.0 / task.need_qty
        return res
    def _get_task(self, cr, uid, ids, context=None):
        return super(project_task,self)._get_task(cr, uid, ids, context=context)
    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        if view_type == 'form' and not view_id:
            view_name = 'project_task_with_drawing_mfg_form_view'
            view_obj = self.pool.get('ir.ui.view')
            view_ids = view_obj.search(cr, uid, [('name','=',view_name)])
            if view_ids:
                view = view_obj.browse(cr, uid, view_ids[0])
                department_obj = self.pool.get('hr.department')
                department_ids = department_obj.search(cr, uid, [('code','in',WORK_STEP_LIST)],order = 'sequence asc')
                departments = department_obj.browse(cr, uid, department_ids)
                work_step_fields = ''
                for department in departments:
                    work_step_fields = work_step_fields + \
                                       "<field name='%s_prepare_qty' class='metro_high_light' attrs=\"{'invisible':[('%s_prepare_qty', '==', 0)],'readonly': True}\"/> \
                                       <field name='%s_done_qty' class='metro_high_light' attrs=\"{'invisible':[('%s_need_qty', '==', 0)],'readonly': True}\"/> \
                                       <field name='%s_need_qty' class='metro_high_light' attrs=\"{'invisible':[('%s_need_qty', '==', 0)],'readonly': True}\"/>" % (department.code,department.code,department.code,department.code,department.code,department.code)
                arch_parts = view.arch.split('<!--DYNAMIC WORKSTEPS DO NOT DELETE-->')
                if len(arch_parts) == 3:
                    view_arch = arch_parts[0] + '<!--DYNAMIC WORKSTEPS DO NOT DELETE-->' + \
                                work_step_fields + '<!--DYNAMIC WORKSTEPS DO NOT DELETE-->' + \
                                arch_parts[2]
                view_obj.write(cr, SUPERUSER_ID, [view_ids[0]],{
                    'arch': view_arch
                })
        res = super(project_task,self).fields_view_get(cr,uid,view_id,view_type,context,toolbar,submenu)
        return res
    _columns = {
            'date_issued': fields.date('Date Issued'),
            'drawing_order_id': fields.many2one('drawing.order', "Drawing Order",readonly=True),
            'prepare_qty': fields.integer('Prepare Quantity',readonly=True),
            'done_qty': fields.integer('Done Quantity',readonly=True),
            'need_qty': fields.integer('Need Quantity',readonly=True),
            'drawing_order_lines': fields.related('drawing_order_id','order_lines',type="one2many",relation="drawing.order.line",string="Drawing Order Lines",readonly=True),
            'big_subassembly_id': fields.related('workorder_id','big_subassembly_id',type='many2one',relation='product.product',string='Big Sub Assembly',readonly=True),
            'dept_code': fields.related('dept_id','code',type="char",size=10,readonly=True),
            'task_lines': fields.one2many('project.task.line','task_id',string='Task Lines',readonly=True),
            'completion_ids': fields.one2many('project.task.completion','task_id',string='Task Completion',readonly=True),
            'progress': fields.function(_hours_get, string='Progress (%)', multi='hours', group_operator="avg", help="If the task has a progress of 99.99% you should close the task if it's finished or reevaluate the time",
                store = {
                    'project.task': (lambda self, cr, uid, ids, c={}: ids, ['work_ids', 'remaining_hours', 'planned_hours','state','done_qty','need_qty'], 10),
                    'project.task.work': (_get_task, ['hours'], 10),
                }),
            'modifyhistory_ids': fields.one2many('project.task.modifyhistory','task_id','Modify History',readonly=True)
            }
    def _email_notify_done(self, cr, uid, ids, group_params, context=None):
        task_ids = ', '.join(str(i) for i in ids)
        email_subject = "Manufacturing Tasks %s have completed" % (task_ids,)
        email_body = ""
        email_from = self.pool.get("res.users").read(cr, uid, uid, ['email'],context=context)['email']
        for group_param in group_params:
            email_group_id = self.pool.get('ir.config_parameter').get_param(cr, uid, group_param, context=context)
            if email_group_id:
                utils.email_send_group(cr, uid, email_from, None,email_subject,email_body, email_group_id, context=context)

    def do_close(self, cr, uid, ids, context=None):
        """ Compatibility when changing to case_close. """
        result = True
        #Check if all task lines finished ?
        task_line_obj = self.pool.get('project.task.line')
        task_line_ids = task_line_obj.search(cr, uid, [
                                                       ('task_id','in', ids),
                                                       ('need_qty','>',0),
                                                       ('state','!=','done'),
                                                       ])
        next_start_task_ids = []
        not_enough_prepare_qty_task_line_ids = []
        if task_line_ids:
            #Make part done if possible
            completion_obj = self.pool.get('project.task.completion')
            completion_line_obj = self.pool.get('project.task.completion.line')
            completion_for_task_ids = {}
            for task_line in task_line_obj.browse(cr, uid, task_line_ids):
                task_id = task_line.task_id
                if task_line.prepare_qty == 0 or task_line.done_qty > task_line.prepare_qty:
                    continue
                if task_line.prepare_qty != task_line.need_qty:
                    not_enough_prepare_qty_task_line_ids.append(task_line.id)
                if task_id.id not in completion_for_task_ids:
                    completion_id = completion_obj.create(cr, uid, {
                        'task_id': task_id.id,
                        'mo_id': task_id.production_id.id,
                        'big_subassembly_id': task_id.big_subassembly_id.id,
                        'dept_id': task_id.dept_id.id,
                    })
                    completion_for_task_ids.update({
                        task_id.id : {
                        'id': completion_id,
                        'completion_lines': [],
                        }
                    })
                completion_id = completion_for_task_ids[task_id.id]['id']
                completion_for_task_ids[task_id.id]['completion_lines'].append({
                    'completion_id': completion_id,
                    'task_line_id': task_line.id,
                    'sequence': len(completion_for_task_ids[task_id.id]['completion_lines'])+ 1,
                    'done_qty': task_line.prepare_qty - task_line.done_qty,
                })
            completion_ids = []
            for task_id in completion_for_task_ids:
                completion_ids.append(completion_for_task_ids[task_id]["id"])
                for completion_line in completion_for_task_ids[task_id]["completion_lines"]:
                    completion_line_obj.create(cr, uid, completion_line)
            completion_obj.action_confirm(cr, uid, completion_ids)
        if len(not_enough_prepare_qty_task_line_ids) > 0:
            result = self.pool.get('warning').info(cr, uid, title='Warning', message=_("Can not mark this task done. Some parts do not have enough prepare quantity!"))
        else:
            result = super(project_task,self).do_close(cr, uid, ids, context=context)
        #Send email to notify task is done
        self._email_notify_done(cr, uid, ids, ['group_mrp_supervisor'], context)
        return result
    def do_open(self, cr, uid, ids, context=None):
        """ Compatibility when changing to case_open. """
        result = super(project_task,self).do_open(cr, uid, ids, context=context)
        self.update_task_line_to_start(cr, uid, ids, context)
        return result
    def do_new_task_completion(self, cr, uid, ids, context=None):
        if 'default_task_id' in context and \
            'default_mo_id' in context and \
            'default_big_subassembly_id' in context and \
            'default_dept_id' in context:
            mod_obj = self.pool.get('ir.model.data')
            res = mod_obj.get_object_reference(cr, uid, 'metro_mrp_drawing', 'metro_project_task_completion_form_view')
            res_id = res and res[1] or False
            return {
                'name':'Task Done Quantity Update',
                'view_type':'form',
                'view_mode':'form',
                'res_model':'project.task.completion',
                'view_id':res_id,
                'type':'ir.actions.act_window',
                'target':'new',
                'context':context.copy(),
            }
        return True
    def update_task_line_to_start(self, cr, uid, ids, context=None):
        drawing_order_line_obj = self.pool.get('drawing.order.line')
        task_line_obj = self.pool.get('project.task.line')
        for task in self.browse(cr, uid, ids):
            if task.project_type == 'mfg':
                #Check if drawing order line is approved before continue
                #if task.drawing_order_id.state != 'approved':
                #    raise osv.except_osv(_('Error!'), _('Drawing order must be approved in order to start task!'))
                task_line_has_prepare_qty_ids = task_line_obj.search(cr, uid, [
                                                                               ('task_id','=',task.id),
                                                                               ('prepare_qty','!=',0),
                                                                               ])
                if len(task_line_has_prepare_qty_ids) == 0:
                    raise osv.except_osv(_('Error!'), _('Can not start task. Parts are not available yet!'))
                task_lines_ids = task_line_obj.search(cr, uid, [
                                                                ('task_id','=',task.id),
                                                                ('need_qty','>',0),
                                                                ('state','not in',['on_working','done'])
                                                                ])
                task_line_obj.write(cr, uid, task_lines_ids, {'state': 'on_working'})
                for order_line in task.drawing_order_lines:
                    drawing_order_line_obj.write(cr, uid, [order_line.id],{'status': _('On Working')})
        return True
    def _check_missed_dealine(self, cr, uid, ids=None, context=None):
        d = datetime.now().date()
        date_now = datetime.strftime(d, "%Y-%m-%d 00:00:00")
        miss_deadline_task_ids = self.search(cr, uid, [('date_deadline','<=',date_now),
                                    ('date_end','=',False),
                                    ('state','not in',['done','cancelled']),])
        if miss_deadline_task_ids:
            stage_obj = self.pool.get('project.task.type')
            stage_ids = stage_obj.search(cr, uid, [
                                                   ('name','=',_('Missed Deadline')),
                                                   ('project_type','=','mfg'),
                                                   ])
            if stage_ids:
                self.stage_set(cr, uid, miss_deadline_task_ids, stage_ids[0] , context=context)
        return True
    def _update_task_line_sequence(self, cr, uid, ids, context=None):
        for task in self.browse(cr, uid, ids,context=context):
            task_line_obj = self.pool.get('project.task.line')
            task_line_ids = task_line_obj.search(cr, uid, [
                ('task_id','=',task.id)
            ],order = 'need_qty desc, product_id asc')
            sequence = 1
            for line in task_line_obj.browse(cr, uid, task_line_ids):
                task_line_obj.write(cr, uid, [line.id],{
                    'sequence': sequence,
                })
                sequence = sequence + 1
        return True
    def move_part_when_task_line_updated(self, cr, uid, task_ids, update_task_line_ids, context=None):
        task_line_obj = self.pool.get('project.task.line')
        drawing_order_line_obj = self.pool.get('drawing.order.line')
        drawing_order_obj = self.pool.get('drawing.order')
        next_task_to_start_ids = []
        for task_line in task_line_obj.browse(cr, uid, update_task_line_ids):
            task = task_line.task_id
            dept_code = task.dept_code
            is_done = False
            product = task_line.product_id
            task_line_state = ''
            if task_line.need_qty > 0:
                if task_line.done_qty == task_line.need_qty:
                    is_done = True
                    task_line_state = 'done'
                elif task_line.task_id.state != 'draft':
                    task_line_state = 'on_working'
            task_line_obj.write(cr, uid, [task_line.id], {
                        'state': task_line_state,
            })
            drawing_order_line_ids = drawing_order_line_obj.search(cr, uid, [
                                                                             ('order_id','=',task.drawing_order_id.id),
                                                                             ('product_id','=',product.id)
                                                                             ])
            if drawing_order_line_ids:
                order_line = drawing_order_line_obj.browse(cr, uid, drawing_order_line_ids[0])
                order_line_vals = {}
                if dept_code == "P":
                    order_line_vals.update({'P_done_qty': task_line.done_qty})
                if dept_code == "Fc":
                    order_line_vals.update({'Fc_done_qty': task_line.done_qty})
                if dept_code == "B":
                    order_line_vals.update({'B_done_qty': task_line.done_qty})
                if dept_code == "Ma":
                    order_line_vals.update({'Ma_done_qty': task_line.done_qty})
                if dept_code == "D":
                    order_line_vals.update({'D_done_qty': task_line.done_qty})
                if dept_code == "Mi":
                    order_line_vals.update({'Mi_done_qty': task_line.done_qty})
                if dept_code == "W":
                    order_line_vals.update({'W_done_qty': task_line.done_qty})
                if dept_code == "A":
                    order_line_vals.update({'A_done_qty': task_line.done_qty})
                if dept_code == "Ct":
                    order_line_vals.update({'Ct_done_qty': task_line.done_qty})
                if dept_code == "Bt":
                    order_line_vals.update({'Bt_done_qty': task_line.done_qty})
                if dept_code == "Ps":
                    order_line_vals.update({'Ps_done_qty': task_line.done_qty})
                if dept_code == "G":
                    order_line_vals.update({'G_done_qty': task_line.done_qty})
                if dept_code == order_line.last_step and is_done:
                    order_line_vals.update({'status': _('Done')})
                elif dept_code != order_line.last_step:
                    steps = drawing_order_obj._split_work_steps(order_line.work_steps)
                    #Move parts
                    next_step = ""
                    for index, step in enumerate(steps):
                        if step == dept_code:
                            next_step = steps[index+1]
                            break
                    if next_step:
                        order_line_vals.update({
                                                next_step + '_prepare_qty': task_line.done_qty,
                                                })
                        #Find next step task line
                        next_task_ids = self.search(cr, uid, [
                                                              ('workorder_id','=',task.workorder_id.id),
                                                              ('dept_code','=',next_step)
                                                              ])
                        next_task_line_ids = task_line_obj.search(cr, uid, [
                                                                            ('task_id','in',next_task_ids),
                                                                            ('product_id','=',product.id)
                                                                            ])
                        if next_task_line_ids:
                            task_line_obj.write(cr, uid, next_task_line_ids,{
                                                                             'prepare_qty': task_line.done_qty
                                                                             })
                        if next_task_ids:
                            next_task_to_start_ids.extend(next_task_ids)
                drawing_order_line_obj.write(cr, uid, [order_line.id],order_line_vals)
        self.update_task_qty(cr, uid, task_ids + next_task_to_start_ids, open_task=True)
        self._check_missed_dealine(cr, uid, task_ids, context=context)
        return True
    def update_task_qty(self, cr, uid, ids, open_task= False, context=None):
        stage_obj = self.pool.get('project.task.type')
        done_task_to_finish_ids = []
        open_task_ids = []
        for task in self.browse(cr, uid, ids):
            prepare_qty = 0
            done_qty = 0
            need_qty = 0
            for task_line in task.task_lines:
                prepare_qty = prepare_qty + task_line.prepare_qty
                done_qty = done_qty + task_line.done_qty
                need_qty = need_qty + task_line.need_qty
            task_vals = {
                           'prepare_qty': prepare_qty,
                           'done_qty': done_qty,
                           'need_qty': need_qty,
                        }
            new_stage_id = False
            if need_qty > 0 and prepare_qty > 0:
                stage_ids = False
                if done_qty == 0:
                    stage_ids = stage_obj.search(cr, uid, [('name','=',_('Pending')),
                                                          ('project_type','=','mfg')])
                else:
                    stage_ids = stage_obj.search(cr, uid, [('name','=',_('In Progress')),
                                                          ('project_type','=','mfg')])
                if stage_ids:
                    new_stage_id = stage_ids[0]
            super(project_task,self).write(cr, uid, [task.id], task_vals)
            if new_stage_id:
                self.stage_set(cr, uid, [task.id], new_stage_id, context=context)
            if done_qty == need_qty and need_qty > 0:
                done_task_to_finish_ids.append(task.id)
            if open_task:
                if task.state == 'draft':
                    if task.prepare_qty > 0:
                        open_task_ids.append(task.id)
                elif task.state == 'done' and task.prepare_qty > task.done_qty:
                    open_task_ids.append(task.id)
        if done_task_to_finish_ids:
            super(project_task,self).do_close(cr, uid, done_task_to_finish_ids, context=context)
        if open_task_ids:
            self.do_open(cr, uid, open_task_ids, context=context)
        return True

    def write(self, cr, uid, ids, vals, context=None):
        """" Override write to check and move parts if finnish """
        result = super(project_task,self).write(cr, uid, ids, vals, context)
        update_task_lines = vals.get('task_lines',False)
        if update_task_lines:
            update_task_line_ids = []
            for update_task_line in update_task_lines:
                if update_task_line[2] and 'done_qty' in update_task_line[2]:
                    update_task_line_ids.append(update_task_line[1])
            self.move_part_when_task_line_updated(cr, uid, ids, update_task_line_ids, context=context)
        modifyhistory_obj = self.pool.get('project.task.modifyhistory')
        for task_id in ids:
            modifyhistory_obj.create(cr, uid, {
                'task_id': task_id,
                'user_id': uid,
                'date': datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                'content': _('Update Task'),
                'vals': '%s'%(vals),
            })
        return result
    def create(self, cr, uid, vals, context=None):
        result = super(project_task, self).create(cr, uid, vals, context)
        modifyhistory_obj = self.pool.get('project.task.modifyhistory')
        if result:
            modifyhistory_obj.create(cr, uid, {
                'task_id': result,
                'user_id': uid,
                'date': datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                'content': _('Create Task'),
                'vals' : '%s'%(vals),
            })
        return result
    def stage_set(self, cr, uid, ids, stage_id, context=None):
        value = {}
        if hasattr(self, 'onchange_stage_id'):
            value = self.onchange_stage_id(cr, uid, ids, stage_id, context=context)['value']
        value['stage_id'] = stage_id
        stage = self.pool.get('project.task.type').browse(cr, uid, stage_id)
        if stage:
            if stage.name == 'On Working':
                cr.execute('SELECT MIN(sequence) as sequence FROM project_task')
                result = cr.dictfetchall()
                min_sequence = result[0]['sequence']
                value['sequence'] = min_sequence - 1
            elif stage.name == 'Waiting':
                cr.execute('SELECT MAX(sequence) as sequence FROM project_task')
                result = cr.dictfetchall()
                max_sequence = result[0]['sequence']
                value['sequence'] = max_sequence + 1
        return super(project_task,self).write(cr, uid, ids, value, context=context)

    def case_set(self, cr, uid, ids, new_state_name=None, values_to_update=None, new_stage_id=None, context=None):
        cases = self.browse(cr, uid, ids, context=context)
        # 1. update the stage
        if new_state_name:
            self.stage_set_with_state_name(cr, uid, cases, new_state_name, context=context)
        elif not (new_stage_id is None):
            self.stage_set(cr, uid, ids, new_stage_id, context=context)
        # 2. update values
        if values_to_update:
            super(project_task,self).write(cr, uid, ids, values_to_update, context=context)
        return True
    def download_all_pdf(self, cr, uid, ids, context):
        order_line_ids = []
        order_name = ''
        for task in self.browse(cr, uid, ids):
            if not order_name:
                order_name = task.drawing_order_id.name
                context.update({'order_name': order_name})
            for order_line in task.drawing_order_lines:
                order_line_ids.append(order_line.id)
        return self.pool.get('drawing.order.line').print_pdf(cr, uid, order_line_ids, context=context)
    def download_pdf(self, cr, uid, ids, context):
        order_line_ids = []
        order_name = ''
        for task in self.browse(cr, uid, ids):
            #produce_part_ids = []
            if not order_name:
                date_now = datetime.now().strftime(tools.DEFAULT_SERVER_DATE_FORMAT)
                order_name = u'%s-%s-%s-%s-%s'%(task.id,
                                               task.product.name,
                                               task.big_subassembly_id.name,
                                               task.dept_id.name,
                                               date_now)
                context.update({'order_name': order_name})
            for task_line in task.task_lines:
                order_line_ids.append(task_line.order_line_id.id)
                #if task_line.need_qty > 0:
                #    produce_part_ids.append(task_line.product_id.id)
            #for order_line in task.drawing_order_lines:
            #    if order_line.product_id.id in produce_part_ids:
            #        order_line_ids.append(order_line.id)
        return self.pool.get('drawing.order.line').print_pdf(cr, uid, order_line_ids, context=context)
project_task()
class mrp_production_workcenter_line(osv.osv):
    _inherit = "mrp.production.workcenter.line"
    _columns = {
        'big_subassembly_id': fields.related('bom_id','product_id',type='many2one',relation='product.product',string='Big Sub Assembly',readonly=True),
    }
    def action_done(self, cr, uid, ids, context=None):
        """ Check if all tasks are done before call parent action_done"""
        project_task_obj = self.pool.get('project.task')
        not_done_task_ids = project_task_obj.search(cr, uid, [
                                                              ('workorder_id','in',ids),
                                                              ('state','not in',['done','cancelled'])
                                                              ])
        if len(not_done_task_ids) > 0:
            raise osv.except_osv(_('Error!'), _('All tasks must be done to finish this work order!'))
        result = super(mrp_production_workcenter_line,self).action_done(cr, uid, ids, context=context)
        return result
    def start_wo(self, cr, uid, ids, context=None):
        drawing_order_obj = self.pool.get('drawing.order')
        project_task_obj = self.pool.get('project.task')
        for workcenter_line in self.browse(cr, uid, ids):
            #Find drawing order of this wo
            drawing_order_ids = drawing_order_obj.search(cr, uid, [
                                                                   ('mo_id','=',workcenter_line.production_id.id),
                                                                   ('product_id','=',workcenter_line.bom_id.product_id.id)
                                                                   ])
            for drawing_order in drawing_order_obj.browse(cr, uid, drawing_order_ids):
                #Check if drawing order is approved ?
                #if drawing_order.state != 'approved':
                #if drawing_order.state in ['draft','rejected','cancel']:
                #    raise osv.except_osv(_('Error!'), _('Drawing order must be ready, confirmed or approved in order to start work order!'))
                #    return False
                first_part_steps = {}
                for order_line in drawing_order.order_lines:
                    if order_line.first_step not in first_part_steps:
                        first_part_steps.update({order_line.first_step : True})
                start_task_ids = []
                for step in first_part_steps:
                    task_ids = project_task_obj.search(cr, uid, [
                                                                 ('workorder_id','=',workcenter_line.id),
                                                                 ('dept_code','=',step)
                                                                 ])
                    start_task_ids.extend(task_ids)
                #Start first task of each
                project_task_obj.do_open(cr, uid, start_task_ids)
    def action_start_working(self, cr, uid, ids, context=None):
        self.start_wo(cr, uid, ids, context)
        result = super(mrp_production_workcenter_line,self).action_start_working(cr, uid, ids, context=context)
        return result    
mrp_production_workcenter_line()