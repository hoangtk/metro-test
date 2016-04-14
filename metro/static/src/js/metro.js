
openerp.metro = function (instance) {
    
    var QWeb = instance.web.qweb;
    var _t = instance.web._t;
    var _lt = instance.web._lt;

    instance.metro.LangSwitcher = instance.web.Widget.extend({
        template: 'LangSwitcher',
        init: function (parent) {
            this._super(parent);
            this.set({"cur_lang": "en_US"});
        },
        start: function() {
            var self = this;
            var tmp = function() {
                this.$el.toggleClass("oe_lang_cn", this.get("cur_lang") === "zh_CN");
                this.$el.toggleClass("oe_lang_en", this.get("cur_lang") === "en_US");
            };
            this.on("change:cur_lang", this, tmp);
            _.bind(tmp, this)();
            this.$(".oe_lang_switch_cn").click(function() {
                self.do_lang_switch();
            });
            this.$(".oe_lang_switch_en").click(function() {
                self.do_lang_switch();
            });
            this.$el.tipsy({
                title: function() {
                    if (self.get("cur_lang") === "zh_CN") {
                        return _.str.sprintf(_t("Switch to English"));
                    } else {
                        return _.str.sprintf(_t("Switch to Chinese"));
                    }
                },
                html: true,
            });
            if(this.session.user_context.lang === "en_US"){
            	this.set({"cur_lang": "en_US"});
            }else{
            	this.set({"cur_lang": "zh_CN"});
            }
            
        },
        do_lang_switch: function () {
            var self = this;
        	if (self.get("cur_lang") === "en_US") {
        		self.set({"cur_lang": "zh_CN"});
        	} else {
        		self.set({"cur_lang": "en_US"});
        	}
            var res_users = new instance.web.DataSet(self, 'res.users');
            var test = self.session.user_context;
            res_users.call('update_lang', [
                [self.session.user_context.uid],{to_lang: self.get("cur_lang")}
            ]).done(function (result) {
            	window.location.reload();
            });
        	
        },
    });
    
    instance.web.UserMenu.include({
        do_update: function () {
            var self = this;
            this._super.apply(this, arguments);
            this.update_promise.done(function () {
                if (self.lang_switcher) {
                    return;
                }else{
                    self.lang_switcher = new instance.metro.LangSwitcher(self);
                    self.lang_switcher.appendTo(instance.webclient.$el.find('.oe_systray'));
                }
            });
        },
    });
    //show the image in list view
    /* Add a new mapping to the registry for image fields */
    instance.web.list.columns.add('field.image','instance.web.list.FieldBinaryImage');
    /* Define a method similar to the one for forms to render image fields */
    instance.web.list.FieldBinaryImage = instance.web.list.Column.extend({
	    /**
	     * Return a image to the binary field of specified as widget image
	     *
	     * @private
	     */
    	_format: function (row_data, options) {
            var placeholder = "/web/static/src/img/placeholder.png";
            var value = row_data[this.id].value;
            var img_url = placeholder;
            if (value && value.substr(0, 10).indexOf(' ') == -1) {
		        /* Data inline */
		        /* FIXME: can we get the mimetype from the data? */
		        img_url = "data:image/png;base64," + value;
	        } else if (value) {
		        /* Data by URI (presumably slow) */
		        img_url = instance.session.url('/web/binary/image', {model: options.model, field: this.id, id: options.id});
	        }
	        /* FIXME: move the 30px stuff to something templateable */
	        return _.template('<image src="<%-src%>" width="50px" height="50px"/>', {src: img_url,});
    	}
    });
    instance.web.form.widgets.add('xlsfile_widget', 'instance.web.form.FieldBinaryXlsFile');
    instance.web.form.FieldBinaryXlsFile = instance.web.form.FieldBinaryFile.extend({
        template: 'FieldBinaryXlsFile',
    });

    instance.web.list.Binary = instance.web.list.Column.extend({
        /**
         * Return a link to the binary data as a file
         *
         * @private
         */
        _format: function (row_data, options) {
            var text = _t("Download");
            var value = row_data[this.id].value;
            var download_url;
            if (value && value.substr(0, 10).indexOf(' ') == -1) {
                download_url = "data:application/octet-stream;base64," + value;
            } else {
                download_url = instance.session.url('/web/binary/saveas', {model: options.model, field: this.id, id: options.id});
                if (this.filename) {
                    download_url += '&filename_field=' + this.filename;
                }
            }
            //johnw, add the download file name for one2many list binary field
            /*
            if (this.filename && row_data[this.filename]) {
                text = _.str.sprintf(_t("Download \"%s\""), instance.web.format_value(
                        row_data[this.filename].value, {type: 'char'}));
            }
            return _.template('<a href="<%-href%>"><%-text%></a> (<%-size%>)', {
                text: text,
                href: download_url,
                size: instance.web.binary_to_binsize(value),
            });
            */
            var row_filename = "Download";
            if (this.filename && row_data[this.filename]) {
            	row_filename = instance.web.format_value(row_data[this.filename].value, {type: 'char'})
                text = _.str.sprintf(_t("Download \"%s\""), row_filename);
            }
            return _.template('<a href="<%-href%>" download="<%-download%>"><%-text%></a>', {
                text: text,
                href: download_url,
                download: row_filename,
            });
        }
    });
};
