# -*- coding: utf-8 -*-
import time
from openerp.osv import fields, osv
from openerp.osv.orm import browse_record, browse_null
from openerp.tools.translate import _
import datetime
import openerp.tools as tools
from openerp.addons.metro_mrp_drawing.drawing_order import WORK_STEP_LIST
import xlrd
import StringIO

class generate_pr_xls_wizard(osv.osv_memory):
    _name = 'generate.pr.xls.wizard'
    _inherit = 'generate.pr.wizard'
    _description = 'Generate PR From Xls Wizard'
    _columns = {
        'filename': fields.char('Filename',size=128),
        'bom_file': fields.binary('BOM File',required=True),
    }

    def do_generate(self, cr, uid, ids, context=None):
        drawing_order_obj = self.pool.get('drawing.order')
        product_obj = self.pool.get('product.product')
        generate_pr = self.browse(cr, uid, ids, context)[0]
        missing_erpno_list = []
        if generate_pr.bom_file:
            error_logs = drawing_order_obj.check_bom_file_content(cr, uid, False, False, generate_pr.bom_file, False)
            if len(error_logs) > 0:
                return self.pool.get('warning').info(cr, uid, title='Error', message="\n".join(error_logs))
            inputStr = StringIO.StringIO()
            inputStr.write(generate_pr.bom_file.decode('base64'))
            workbook = xlrd.open_workbook(file_contents=inputStr.getvalue())
            worksheet = workbook.sheet_by_index(0)
            row = 2
            sequence = 1
            pur_req_id = False

            while row < worksheet.nrows:
                bom_line = drawing_order_obj.read_bom_line(worksheet=worksheet, row=row)
                if bom_line['part_name']:
                    if bom_line['part_type'] != 'PRODUCED' and bom_line['erp_no']:
                        product_ids = product_obj.search(cr, uid, [
                            ('default_code', '=', bom_line['erp_no'])
                        ])
                        if not product_ids:
                            missing_erpno_list.append(bom_line['erp_no'])
                        else:
                            product_id = product_obj.browse(cr, uid, product_ids[0])
                            bom_line.update({'product_id': product_id,
                                             'quantity': bom_line['bom_qty']})
                            if not pur_req_id:
                                pur_req_id = self._create_pr(cr, uid, {
                                    'warehouse_id': generate_pr.warehouse_id.id,
                                    'delivery_date': generate_pr.delivery_date,
                                })
                            self._create_pr_line(cr, uid, pur_req_id, bom_line, sequence, generate_pr.delivery_date, False)
                            sequence += 1
                row += 1
        if len(missing_erpno_list) > 0:
            return self.pool.get('warning').info(cr, uid, title='Information', message=_(
                "Some parts can not generate PR due to erp # do not exist(%s)!") % ",".join(missing_erpno_list))
        return True

generate_pr_xls_wizard()
