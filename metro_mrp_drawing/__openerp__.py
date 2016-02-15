# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>).
#    Copyright (C) 2010 OpenERP s.a. (<http://openerp.com>).
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
{
    'name': 'Metro MRP Drawing',
    'version': '1.0',
    'category': 'Metro',
    'description': """
        Metro MRP Drawing
        """,
    'author': 'Metro Tower Trucks',
    'website': 'http://www.metrotowtrucks.com',
    'depends': ["web", "metro", "metro_project","metro_purchase"],
    'css' : [
        "static/src/css/mrp_drawing.css",
    ],
    'qweb' : [
        'static/src/xml/web_kanban.xml',
        "static/src/xml/base.xml",
    ],
    'js' : [
        "static/src/js/mrp_drawing.js",
    ],        
    'data': ['project_data.xml',
             'project_ir_cron_data.xml',
             'task_report.xml',
             'wizard/task_print.xml',
             'wizard/generate_pr_wizard.xml',
             'upload_multi_drawings_view.xml',
             'drawing_order_view.xml',
             'drawing_step_view.xml',
             'pur_req_view.xml',
             'mrp_view.xml',
             'security/ir.model.access.csv'
             ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
