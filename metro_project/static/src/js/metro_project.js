
openerp.metro_project = function (instance) {
    
    var QWeb = instance.web.qweb;
    var _t = instance.web._t;
    var _lt = instance.web._lt;
    /*
    instance.web_kanban.KanbanGroup.include({
        do_action_print: function() {
            var self = this;  		
    		var item_ids = []
            _.each(this.records, function(record) {
    			item_ids.push(record.id)
            });
            self.do_action({
                name: _t("MFG Tasks"),
                res_model: 'task.print',
                src_model: 'project.task',
                views: [[false, 'form']],
                type: 'ir.actions.act_window',
                target: 'new',
    			context: {'active_ids':item_ids}
            });
            var am = instance.webclient.action_manager;
            var form = am.dialog_widget.views.form.controller;
            form.on("on_button_cancel", am.dialog, am.dialog.close);
            form.on('record_saved', self, function() {
                am.dialog.close();
                self.view.do_reload();
            });    
        },
    });
    */
};
