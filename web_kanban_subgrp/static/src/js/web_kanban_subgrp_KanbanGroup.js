openerp.web_kanban_subgrp_KanbanGroup = function (instance) {
var _t = instance.web._t,
   _lt = instance.web._lt;
var QWeb = instance.web.qweb;
//分组控件, called by do_process_groups(),do_process_dataset()
instance.web_kanban_subgrp.KanbanGroup = instance.web.Widget.extend({
    template: 'KanbanView_subgrp.group_header',
    //调用此处代码:do_process_groups():groups_array[index] = new instance.web_kanban_subgrp.KanbanGroup(self, sub_groups, group);
    init: function (parent, sub_groups, group) {
        var self = this;
        this._super(parent);
        this.$has_been_started = $.Deferred();
        this.view = parent;
        this.group = group;
        this.aggregates = {};
        this.value = this.title = null;
        if (this.group) {
            //设置标题和统计数据
            this.value = group.get('value');
            this.title = group.get('value');
            if (this.value instanceof Array) {
                this.title = this.value[1];
                this.value = this.value[0];
            }
            var field = this.view.group_by_field;
            if (!_.isEmpty(field)) {
                try {
                    this.title = instance.web.format_value(group.get('value'), field, false);
                } catch(e) {}
            }
            if (!_.isEmpty(this.title)) {
				if (this.title.indexOf('/') > 0) {
					this.title = this.title.substr(this.title.indexOf('/')+1)
				}
			}
            //统计字段数据
            _.each(this.view.aggregates, function(value, key) {
                self.aggregates[value] = group.get('aggregates')[key];
            });
        }

        if (this.title === false) {
            this.title = _t('Undefined');
            this.undefined_title = true;
        }
        var key = this.view.group_by + '-' + this.value;
        if (!this.view.state.groups[key]) {
            this.view.state.groups[key] = {
                folded: group ? group.get('folded') : false
            };
        }
        this.state = this.view.state.groups[key];
        this.$sub_groups = null;

        this.sub_groups = [];
        this.$has_been_started.done(function() {
            //添加组下面的子分组数据
            self.do_add_sub_groups(sub_groups);
        });
    },
    //调用此处代码: do_add_groups(): return group.insertBefore($last_td);
    start: function() {
        var self = this,
            def = this._super();
        if (! self.view.group_by) {
            self.$el.addClass("oe_kanban_no_group");
            self.quick = new (get_class(self.view.quick_create_class))(this, self.dataset, {}, false)
                .on('added', self, self.proxy('quick_created'));
            self.quick.replace($(".oe_kanban_no_group_qc_placeholder"));
        }
        this.$sub_groups = $(QWeb.render('KanbanView_subgrp.group_subgroups_container', { widget : this}));
        this.$sub_groups.insertBefore(this.view.$el.find('.oe_kanban_groups_records td:last'));

        this.$el.on('click', '.oe_kanban_group_dropdown li a', function(ev) {
            var fn = 'do_action_' + $(ev.target).data().action;
            if (typeof(self[fn]) === 'function') {
                self[fn]($(ev.target));
            }
        });
        // Head hook
        // Selecting records
        /*the select/unselect all function for input checkbox(select_all) in web_kanban.xml, 09/17/2014*/
        this.$el.on('click', '.oe_kanban_group_title_text input', function(ev) {
            var fn = 'do_action_' + $(ev.target).data().action;
            if (typeof(self[fn]) === 'function') {
                self[fn]($(ev.target));
            }
        });

        this.$el.data('widget', this);
        this.$sub_groups.data('widget', this);
        this.$has_been_started.resolve();
        var add_btn = this.$el.find('.oe_kanban_add');
        add_btn.tipsy({delayIn: 500, delayOut: 1000});
        this.is_started = true;
        return def;
    },
    destroy: function() {
        this._super();
        if (this.$sub_groups) {
            this.$sub_groups.remove();
        }
    },
    //添加组下面的子分组
    do_add_sub_groups: function(sub_groups, prepend) {	
        var self = this;
        var $list_header = this.$sub_groups.find('.oe_kanban_group_list_header');
        var $subgrps = this.$sub_groups.find('.oe_kanban_column_subgroups');

        _.each(sub_groups, function(sub_group) {			
			//读取子分组的明细数据
			cur_dataset = self.view.dataset
			var dataset = new instance.web.DataSetSearch(self, cur_dataset.model,
				new instance.web.CompoundContext(cur_dataset.get_context(), self.group.model.context(),sub_group.model.context()), 
				self.group.model.domain().concat(sub_group.model.domain())
				);
			return dataset.read_slice(self.view.fields_keys.concat(['__last_update']), { 'limit': self.view.limit })
				.then(function(records) {			
					//读取子分组的明细数据
					subgroup_field_name = sub_group.get('grouped_on')
					subgroup_model = self.view.fields_view.fields[subgroup_field_name].relation
					subgroup_value = sub_group.get('value')[0]
					new instance.web.Model(subgroup_model).query(['name','mfg_ids','product_id']).filter([['id','=',subgroup_value]]).first()
						.then(function(result) {
							var mfg_ids_name = ''
							//mfg id load finished flag
							var $mfg_ids_loaded = $.Deferred();		
							new instance.web.Model('sale.product').query(['name']).filter([['id','in',result.mfg_ids]]).all()
								.then(function(mfg_ids_data) {
									_.each(mfg_ids_data, function(mfg_id){
										mfg_ids_name += mfg_id.name + ', '
									});
									if (mfg_ids_name.length > 1){
										mfg_ids_name = mfg_ids_name.slice(0,-2)
									}
									$mfg_ids_loaded.resolve();
								});
								
							var product_name = ''
							//product id load finished flag
							var $product_id_loaded = $.Deferred();		
							new instance.web.Model('product.product').query(['name']).filter([['id','=',result.product_id[0]]]).first()
								.then(function(product) {
									product_name = product.name
									$product_id_loaded.resolve();
								});
							
							$.when($mfg_ids_loaded, $product_id_loaded).then(function() {	
								sub_group.title1 = mfg_ids_name							
								sub_group.title2 = result.name
								sub_group.title3 = product_name
								//创建实例,调用init()
								var rec = new instance.web_kanban_subgrp.KanbanSubGroup(self, records, sub_group, cur_dataset);
								if (!prepend) {
									//添加到界面,调用start()
									rec.appendTo($subgrps);
									self.sub_groups.push(rec);
								} else {
									rec.prependTo($subgrps);
									self.sub_groups.unshift(rec);
								}								
							});							
							
					});
			});
				
        });
		
    },
	

    do_toggle_fold: function(compute_width) {
        this.$el.add(this.$sub_groups).toggleClass('oe_kanban_group_folded');
        this.state.folded = this.$el.is('.oe_kanban_group_folded');
        this.$("ul.oe_kanban_group_dropdown li a[data-action=toggle_fold]").text((this.state.folded) ? _t("Unfold") : _t("Fold"));
    },
    do_action_toggle_fold: function() {
        this.do_toggle_fold();
    },
    do_action_edit: function() {
        var self = this;
        self.do_action({
            res_id: this.value,
            name: _t("Edit column"),
            res_model: self.view.group_by_field.relation,
            views: [[false, 'form']],
            type: 'ir.actions.act_window',
            target: "new",
            flags: {
                action_buttons: true,
            }
        });
        var am = instance.webclient.action_manager;
        var form = am.dialog_widget.views.form.controller;
        form.on("on_button_cancel", am.dialog, am.dialog.close);
        form.on('record_saved', self, function() {
            am.dialog.close();
            self.view.do_reload();
        });
    },    
    do_action_delete: function() {
        var self = this;
        if (confirm(_t("Are you sure to remove this column ?"))) {
            (new instance.web.DataSet(self, self.view.group_by_field.relation)).unlink([self.value]).done(function(r) {
                self.view.do_reload();
            });
        }  
    },
    /*the select/unselect all function for checkbox(select_all) in web_kanban.xml, 09/17/2014*/
    do_action_select_all: function(obj) {				
        _.each(this.sub_groups, function(sub_group) {
			sub_group.$('.oe_kanban_record_selector').prop('checked',
                $(obj).prop('checked')  || false);
        });				
    },
    /*the print function for 'print selected' ddlb menu, johnw, 09/17/2014*/
    do_action_print_selected: function(obj) {
        var self = this;  		
		var item_ids = [];
        _.each(this.sub_groups, function(sub_group) {
			sub_group.$('.oe_kanban_record_selector:checked').each(function () {
				data_id = parseInt($(this).attr('data-id'));
				item_ids.push(data_id);
			});
        });
		
        if (item_ids.length == 0) {
            instance.web.dialog($("<div />").text(_t("You must choose at least one record.")), { title: _t("Warning"), modal: true });
            return false;
        };	
        self.do_action({
            name: _t("MFG Tasks"),
            res_model: 'task.print',
            src_model: 'project.task',
            views: [[false, 'form']],
            type: 'ir.actions.act_window',
            target: 'new',
			context: {'active_ids':item_ids,'default_print_type':'by_team'}
        });
        var am = instance.webclient.action_manager;
        var form = am.dialog_widget.views.form.controller;
        form.on("on_button_cancel", am.dialog, am.dialog.close);
        form.on('record_saved', self, function() {
            am.dialog.close();
            self.view.do_reload();
        });    
    },
    /*the print function for print ddlb menu, johnw, 09/13/2014*/
    do_action_print: function() {
        var self = this;  		
		var item_ids = []

        _.each(this.sub_groups, function(sub_group) {
			_.each(sub_group.records, function(record) {
				item_ids.push(record.id)
			});
        });
		
        self.do_action({
            name: _t("MFG Tasks"),
            res_model: 'task.print',
            src_model: 'project.task',
            views: [[false, 'form']],
            type: 'ir.actions.act_window',
            target: 'new',
			context: {'active_ids':item_ids,'default_print_type':'by_team'}
        });
        var am = instance.webclient.action_manager;
        var form = am.dialog_widget.views.form.controller;
        form.on("on_button_cancel", am.dialog, am.dialog.close);
        form.on('record_saved', self, function() {
            am.dialog.close();
            self.view.do_reload();
        });    
    }, 
    /**
     * Handles a newly created record
     *
     * @param {id} id of the newly created record
     */
    quick_created: function (record) {
        var id = record, self = this;
        this.dataset.read_ids([id], this.view.fields_keys)
            .done(function (records) {
                self.view.dataset.ids.push(id);
                self.do_add_records(records, true);
            });
    }
});
};