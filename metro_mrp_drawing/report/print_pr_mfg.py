import time
from openerp.report import report_sxw
from openerp.osv import osv, fields
from openerp.osv import osv
from datetime import datetime
import openerp.tools as tools
from datetime import timedelta
class print_pr_mfg(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(print_pr_mfg, self).__init__(cr, uid, name, context=context)
        type = context.get('type','all')
        self.type = type
        self.localcontext.update({
            'type': self.type,
            'time': time,
            'get_mfg_parts': self._get_mfg_parts,
        })
    def _get_mfg_parts(self, req, type='all'):
        result = []
        req_line_obj = self.pool.get('pur.req.line')
        if type=='all':
            return req.line_ids
        elif type=='missing':
            for part in req.line_ids:
                if part.product_qty_remain > 0:
                    result.append(part)
        elif type == 'all_sort_by_supplier':
            line_ids = req_line_obj.search(self.cr, self.uid, [('req_id','=',req.id)], order="supplier_id asc")
            result = req_line_obj.browse(self.cr, self.uid, line_ids)
        elif type == 'all_sort_by_supplier_missing':
            line_ids = req_line_obj.search(self.cr, self.uid, [('req_id', '=', req.id)],
                                               order="supplier_id asc")
            for part in req_line_obj.browse(self.cr, self.uid, line_ids):
                if part.product_qty_remain > 0:
                    result.append(part)
        return result
report_sxw.report_sxw('report.pr.mfg.part','pur.req','addons/metro_mrp_drawing/report/pr_mfg_part.rml',parser=print_pr_mfg, header='internal')
