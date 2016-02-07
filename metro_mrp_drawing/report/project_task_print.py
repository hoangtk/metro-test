# -*- coding: utf-8 -*-
##############################################################################
#    
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
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

import time
from openerp.report import report_sxw
from openerp.osv import osv, fields
from openerp.osv import osv
from datetime import datetime
import openerp.tools as tools
from datetime import timedelta
class project_task_print_with_parts(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(project_task_print_with_parts, self).__init__(cr, uid, name, context=context)
        active_id = context.get('active_id',False)
        self.task_day = False
        if active_id:
            task_print = self.pool.get('task.print').browse(cr, uid, active_id)
            self.task_day = task_print.task_day
        self.localcontext.update({
            'task_day': self.task_day,
            'time': time,
            'get_priority':self.get_priority,
            'get_emp_names':self.get_emp_names,
            'get_mfg_ids':self.get_mfg_ids,
            'get_group_mfg_ids': self.get_group_mfg_ids,
            'get_project': self.get_project,
            'get_unit': self.get_unit,
            'get_unit_qty': self.get_unit_qty,
            'get_sum': self._get_sum,
            'get_weekdays': self._get_week_list,
            'get_today': self._get_today,
            'get_quantities': self._get_part_quantities,
            'get_task_quantities': self._get_task_quantities,
            'get_all_part_quantities': self._get_all_part_quantities,
            'get_sum_bom_qty': self._get_sum_bom_qty,
        })
    def get_priority(self,priority):
        return self._get_sellection_name('project.task','priority',priority)  
    def get_emp_names(self,emps):
        emp_names = [emp.name for emp in emps]
        return ', '.join(emp_names)  
    def get_mfg_ids(self,mfg_ids):
        mfg_ids_name = [mfg_id.name for mfg_id in mfg_ids]
        return ','.join(mfg_ids_name)   
    def get_group_mfg_ids(self,group):
        mfg_ids_dict = {}
        for task_id in group.task_ids:
            for mfg_id in task_id.mfg_ids:
                mfg_ids_dict[mfg_id] = True
        mfg_ids = []
        for key in sorted(mfg_ids_dict.iterkeys()):
            mfg_ids.append(key)
        return self.get_mfg_ids(mfg_ids)       
    def get_unit_qty(self, group):
        product_names_dict = {}
        for task_id in group.task_ids:
            if task_id.product.name not in product_names_dict:
                product_names_dict[task_id.product.name] = int(task_id.production_id.product_qty)
            else:
                product_names_dict[task_id.product.name] = product_names_dict[task_id.product.name] + int(task_id.production_id.product_qty)
        product_names = []
        for key in sorted(product_names_dict.iterkeys()):
            product_names.append(key + "(" + str(product_names_dict[key]) + ")")
        return ";".join(product_names)        
        return True
    def get_unit(self, group):
        product_names_dict = {}
        for task_id in group.task_ids:
            product_names_dict[self.get_mfg_ids(task_id.mfg_ids) + "(" + task_id.product.name + ")"] = True
        product_names = []
        for key in sorted(product_names_dict.iterkeys()):
            product_names.append(key)
        return ";".join(product_names)
    def get_project(self, group):
        subassembly_names_dict = {}
        for task_id in group.task_ids:
            subassembly_names_dict[self.get_mfg_ids(task_id.mfg_ids) + "(" + task_id.big_subassembly_id.name  + ")"] = True
        subassembly_names = []
        for key in sorted(subassembly_names_dict.iterkeys()):
            subassembly_names.append(key)
        return ";".join(subassembly_names)    
    #get the selection display value by the selection key(field_value)
    def _get_sellection_name(self,model_name,field_name,field_value):
        field_sel = self.pool.get(model_name)._columns[field_name].selection
        trans_src = field_value;
        for sel_item in field_sel:
            if(sel_item[0] == field_value):
                trans_src = sel_item[1]
                break
        trans_obj = self.pool.get('ir.translation')
        trans_name = model_name + ',' + field_name
        trans_result = trans_obj._get_source(self.cr, self.uid, trans_name, 'selection', self.localcontext.get('lang'), trans_src)
        return trans_result 
    def _get_today(self):
        return datetime.now().date()
    def _get_week_list(self):
        if self.task_day:
            #date_now = datetime.strptime(self.task_day, "%Y-%m-%d")
            date_now = datetime.strptime(self.task_day, tools.DEFAULT_SERVER_DATE_FORMAT)
        else:
            date_now = datetime.now().date()
        result = []
        week_days = ['MON','TUE','WED','THU','FRI','SAT','SUN']
        for d in range(7):
            d_day = date_now + timedelta(days = d)
            r = {}
            r["name"] = week_days[d_day.weekday()]
            r["date"] = d_day.strftime("%m/%d")
            result.append(r)
        return result
    def _get_task_quantities(self, task):
        result = []
        i = 1
        for line in task.task_lines:
            if self.task_day or line.need_qty > 0:
                r = {}
                r['id'] = i
                r['name'] = line.product_id.name
                r['need_qty'] = line.need_qty
                r['done_qty'] = line.done_qty
                r['bom_qty'] = ''
                if task.production_id.product_qty > 0:
                    r['bom_qty'] = int(line.need_qty / task.production_id.product_qty)
                result.append(r)
                if i% 2 > 0:
                    r['style'] = 'ODD'
                else:
                    r['style'] = 'EVEN'
                i = i + 1
        return result
    def _get_sum_bom_qty(self, task):
        result = 0
        task_qties = self._get_task_quantities(task)
        for q in task_qties:
            result = result + q['bom_qty']
        return result
    def _get_all_part_quantities(self, group):
        i = 1
        result = []
#         language_code = self.pool.get('res.users').browse(self.cr,self.uid, self.uid).lang
#         language_ids = self.pool.get('res.lang').search(self.cr, self.uid, [
#                                                                            ('code','=',language_code)
#                                                                            ])
#         languages = self.pool.get('res.lang').browse(self.cr,self.uid, language_ids)
        #date_format="%Y-%m-%d"
        date_format = tools.DEFAULT_SERVER_DATE_FORMAT
#         if languages:
#             date_format = languages[0].date_format
        for task_id in group.task_ids:
            r = {}
            r['id'] = i
            r['mfg_id'] = self.get_mfg_ids(task_id.mfg_ids)
            r['unit'] = task_id.product.name
            r['project'] = task_id.big_subassembly_id.name
            r['date_issued'] = ''
            r['date_start'] = ''
            r['date_deadline'] = ''
            if task_id.date_issued:
                try:
                    r['date_issued'] = datetime.strptime(task_id.date_issued, date_format).strftime("%m/%d")
                except:
                    r['date_issued'] = ''
            if task_id.date_start:
                try:
                    r['date_start'] = datetime.strptime(task_id.date_start, date_format).strftime("%m/%d")
                except:
                    r['date_start'] = ''
            if task_id.date_deadline:
                try:
                    r['date_deadline'] = datetime.strptime(task_id.date_deadline, date_format).strftime("%m/%d")
                except:
                    r['date_deadline'] = ''
            r['days_left'] = ''
            date_now = datetime.now().date()
            if task_id.date_deadline:
                try:
                    time_delta = date_now - datetime.strptime(task_id.date_deadline, date_format).date() 
                    r['days_left'] = time_delta.days
                except:
                    r['days_left'] = ''
            result.append(r)
            i = i + 1
        return result
    def _get_part_quantities(self, group):
        task_ids = []
        for task_id in group.task_ids:
            task_ids.append(task_id.id)
        self.cr.execute("SELECT p.name_template as name, " \
                        "COALESCE(SUM(l.need_qty),0) as need_qty, " \
                        "COALESCE(SUM(l.done_qty),0) as done_qty " \
                "FROM project_task_line l " \
                "LEFT JOIN product_product p ON l.product_id = p.id " \
                "WHERE task_id IN %s " \
                "GROUP BY p.name_template " \
                "HAVING COALESCE(SUM(l.need_qty),0) > 0 " \
                "ORDER BY p.name_template",(tuple(task_ids),))
        result = self.cr.dictfetchall()
        i = 1
        new_result = []
        date_now = datetime.now().date()
        week_day = date_now.weekday()
        for r in result:
            r['id'] = i
            for d in range(7):
                if d == week_day:
                    r[d] = r['done_qty']
                else:
                    r[d] = ''
            i = i + 1
            new_result.append(r)
        return new_result
    def _get_sum(self,group):
        result= {'need_qty': 0,
                 'done_qty': 0}
        quantities_res = self._get_part_quantities(group)
        date_now = datetime.now().date()
        week_day = date_now.weekday()        
        for d in range(7):
            result[d] = ''        
        for r in quantities_res:
            result['need_qty'] = result['need_qty'] + r['need_qty']
            result['done_qty'] = result['done_qty'] + r['done_qty']
        result[week_day] = result['done_qty']
        return result
#tasks by group
report_sxw.report_sxw('report.task.group.by_assignee_full','task.group','addons/metro_mrp_drawing/report/task_group_by_assignee_full.rml',parser=project_task_print_with_parts, header='internal')
report_sxw.report_sxw('report.task.group.by_employee_full','task.group','addons/metro_mrp_drawing/report/task_group_by_employee_full.rml',parser=project_task_print_with_parts, header='internal')
report_sxw.report_sxw('report.task.group.by_team_full','task.group','addons/metro_mrp_drawing/report/task_group_by_team_full.rml',parser=project_task_print_with_parts, header='internal')
report_sxw.report_sxw('report.task.group.by_assignee_brief','task.group','addons/metro_mrp_drawing/report/task_group_by_assignee_brief.rml',parser=project_task_print_with_parts, header='internal')
report_sxw.report_sxw('report.task.group.by_employee_brief','task.group','addons/metro_mrp_drawing/report/task_group_by_employee_brief.rml',parser=project_task_print_with_parts, header='internal')
report_sxw.report_sxw('report.task.group.by_team_brief','task.group','addons/metro_mrp_drawing/report/task_group_by_team_brief.rml',parser=project_task_print_with_parts, header='internal')

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

