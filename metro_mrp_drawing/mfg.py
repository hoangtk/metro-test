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
from openerp.addons.product import _common
class project_task_line(osv.osv):
    _name = "project.task.line"
    _columns = {
                'task_id': fields.many2one('project.task','Task'),
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
                    raise osv.except_osv(_('Error!'), _(line.product_id.name + ' : done quantity must <= need quantity!'))
                    return False
        result = super(project_task_line,self).write(cr, uid, ids, vals, context=context)
        return result
    _defaults = {
                }
    _order = "need_qty desc"
project_task_line()
def rounding(f, r):
    import math
    if not r:
        return f
    return math.ceil(f / r) * r
class mrp_bom(osv.osv):
    _name = 'mrp.bom'
    _inherit = 'mrp.bom'
    def _bom_explode_an_assembly(self, cr, uid, bom, product, factor, properties=None, level=0, routing_id=False, previous_products=None, master_bom=None, context=None,assembly_id = False):
        """ Finds Products and Work Centers for related BoM for manufacturing order.
        @param bom: BoM of particular product template.
        @param product: Select a particular variant of the BoM. If False use BoM without variants.
        @param factor: Factor represents the quantity, but in UoM of the BoM, taking into account the numbers produced by the BoM
        @param properties: A List of properties Ids.
        @param level: Depth level to find BoM lines starts from 10.
        @param previous_products: List of product previously use by bom explore to avoid recursion
        @param master_bom: When recursion, used to display the name of the master bom
        @return: result: List of dictionaries containing product details.
                 result2: List of dictionaries containing Work Center details.
        """
        uom_obj = self.pool.get("product.uom")
        routing_obj = self.pool.get('mrp.routing')
        master_bom = master_bom or bom


        def _factor(factor, product_efficiency, product_rounding):
            factor = factor / (product_efficiency or 1.0)
            factor = _common.ceiling(factor, product_rounding)
            if factor < product_rounding:
                factor = product_rounding
            return factor

        factor = _factor(factor, bom.product_efficiency, bom.product_rounding)

        result = []
        result2 = []

        routing = (routing_id and routing_obj.browse(cr, uid, routing_id)) or bom.routing_id or False
        if routing:
            for wc_use in routing.workcenter_lines:
                wc = wc_use.workcenter_id
                d, m = divmod(factor, wc_use.workcenter_id.capacity_per_cycle)
                mult = (d + (m and 1.0 or 0.0))
                cycle = mult * wc_use.cycle_nbr
                result2.append({
                    'name': tools.ustr(wc_use.name) + ' - ' + tools.ustr(bom.product_tmpl_id.name_get()[0][1]),
                    'workcenter_id': wc.id,
                    'sequence': level + (wc_use.sequence or 0),
                    'cycle': cycle,
                    'hour': float(wc_use.hour_nbr * mult + ((wc.time_start or 0.0) + (wc.time_stop or 0.0) + cycle * (wc.time_cycle or 0.0)) * (wc.time_efficiency or 1.0)),
                })

        for bom_line_id in bom.bom_line_ids:
            if bom_line_id == assembly_id:
                if self._skip_bom_line(cr, uid, bom_line_id, product, context=context):
                    continue
                if set(map(int, bom_line_id.property_ids or [])) - set(properties or []):
                    continue
    
                if previous_products and bom_line_id.product_id.product_tmpl_id.id in previous_products:
                    raise osv.except_osv(_('Invalid Action!'), _('BoM "%s" contains a BoM line with a product recursion: "%s".') % (master_bom.name,bom_line_id.product_id.name_get()[0][1]))
    
                quantity = _factor(bom_line_id.product_qty * factor, bom_line_id.product_efficiency, bom_line_id.product_rounding)
                bom_id = self._bom_find(cr, uid, product_id=bom_line_id.product_id.id, properties=properties, context=context)
    
                #If BoM should not behave like PhantoM, just add the product, otherwise explode further
                if bom_line_id.type != "phantom" and (not bom_id or self.browse(cr, uid, bom_id, context=context).type != "phantom"):
                    result.append({
                        'name': bom_line_id.product_id.name,
                        'product_id': bom_line_id.product_id.id,
                        'product_qty': quantity,
                        'product_uom': bom_line_id.product_uom.id,
                        'product_uos_qty': bom_line_id.product_uos and _factor(bom_line_id.product_uos_qty * factor, bom_line_id.product_efficiency, bom_line_id.product_rounding) or False,
                        'product_uos': bom_line_id.product_uos and bom_line_id.product_uos.id or False,
                    })
                elif bom_id:
                    all_prod = [bom.product_tmpl_id.id] + (previous_products or [])
                    bom2 = self.browse(cr, uid, bom_id, context=context)
                    # We need to convert to units/UoM of chosen BoM
                    factor2 = uom_obj._compute_qty(cr, uid, bom_line_id.product_uom.id, quantity, bom2.product_uom.id)
                    quantity2 = factor2 / bom2.product_qty
                    res = self._bom_explode(cr, uid, bom2, bom_line_id.product_id, quantity2,
                        properties=properties, level=level + 10, previous_products=all_prod, master_bom=master_bom, context=context)
                    result = result + res[0]
                    result2 = result2 + res[1]
                else:
                    raise osv.except_osv(_('Invalid Action!'), _('BoM "%s" contains a phantom BoM line but the product "%s" does not have any BoM defined.') % (master_bom.name,bom_line_id.product_id.name_get()[0][1]))

        return result, result2
    
mrp_bom()
class mrp_production(osv.osv):
    _inherit = 'mrp.production'
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
    def _prepare_lines_an_assembly(self, cr, uid, production, assembly_id):
        # search BoM structure and route
        bom_obj = self.pool.get('mrp.bom')
        uom_obj = self.pool.get('product.uom')
        bom_point = production.bom_id
        bom_id = production.bom_id.id
        if not bom_point:
            bom_id = bom_obj._bom_find(cr, uid, product_id=production.product_id.id)
            if bom_id:
                bom_point = bom_obj.browse(cr, uid, bom_id)
                routing_id = bom_point.routing_id.id or False
                self.write(cr, uid, [production.id], {'bom_id': bom_id, 'routing_id': routing_id})

        if not bom_id:
            raise osv.except_osv(_('Error!'), _("Cannot find a bill of material for this product."))

        # get components and workcenter_lines from BoM structure
        factor = uom_obj._compute_qty(cr, uid, production.product_uom.id, production.product_qty, bom_point.product_uom.id)
        # product_lines, workcenter_lines
        return bom_obj._bom_explode_an_assembly(cr, uid, bom_point, production.product_id, factor / bom_point.product_qty, routing_id=production.routing_id.id,assembly_id = assembly_id)

    
    def _action_compute_lines_an_aseembly(self, cr, uid, ids, assembly_id):
        results = []
        prod_line_obj = self.pool.get('mrp.production.product.line')
        workcenter_line_obj = self.pool.get('mrp.production.workcenter.line')
        for production in self.browse(cr, uid, ids):
            #unlink product_lines
            prod_line_obj.unlink(cr, SUPERUSER_ID, [line.id for line in production.product_lines])
            #unlink workcenter_lines
            workcenter_line_obj.unlink(cr, SUPERUSER_ID, [line.id for line in production.workcenter_lines])

            res = self._prepare_lines_an_assembly(cr, uid, production)
            results = res[0] # product_lines
            results2 = res[1] # workcenter_lines

            # reset product_lines in production order
            for line in results:
                line['production_id'] = production.id
                prod_line_obj.create(cr, uid, line)

            #reset workcenter_lines in production order
            for line in results2:
                line['production_id'] = production.id
                workcenter_line_obj.create(cr, uid, line)
        return results        
    def action_compute_an_assembly(self, cr, uid, ids, assembly_id):
        return len(self._action_compute_lines_an_aseembly(cr, uid, ids, assembly_id))
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
                    drawing_order_line_obj.write(cr, uid, [line.id], order_vals)
            project_task_obj.unlink(cr, uid, duplicate_task_ids) 
            workcenter_line_obj.unlink(cr, uid, remove_workcenter_line_ids)
            #Add product and qty to task
            for line in mo.workcenter_lines:
                for task_id in line.task_ids:
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
    _columns = {
            'date_issued': fields.date('Date Issued'),
            'drawing_order_id': fields.many2one('drawing.order', "Drawing Order"),
            'prepare_qty': fields.integer('Prepare Quantity',readonly=True),
            'done_qty': fields.integer('Done Quantity',readonly=True),
            'need_qty': fields.integer('Need Quantity',readonly=True),         
            'drawing_order_lines': fields.related('drawing_order_id','order_lines',type="one2many",relation="drawing.order.line",string="Drawing Order Lines"),
            'big_subassembly_id': fields.related('workorder_id','big_subassembly_id',type='many2one',relation='product.product',string='Big Sub Assembly',readonly=True),
            'dept_code': fields.related('dept_id','code',type="char",size=10,readonly=True),
            'task_lines': fields.one2many('project.task.line','task_id',string='Task Lines',ondelete="cascade"),
            'progress': fields.function(_hours_get, string='Progress (%)', multi='hours', group_operator="avg", help="If the task has a progress of 99.99% you should close the task if it's finished or reevaluate the time",
                store = {
                    'project.task': (lambda self, cr, uid, ids, c={}: ids, ['work_ids', 'remaining_hours', 'planned_hours','state','done_qty','need_qty'], 10),
                    'project.task.work': (_get_task, ['hours'], 10),
                }),            
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
        #Check if all task lines finished ?
        task_line_obj = self.pool.get('project.task.line')
        task_line_ids = task_line_obj.search(cr, uid, [
                                                       ('task_id','in', ids),
                                                       ('need_qty','>',0),
                                                       ('state','!=','done'),
                                                       ])
        if task_line_ids:
            #TODO: Make part done
            for task_line in task_line_obj.browse(cr, uid, task_line_ids):
                task_line_obj.write(cr, uid, [task_line.id],{
                                                             'done_qty':task_line.need_qty,
                                                             'state':'done'
                                                             })
            #raise osv.except_osv(_('Error!'), _('Can not mark task done unless all parts are done!'))
        result = super(project_task,self).do_close(cr, uid, ids, context=context)
        #TODO Send email to notify task is done
        self._email_notify_done(cr, uid, ids, ['group_mrp_supervisor'], context)
        return result    
    def do_open(self, cr, uid, ids, context=None):
        """ Compatibility when changing to case_open. """
        result = super(project_task,self).do_open(cr, uid, ids, context=context)
        self._update_task_line_status(cr, uid, ids, context)
        return result
    def do_save(self, cr, uid, ids, context=None):
        return True
    def _update_task_line_status(self, cr, uid, ids, context=None):
        drawing_order_line_obj = self.pool.get('drawing.order.line')
        task_line_obj = self.pool.get('project.task.line')
        for task in self.browse(cr, uid, ids):
            if task.project_type == 'mfg':
                #TODO: Check if drawing order line is approved before continue
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
                    task_vals = {}
                    task_vals.update({'status': 'On Working'})
                    drawing_order_line_obj.write(cr, uid, [order_line.id],task_vals)
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
    def write(self, cr, uid, ids, vals, context=None):
        """" Override write to check and move parts if finnish """
        result = super(project_task,self).write(cr, uid, ids, vals, context)
        drawing_order_obj = self.pool.get('drawing.order')
        drawing_order_line_obj = self.pool.get('drawing.order.line')
        task_line_obj = self.pool.get('project.task.line')
        stage_obj = self.pool.get('project.task.type')
        next_task_to_start_ids = []
        done_task_to_finish_ids = []
        changed_prepare_qty_taskline_ids = []
        for task in self.browse(cr, uid, ids):
            if task.project_type == 'mfg':
                dept_code = task.dept_code
                prepare_qty = 0
                done_qty = 0
                need_qty = 0
                for task_line in task.task_lines:
                    prepare_qty = prepare_qty + task_line.prepare_qty
                    done_qty = done_qty + task_line.done_qty
                    need_qty = need_qty + task_line.need_qty
                    is_done = False
                    product = task_line.product_id
                    if task_line.done_qty == task_line.need_qty and task_line.need_qty > 0:
                        is_done = True
                        task_line_obj.write(cr, uid, [task_line.id],{
                                                                     'state':'done',
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
                            order_line_vals.update({'status': 'Done'})
                        elif dept_code != order_line.last_step:
                            steps = drawing_order_obj._split_work_steps(order_line.work_steps)
                            #Move parts
                            next_step = ""
                            for index, step in enumerate(steps):
                                if step == dept_code:
                                    next_step = steps[index+1]
                                    break
                            if next_step and task_line.done_qty > 0: 
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
                                    changed_prepare_qty_taskline_ids.extend(next_task_line_ids)
                                if next_task_ids:
                                    next_task_to_start_ids.extend(next_task_ids)
                        drawing_order_line_obj.write(cr, uid, [order_line.id],order_line_vals)
                task_vals = {
                               'prepare_qty': prepare_qty,
                               'done_qty': done_qty,
                               'need_qty': need_qty,
                            }
                #TODO: Set stage for tasks
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
        created_next_task_to_start_ids = self.search(cr, uid, [
                                                               ('state','=','draft'),
                                                               ('id','in',next_task_to_start_ids)
                                                               ])
        if changed_prepare_qty_taskline_ids:
            taskline_records = task_line_obj.read(cr, uid, changed_prepare_qty_taskline_ids, ['task_id'])
            changed_prepare_qty_task_ids = []
            for record in taskline_records:
                changed_prepare_qty_task_ids.append(record['task_id'][0])
            for task in self.browse(cr, uid, changed_prepare_qty_task_ids):
                prepare_qty = 0.0
                for task_line in task.task_lines:
                    prepare_qty = prepare_qty + task_line.prepare_qty
                self.write(cr, uid, [task.id],{'prepare_qty': prepare_qty})
        if created_next_task_to_start_ids:
            self.do_open(cr, uid, created_next_task_to_start_ids,context=context)
        if done_task_to_finish_ids:
            self.do_close(cr, uid, done_task_to_finish_ids, context=context)
        self._check_missed_dealine(cr, uid, ids, context=context)
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
    def download_pdf(self, cr, uid, ids, context):
        order_line_ids = []
        for task in self.browse(cr, uid, ids):
            produce_part_ids = []
            for task_line in task.task_lines:
                if task_line.need_qty > 0: 
                    produce_part_ids.append(task_line.product_id.id)
            for order_line in task.drawing_order_lines:
                if order_line.product_id.id in produce_part_ids:
                    order_line_ids.append(order_line.id)
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
    def action_start_working(self, cr, uid, ids, context=None):
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
                if drawing_order.state != 'approved':
                    raise osv.except_osv(_('Error!'), _('Drawing order must be approved in order to start work order!'))
                    return False
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
        result = super(mrp_production_workcenter_line,self).action_start_working(cr, uid, ids, context=context)
        return result    
mrp_production_workcenter_line()