openerp.web_kanban_subgrp = function (instance) {

var _t = instance.web._t,
   _lt = instance.web._lt;
var QWeb = instance.web.qweb;
instance.web.views.add('kanban_subgrp', 'instance.web_kanban_subgrp.KanbanView');

openerp.web_kanban_subgrp_KanbanGroup(instance)
openerp.web_kanban_subgrp_KanbanSubGroup(instance)
openerp.web_kanban_subgrp_KanbanRecord(instance)

instance.web_kanban_subgrp.KanbanView = instance.web.View.extend({
    template: "KanbanView_subgrp",
    display_name: _lt('Kanban'),
    default_nr_columns: 1,
    view_type: "kanban_sugrp",
    quick_create_class: "instance.web_kanban_subgrp.QuickCreate",
    number_of_color_schemes: 10,
    init: function (parent, dataset, view_id, options) {
        this._super(parent, dataset, view_id, options);
        var self = this;
        _.defaults(this.options, {
            "quick_creatable": false,
            "creatable": true,
            "create_text": undefined,
            "read_only_mode": false,
            "confirm_on_delete": true,
        });
        this.fields_view = {};
        this.fields_keys = [];
        this.group_by = null;
        this.group_by_field = {};
        this.grouped_by_m2o = false;
        this.many2manys = [];
		//ADD:sub group by fields
        this.sub_group_by = null;
        this.sub_group_by_field = {};
        //存储group和记录数据的字典
        this.state = {
            groups : {},
            subgrps: {}, //ADD:增加子分组
            records : {}
        };
        //存储KankanGroup的Widget
        this.groups = [];
        //存储汇总列名和标题
        this.aggregates = {};
        //可用的汇总列tag
        this.group_operators = ['avg', 'max', 'min', 'sum', 'count'];
        this.qweb = new QWeb2.Engine();
        this.qweb.debug = instance.session.debug;
        this.qweb.default_dict = _.clone(QWeb.default_dict);
        this.has_been_loaded = $.Deferred();
        this.search_domain = this.search_context = this.search_group_by = null;
        this.currently_dragging = {};
        //this.limit = options.limit || 40;
        //ADD:因为加入了子分组,所以将限制改为无限
        this.limit = 20000;
        this.add_group_mutex = new $.Mutex();
    },
    view_loading: function(r) {
        return this.load_kanban(r);
    },
    start: function() {
        var self = this;
        this._super.apply(this, arguments);
        this.$el.on('click', '.oe_kanban_dummy_cell', function() {
            if (self.$buttons) {
                self.$buttons.find('.oe_kanban_add_column').openerpBounce();
            }
        });
    },
    destroy: function() {
        this._super.apply(this, arguments);
        $('html').off('click.kanban');
    },
    load_kanban: function(data) {
        this.fields_view = data;
        this.$el.addClass(this.fields_view.arch.attrs['class']);
        this.$buttons = $(QWeb.render("KanbanView.buttons", {'widget': this}));
        if (this.options.$buttons) {
            this.$buttons.appendTo(this.options.$buttons);
        } else {
            this.$el.find('.oe_kanban_buttons').replaceWith(this.$buttons);
        }
        this.$buttons
            .on('click', 'button.oe_kanban_button_new', this.do_add_record)
            .on('click', '.oe_kanban_add_column', this.do_add_group);
        this.$groups = this.$el.find('.oe_kanban_groups tr');
        this.fields_keys = _.keys(this.fields_view.fields);
        this.add_qweb_template();
        this.has_been_loaded.resolve();
        this.trigger('kanban_view_loaded', data);
        return $.when();
    },
    _is_quick_create_enabled: function() {
        if (!this.options.quick_creatable || !this.is_action_enabled('create'))
            return false;
        if (this.fields_view.arch.attrs.quick_create !== undefined)
            return JSON.parse(this.fields_view.arch.attrs.quick_create);
        return !! this.group_by;
    },
    is_action_enabled: function(action) {
        if (action === 'create' && !this.options.creatable)
            return false;
        return this._super(action);
    },
    /*  add_qweb_template
    *   select the nodes into the xml and send to extract_aggregates the nodes with TagName="field"
    */
    add_qweb_template: function() {
        for (var i=0, ii=this.fields_view.arch.children.length; i < ii; i++) {
            var child = this.fields_view.arch.children[i];
            if (child.tag === "templates") {
				//增加kanban view里面定义的kanban-box template
                this.transform_qweb_template(child);
                this.qweb.add_template(instance.web.json_node_to_xml(child));
                break;
            } else if (child.tag === 'field') {
                this.extract_aggregates(child);
            }
        }
    },
    /*  extract_aggregates
    *   extract the agggregates from the nodes (TagName="field")
    */
    extract_aggregates: function(node) {
        for (var j = 0, jj = this.group_operators.length; j < jj;  j++) {
            if (node.attrs[this.group_operators[j]]) {
                this.aggregates[node.attrs.name] = node.attrs[this.group_operators[j]];
                break;
            }
        }
    },
    transform_qweb_template: function(node) {
        var qweb_add_if = function(node, condition) {
            if (node.attrs[QWeb.prefix + '-if']) {
                condition = _.str.sprintf("(%s) and (%s)", node.attrs[QWeb.prefix + '-if'], condition);
            }
            node.attrs[QWeb.prefix + '-if'] = condition;
        };
        // Process modifiers
        if (node.tag && node.attrs.modifiers) {
            var modifiers = JSON.parse(node.attrs.modifiers || '{}');
            if (modifiers.invisible) {
                qweb_add_if(node, _.str.sprintf("!kanban_compute_domain(%s)", JSON.stringify(modifiers.invisible)));
            }
        }
        switch (node.tag) {
            case 'field':
                if (this.fields_view.fields[node.attrs.name].type === 'many2many') {
                    if (_.indexOf(this.many2manys, node.attrs.name) < 0) {
                        this.many2manys.push(node.attrs.name);
                    }
                    node.tag = 'div';
                    node.attrs['class'] = (node.attrs['class'] || '') + ' oe_form_field oe_tags';
                } else {
                    node.tag = QWeb.prefix;
                    node.attrs[QWeb.prefix + '-esc'] = 'record.' + node.attrs['name'] + '.value';
                }
                break;
            case 'button':
            case 'a':
                var type = node.attrs.type || '';
                if (_.indexOf('action,object,edit,open,delete'.split(','), type) !== -1) {
                    _.each(node.attrs, function(v, k) {
                        if (_.indexOf('icon,type,name,args,string,context,states,kanban_states'.split(','), k) != -1) {
                            node.attrs['data-' + k] = v;
                            delete(node.attrs[k]);
                        }
                    });
                    if (node.attrs['data-string']) {
                        node.attrs.title = node.attrs['data-string'];
                    }
                    if (node.attrs['data-icon']) {
                        node.children = [{
                            tag: 'img',
                            attrs: {
                                src: instance.session.prefix + '/web/static/src/img/icons/' + node.attrs['data-icon'] + '.png',
                                width: '16',
                                height: '16'
                            }
                        }];
                    }
                    if (node.tag == 'a') {
                        node.attrs.href = '#';
                    } else {
                        node.attrs.type = 'button';
                    }
                    node.attrs['class'] = (node.attrs['class'] || '') + ' oe_kanban_action oe_kanban_action_' + node.tag;
                }
                break;
        }
        if (node.children) {
            for (var i = 0, ii = node.children.length; i < ii; i++) {
                this.transform_qweb_template(node.children[i]);
            }
        }
    },
    do_add_record: function() {
        this.dataset.index = null;
        this.do_switch_view('form');
    },
    do_add_group: function() {
        var self = this;
        self.do_action({
            name: _t("Add column"),
            res_model: self.group_by_field.relation,
            views: [[false, 'form']],
            type: 'ir.actions.act_window',
            target: "new",
            context: self.dataset.get_context(),
            flags: {
                action_buttons: true,
            }
        });
        var am = instance.webclient.action_manager;
        var form = am.dialog_widget.views.form.controller;
        form.on("on_button_cancel", am.dialog, am.dialog.close);
        form.on('record_created', self, function(r) {
            (new instance.web.DataSet(self, self.group_by_field.relation)).name_get([r]).done(function(new_record) {
                am.dialog.close();
                var domain = self.dataset.domain.slice(0);
                domain.push([self.group_by, '=', new_record[0][0]]);
                var dataset = new instance.web.DataSetSearch(self, self.dataset.model, self.dataset.get_context(), domain);
                var datagroup = {
                    get: function(key) {
                        return this[key];
                    },
                    value: new_record[0],
                    length: 0,
                    aggregates: {},
                };
                var new_group = new instance.web_kanban_subgrp.KanbanGroup(self, [], datagroup, dataset);
                self.do_add_groups([new_group]).done(function() {
                    $(window).scrollTo(self.groups.slice(-1)[0].$el, { axis: 'x' });
                });
            });
        });
    },
    do_search: function(domain, context, group_by) {
        var self = this;
        this.$el.find('.oe_view_nocontent').remove();
        this.search_domain = domain;
        this.search_context = context;
        this.search_group_by = group_by;
        //当QWeb装载完毕后执行此代码,完成代码在 "load_kanban():this.has_been_loaded.resolve();"
        return $.when(this.has_been_loaded).then(function() {
            //如果默认action没有传递相关group_by则使用view定义的"default_group_by"
            self.group_by = group_by.length ? group_by[0] : self.fields_view.arch.attrs.default_group_by;
            self.group_by_field = self.fields_view.fields[self.group_by] || {};
            //如果分组列是many2one类型的,则显示增加相关模型的按钮,web_kanban.xml
            self.grouped_by_m2o = (self.group_by_field.type === 'many2one');
            self.$buttons.find('.oe_alternative').toggle(self.grouped_by_m2o);
            //如果分组列是many2one类型的,则鼠标指针图标改为移动类型,见kanban.css
            self.$el.toggleClass('oe_kanban_grouped_by_m2o', self.grouped_by_m2o);
            //根据groups执行查询和分组
            var grouping_fields = self.group_by ? [self.group_by].concat(_.keys(self.aggregates)) : undefined;
            var grouping = new instance.web.Model(self.dataset.model, context, domain).query().group_by(grouping_fields);            
            return self.alive($.when(grouping)).done(function(groups) {
                //处理分组数据
                if (groups) {
                    //分组处理,例如任务按照状态显示
                    self.do_process_groups(groups);
                } else {
                    //不分组,例如雇员的Kanban视图
                    self.do_process_dataset();
                }
            });
        });
    },
    do_process_groups: function(groups) {
        var self = this;
        this.$el.removeClass('oe_kanban_ungrouped').addClass('oe_kanban_grouped');
        this.add_group_mutex.exec(function() {
            self.do_clear_groups();
            self.dataset.ids = [];
            if (!groups.length) {
                self.no_result();
                return false;
            }
            var remaining = groups.length - 1,
                groups_array = [];
            return $.when.apply(null, _.map(groups, function (group, index) {
                //读取分组的明细数据,添加到dataset中
                var dataset = new instance.web.DataSetSearch(self, self.dataset.model,
                    new instance.web.CompoundContext(self.dataset.get_context(), group.model.context()), group.model.domain());
                dataset.read_slice(self.fields_keys.concat(['__last_update']), { 'limit': self.limit })
                    .then(function(records) {
                        self.dataset.ids.push.apply(self.dataset.ids, dataset.ids);
                });
                //读取分组的子分组数据
				//console.log(self.fields_view.arch.attrs.sub_group_by);
				self.sub_group_by = self.fields_view.arch.attrs.sub_group_by;
				self.sub_group_by_field = self.fields_view.fields[self.sub_group_by] || {};				
				var sub_grouping = new instance.web.Model(self.dataset.model, 
					new instance.web.CompoundContext(self.dataset.get_context(), group.model.context()), 
					group.model.domain())
					.query().group_by(self.sub_group_by);
				return self.alive($.when(sub_grouping)).done(function(sub_groups) {
					//添加'组'的Widget到数组
					groups_array[index] = new instance.web_kanban_subgrp.KanbanGroup(self, sub_groups, group);

					if (!remaining--) {
						self.dataset.index = self.dataset.size() ? 0 : null;
						//所有组处理完毕后,添加所有组的Widgets到界面
						return self.do_add_groups(groups_array);					
					}	
				});				
				
            }));
        });
    },
    do_process_dataset: function() {
        var self = this;
        this.$el.removeClass('oe_kanban_grouped').addClass('oe_kanban_ungrouped');
        this.add_group_mutex.exec(function() {
            var def = $.Deferred();
            self.do_clear_groups();
            self.dataset.read_slice(self.fields_keys.concat(['__last_update']), { 'limit': self.limit }).done(function(records) {
                var kgroup = new instance.web_kanban_subgrp.KanbanGroup(self, records, null, self.dataset);
                self.do_add_groups([kgroup]).done(function() {
                    if (_.isEmpty(records)) {
                        self.no_result();
                    }
                    def.resolve();
                });
            }).done(null, function() {
                def.reject();
            });
            return def;
        });
    },
    do_reload: function() {
        this.do_search(this.search_domain, this.search_context, this.search_group_by);
    },
    do_clear_groups: function() {
        var groups = this.groups.slice(0);
        this.groups = [];
        _.each(groups, function(group) {
            group.destroy();
        });
    },
    do_add_groups: function(groups) {
        var self = this;
        var $parent = this.$el.parent();
        //清空当前页面
        this.$el.detach();
        _.each(groups, function(group) {
            self.groups[group.undefined_title ? 'unshift' : 'push'](group);
        });
        var $last_td = self.$el.find('.oe_kanban_groups_headers td:last');
        var groups_started = _.map(this.groups, function(group) {
            if (!group.is_started) {
                //添加组到界面
                return group.insertBefore($last_td);
            }
        });
        return $.when.apply(null, groups_started).done(function () {
            //增加组和卡片的可拖动代码
            self.on_groups_started();
            self.$el.appendTo($parent);
            _.each(self.groups, function(group) {
                //计算组下每个card的高度
				_.each(group.sub_groups, function(sub_group) {
					sub_group.compute_cards_auto_height();
				});
            });
        });
    },
    on_subgroup_started: function(container) {
        var self = this;
        if (this.group_by) {
            // Kanban cards drag'n'drop
            var $columns = container.$('.oe_kanban_column_cards');
            $columns.sortable({
                handle : '.oe_kanban_draghandle',
                start: function(event, ui) {
                    self.currently_dragging.index = ui.item.parent().children('.oe_kanban_record').index(ui.item);
                    self.currently_dragging.group = ui.item.parents('.oe_kanban_column:first').data('widget');
					self.currently_dragging.sub_group = ui.item.parents('.oe_kanban_subgroup:first').data('widget');
                    ui.item.find('*').on('click.prevent', function(ev) {
                        return false;
                    });
                    ui.placeholder.height(ui.item.height());
                },
                revert: 150,
                stop: function(event, ui) {
                    var record = ui.item.data('widget');
                    var old_index = self.currently_dragging.index;
                    var new_index = ui.item.parent().children('.oe_kanban_record').index(ui.item);
                    var old_group = self.currently_dragging.group;
                    var new_group = ui.item.parents('.oe_kanban_column:first').data('widget');
                    var old_sub_group = self.currently_dragging.sub_group;
                    var new_sub_group = ui.item.parents('.oe_kanban_subgroup:first').data('widget');
                    if (!(old_group.title === new_group.title && old_group.value === new_group.value && old_index == new_index)) {
                        self.on_sub_group_record_moved(record, old_group, old_sub_group, old_index, new_group, new_sub_group, new_index);
                    }
                    setTimeout(function() {
                        // A bit hacky but could not find a better solution for Firefox (problem not present in chrome)
                        // http://stackoverflow.com/questions/274843/preventing-javascript-click-event-with-scriptaculous-drag-and-drop
                        ui.item.find('*').off('click.prevent');
                    }, 0);
                },
                scroll: false
            });
		};
	},		
    on_sub_group_record_moved : function(record, old_group, old_sub_group, old_index, new_group, new_sub_group, new_index) {
        var self = this;
        $.fn.tipsy.clear();
        $(old_group.$el).add(new_group.$el).find('.oe_kanban_aggregates, .oe_kanban_group_length').hide();
        if (old_group === new_group) {
            new_sub_group.records.splice(old_index, 1);
            new_sub_group.records.splice(new_index, 0, record);
            new_sub_group.do_save_sequences();
        } else {
            old_sub_group.records.splice(old_index, 1);
            new_sub_group.records.splice(new_index, 0, record);
            record.group = new_sub_group;
            var data = {};
            data[this.group_by] = new_group.value;
            this.dataset.write(record.id, data, {}).done(function() {
                record.do_reload();
                new_sub_group.do_save_sequences();
            }).fail(function(error, evt) {
                evt.preventDefault();
                alert(_t("An error has occured while moving the record to this group: ") + data.fault_code);
                self.do_reload(); // TODO: use draggable + sortable in order to cancel the dragging when the rcp fails
            });
        }
    },	
    on_groups_started: function() {
        var self = this;
        if (this.group_by) {
            // Kanban cards drag'n'drop
            var $columns = this.$el.find('.oe_kanban_column .oe_kanban_column_cards');
            $columns.sortable({
                handle : '.oe_kanban_draghandle',
                start: function(event, ui) {
                    self.currently_dragging.index = ui.item.parent().children('.oe_kanban_record').index(ui.item);
                    self.currently_dragging.group = ui.item.parents('.oe_kanban_column:first').data('widget');
                    ui.item.find('*').on('click.prevent', function(ev) {
                        return false;
                    });
                    ui.placeholder.height(ui.item.height());
                },
                revert: 150,
                stop: function(event, ui) {
                    var record = ui.item.data('widget');
                    var old_index = self.currently_dragging.index;
                    var new_index = ui.item.parent().children('.oe_kanban_record').index(ui.item);
                    var old_group = self.currently_dragging.group;
                    var new_group = ui.item.parents('.oe_kanban_column:first').data('widget');
                    if (!(old_group.title === new_group.title && old_group.value === new_group.value && old_index == new_index)) {
                        self.on_record_moved(record, old_group, old_index, new_group, new_index);
                    }
                    setTimeout(function() {
                        // A bit hacky but could not find a better solution for Firefox (problem not present in chrome)
                        // http://stackoverflow.com/questions/274843/preventing-javascript-click-event-with-scriptaculous-drag-and-drop
                        ui.item.find('*').off('click.prevent');
                    }, 0);
                },
                scroll: false
            });
            // Keep connectWith out of the sortable initialization for performance sake:
            // http://www.planbox.com/blog/development/coding/jquery-ui-sortable-slow-to-bind.html
            $columns.sortable({ connectWith: $columns });

            // Kanban groups drag'n'drop
            var start_index;
            if (this.grouped_by_m2o) {
                this.$('.oe_kanban_groups_headers').sortable({
                    items: '.oe_kanban_group_header',
                    helper: 'clone',
                    axis: 'x',
                    opacity: 0.5,
                    scroll: false,
                    start: function(event, ui) {
                        start_index = ui.item.index();
                        self.$('.oe_kanban_record, .oe_kanban_quick_create').css({ visibility: 'hidden' });
                    },
                    stop: function(event, ui) {
                        var stop_index = ui.item.index();
                        if (start_index !== stop_index) {
                            var $start_column = $('.oe_kanban_groups_records .oe_kanban_column').eq(start_index);
                            var $stop_column = $('.oe_kanban_groups_records .oe_kanban_column').eq(stop_index);
                            var method = (start_index > stop_index) ? 'insertBefore' : 'insertAfter';
                            $start_column[method]($stop_column);
                            var tmp_group = self.groups.splice(start_index, 1)[0];
                            self.groups.splice(stop_index, 0, tmp_group);
                            var new_sequence = _.pluck(self.groups, 'value');
                            (new instance.web.DataSet(self, self.group_by_field.relation)).resequence(new_sequence).done(function(r) {
                                if (r === false) {
                                    console.error("Kanban: could not resequence model '%s'. Probably no 'sequence' field.", self.group_by_field.relation);
                                }
                            });
                        }
                        self.$('.oe_kanban_record, .oe_kanban_quick_create').css({ visibility: 'visible' });
                    }
                });
            }
        } else {
            this.$el.find('.oe_kanban_draghandle').removeClass('oe_kanban_draghandle');
        }
        this.postprocess_m2m_tags();
    },
    on_record_moved : function(record, old_group, old_index, new_group, new_index) {
        var self = this;
        $.fn.tipsy.clear();
        $(old_group.$el).add(new_group.$el).find('.oe_kanban_aggregates, .oe_kanban_group_length').hide();
        if (old_group === new_group) {
            new_group.records.splice(old_index, 1);
            new_group.records.splice(new_index, 0, record);
            new_group.do_save_sequences();
        } else {
            old_group.records.splice(old_index, 1);
            new_group.records.splice(new_index, 0, record);
            record.group = new_group;
            var data = {};
            data[this.group_by] = new_group.value;
            this.dataset.write(record.id, data, {}).done(function() {
                record.do_reload();
                new_group.do_save_sequences();
            }).fail(function(error, evt) {
                evt.preventDefault();
                alert(_t("An error has occured while moving the record to this group: ") + data.fault_code);
                self.do_reload(); // TODO: use draggable + sortable in order to cancel the dragging when the rcp fails
            });
        }
    },

    do_show: function() {
        if (this.$buttons) {
            this.$buttons.show();
        }
        this.do_push_state({});
        return this._super();
    },
    do_hide: function () {
        if (this.$buttons) {
            this.$buttons.hide();
        }
        return this._super();
    },
    open_record: function(id, editable) {
        if (this.dataset.select_id(id)) {
            this.do_switch_view('form', null, { mode: editable ? "edit" : undefined });
        } else {
            this.do_warn("Kanban: could not find id#" + id);
        }
    },
    no_result: function() {
        if (this.groups.group_by
            || !this.options.action
            || !this.options.action.help) {
            return;
        }
        this.$el.find('.oe_view_nocontent').remove();
        this.$el.prepend(
            $('<div class="oe_view_nocontent">').html(this.options.action.help)
        );
        var create_nocontent = this.$buttons;
        this.$el.find('.oe_view_nocontent').click(function() {
            create_nocontent.openerpBounce();
        });
    },

    /*
    *  postprocessing of fields type many2many
    *  make the rpc request for all ids/model and insert value inside .oe_tags fields
    */
    postprocess_m2m_tags: function() {
        var self = this;
        if (!this.many2manys.length) {
            return;
        }
        var relations = {};
        this.groups.forEach(function(group) {
			group.sub_groups.forEach(function(sub_group) {
				sub_group.records.forEach(function(record) {
					self.many2manys.forEach(function(name) {
						var field = record.record[name];
						var $el = record.$('.oe_form_field.oe_tags[name=' + name + ']').empty();
						if (!relations[field.relation]) {
							relations[field.relation] = { ids: [], elements: {}};
						}
						var rel = relations[field.relation];
						field.raw_value.forEach(function(id) {
							rel.ids.push(id);
							if (!rel.elements[id]) {
								rel.elements[id] = [];
							}
							rel.elements[id].push($el[0]);
						});
					});
				});
			});
        });
       _.each(relations, function(rel, rel_name) {
            var dataset = new instance.web.DataSetSearch(self, rel_name, self.dataset.get_context());
            dataset.name_get(_.uniq(rel.ids)).done(function(result) {
                result.forEach(function(nameget) {
                    $(rel.elements[nameget[0]]).append('<span class="oe_tag">' + _.str.escapeHTML(nameget[1]) + '</span>');
                });
            });
        });
    }
});


function get_class(name) {
    return new instance.web.Registry({'tmp' : name}).get_object("tmp");
}

/**
 * Quick creation view.
 *
 * Triggers a single event "added" with a single parameter "name", which is the
 * name entered by the user
 *
 * @class
 * @type {*}
 */
instance.web_kanban_subgrp.QuickCreate = instance.web.Widget.extend({
    template: 'KanbanView_subgroup.quick_create',
    
    /**
     * close_btn: If true, the widget will display a "Close" button able to trigger
     * a "close" event.
     */
    init: function(parent, dataset, context, buttons) {
        this._super(parent);
        this._dataset = dataset;
        this._buttons = buttons || false;
        this._context = context || {};
    },
    start: function () {
        var self = this;
        self.$input = this.$el.find('input');
        self.$input.keyup(function(event){
            if(event.keyCode == 13){
                self.quick_add();
            }
        });
        $(".oe_kanban_quick_create_add", this.$el).click(function () {
            self.quick_add();
            self.focus();
        });
        $(".oe_kanban_quick_create_close", this.$el).click(function (ev) {
            ev.preventDefault();
            self.trigger('close');
        });
        self.$input.keyup(function(e) {
            if (e.keyCode == 27 && self._buttons) {
                self.trigger('close');
            }
        });
    },
    focus: function() {
        this.$el.find('input').focus();
    },
    /**
     * Handles user event from nested quick creation view
     */
    quick_add: function () {
        var self = this;
        var val = this.$input.val();
        if (/^\s*$/.test(val)) { return; }
        this._dataset.call(
            'name_create', [val, new instance.web.CompoundContext(
                    this._dataset.get_context(), this._context)])
            .then(function(record) {
                self.$input.val("");
                self.trigger('added', record[0]);
            }, function(error, event) {
                event.preventDefault();
                return self.slow_create();
            });
    },
    slow_create: function() {
        var self = this;
        var pop = new instance.web.form.SelectCreatePopup(this);
        pop.select_element(
            self._dataset.model,
            {
                title: _t("Create: ") + (this.string || this.name),
                initial_view: "form",
                disable_multiple_selection: true
            },
            [],
            {"default_name": self.$input.val()}
        );
        pop.on("elements_selected", self, function(element_ids) {
            self.$input.val("");
            self.trigger('added', element_ids[0]);
        });
    }
});
};

// vim:et fdc=0 fdl=0 foldnestmax=3 fdm=syntax:
