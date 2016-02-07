openerp.web_url = function(instance) {

var QWeb = instance.web.qweb,
    _t = instance.web._t;

instance.web.ListView.List = instance.web.ListView.List.extend({
    render: function () {
        var self = this;
        this.$current.empty().append(
            QWeb.render('ListView.rows', _.extend({
                    render_cell: function () {
                        return self.render_cell.apply(self, arguments); }
                }, this)));
        this.records.each(function(record){
            var $row = self.$current.find('[data-id=' + record.get('id') + ']');
            for(var i=0, length=self.columns.length; i<length; ++i) {
            //alert(self.columns[i].name);
		if(self.columns[i].widget === 'drawing_url') {
                	var $cell = $row.find((_.str.sprintf('[data-field=%s]', self.columns[i].id)));
                	var download_url;
                	var value = record.get(self.columns[i].id);
                    if (value && value.substr(0, 10).indexOf(' ') == -1) {
                    //    download_url = "data:application/octet-stream;base64," + value;
                    	download_url = instance.session.url('/web/binary/saveas', {model: self.dataset.model, field: self.columns[i].id, id: record.attributes.id});
	                    if (self.columns[i].filename) {
	                        download_url += '&filename_field=' + self.columns[i].filename;
	                    }
	                	$cell.html(_.template('<a class="oe_form_uri" href="<%-text%>" target="blank" data-model="<%-model%>" data-id="<%-id%>">Download</a>', 	{
	                        text: instance.web.format_value(download_url, self.columns[i], ''),
	                        model: self.columns[i].relation,
	                        id: record.attributes.id
	                    	}))
                    }else
                    	$cell.html('');
                    	
                }
            }
        });
        this.pad_table_to(4);
    }
});

 
instance.web.form.One2ManyList = instance.web.form.One2ManyList.extend({
	render: function () {
        var self = this;
        this.$current.empty().append(
            QWeb.render('ListView.rows', _.extend({
                    render_cell: function () {
                        return self.render_cell.apply(self, arguments); }
                }, this)));
        this.records.each(function(record){
            var $row = self.$current.find('[data-id=' + record.get('id') + ']');
            for(var i=0, length=self.columns.length; i<length; ++i) {
                if(self.columns[i].widget === 'drawing_url') {
                	var $cell = $row.find((_.str.sprintf('[data-field=%s]', self.columns[i].id)));
                	var download_url;
                	var value = record.get(self.columns[i].id);
                    if (value && value.substr(0, 10).indexOf(' ') == -1) {
                        //    download_url = "data:application/octet-stream;base64," + value;
                        	download_url = instance.session.url('/web/binary/saveas', {model: self.dataset.model, field: self.columns[i].id, id: record.attributes.id});
    	                    if (self.columns[i].filename) {
    	                        download_url += '&filename_field=' + self.columns[i].filename;
    	                    }
    	                	$cell.html(_.template('<a class="oe_form_uri" href="<%-text%>" target="blank" data-model="<%-model%>" data-id="<%-id%>">Download</a>', 	{
    	                        text: instance.web.format_value(download_url, self.columns[i], ''),
    	                        model: self.columns[i].relation,
    	                        id: record.attributes.id
    	                    	}))
                        }else
                        	$cell.html('');
                }
            }
        });
        this.pad_table_to(4);
    }
  }); 
};