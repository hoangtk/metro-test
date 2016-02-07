# -*- coding: utf-8 -*-
import openerp.addons.web.http as http
from werkzeug.wrappers import Response
import urllib
class Drawing_Order_Print_PDF(http.Controller):
    _cp_path = '/web/export/drawing_order_print_pdf'
    @http.httprequest
    def index(self, request, file_name, file_data):
        pdf_data = open(file_data,'rb').read()
        response = Response(pdf_data)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = 'attachment; filename="%s.pdf"'%file_name
        return response
