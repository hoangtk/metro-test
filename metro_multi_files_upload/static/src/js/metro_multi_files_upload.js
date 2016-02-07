
openerp.metro_multi_files_upload = function (instance) {
    
    var QWeb = instance.web.qweb;
    var _t = instance.web._t;
    var _lt = instance.web._lt;
    
    /**Add the file multi selecting on the many2many_binary field**/
    instance.web.form.FieldMany2ManyBinaryMultiFiles.include({
        on_file_change: function (event) {
            event.stopPropagation();
            var self = this;
            var $target = $(event.target);
            if ($target.val() !== '') {            	
            	//get the file list
            	sel_files = event.target.files;
            	
            	var filename = 'empty file checking';            	
                var files = _.filter(this.get('value'), function (file) {
                    if((file.filename || file.name) == filename) {
                        self.ds_file.unlink([file.id]);
                        return false;
                    } else {
                        return true;
                    }
                });
                
                for (var i = 0; i < sel_files.length; i += 1) {
                    filename = sel_files[i].name;

                    // if the files is currently uploded, don't send again
                    if( !isNaN(_.find(files, function (file) { return (file.filename || file.name) == filename && file.upload; } )) ) {
                        sel_files[i] = False
                    	continue;
                    }

                    // if the files exits for this answer, delete the file before upload
                    files = _.filter(files, function (file) {
                        if((file.filename || file.name) == filename) {
                            self.ds_file.unlink([file.id]);
                            return false;
                        } else {
                            return true;
                        }
                    });
                    
                    // add file on result
                    files.push({
                        'id': 0,
                        'name': filename,
                        'filename': filename,
                        'url': '',
                        'upload': true
                    });                    
                	
                }                    

                // block UI or not
//                if(this.node.attrs.blockui>0) {
//                    instance.web.blockUI();
//                }
                instance.web.blockUI();

                // TODO : unactivate send on wizard and form

                // submit file
                this.$('form.oe_form_binary_form').submit();
                this.$(".oe_fileupload").hide();

                this.set({'value': files});
            }
        },
        on_file_loaded: function (event, result) {
            var files = this.get('value');

            // unblock UI
//            if(this.node.attrs.blockui>0) {
//                instance.web.unblockUI();
//            }
            instance.web.unblockUI();

            // TODO : activate send on wizard and form

            if (result.error) {
                this.do_warn( _t('Uploading error'), result.error);
                files = _.filter(files, function (val) { return !val.upload; });
            } else {
                for(var i in files){
                    filename = files[i].filename
                    created_file_id = result[filename]
                    if(created_file_id != undefined && files[i].upload) {
                        files[i] = {
                            'id': created_file_id,
                            'name': filename,
                            'filename': filename,
                            'url': this.get_file_url({id:created_file_id})
                        };
                    }
                }
            }

            this.set({'value': files});
            this.render_value()
        },
        
    });
    
};
