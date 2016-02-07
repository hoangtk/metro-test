openerp.web_kanban_subgrp_KanbanSubGroup = function (instance) {
var _t = instance.web._t,
   _lt = instance.web._lt;
var QWeb = instance.web.qweb;
//分组控件, called by do_process_groups(),do_process_dataset()
instance.web_kanban_subgrp.KanbanSubGroup = instance.web.Widget.extend({
    template: 'KanbanView_subgrp.subgroup',
    //调用此处代码:do_process_groups():groups_array[index] = new instance.web_kanban_subgrp.KanbanGroup(self, records, group, dataset);
    init: function (parent, records, group, dataset) {
        var self = this;
        this._super(parent);
        this.$has_been_started = $.Deferred();
        this.view = parent.view;
        this.group = group;
        this.dataset = dataset;
        this.dataset_offset = 0;
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
			this.title1 = group.title1
			this.title2 = group.title2
			this.title3 = group.title3
            //统计字段数据
            _.each(this.view.aggregates, function(value, key) {
                self.aggregates[value] = group.get('aggregates')[key];
            });
        }

        if (this.title === false) {
            this.title = _t('Undefined');
            this.undefined_title = true;
        }
        var key = this.view.sub_group_by + '-' + this.value;
        if (!this.view.state.subgrps[key]) {
            this.view.state.subgrps[key] = {
                folded: group ? group.get('folded') : false
            };
        }
        this.state = this.view.state.subgrps[key];
        this.$records = null;

        this.records = [];
        this.$has_been_started.done(function() {
            //添加组下面的每行数据
            self.do_add_records(records);
        });
    },
	
    start: function() {
        var self = this,
            def = this._super();
        this.$records = this.$('.oe_kanban_column_cards');
        this.$records.click(function (ev) {
            if (ev.target == ev.currentTarget) {
                if (!self.state.folded) {
                    add_btn.openerpBounce();
                }
            }
        });		
        this.$el.on('click', '.oe_kanban_subgroup_list', function(ev) {
			self.$('.oe_kanban_subgroup_list .oe_tag').toggle();
			self.$('.oe_kanban_column_cards').toggle();
        });
		this.$el.data('widget', this);
        this.$has_been_started.resolve();
        this.is_started = true;
		this.view.on_subgroup_started(this)
        return def;
    },
	
    compute_cards_auto_height: function() {
        // oe_kanban_no_auto_height is an empty class used to disable this feature
        if (!this.view.group_by) {
            var min_height = 0;
            var els = [];
            _.each(this.records, function(r) {
                var $e = r.$el.children(':first:not(.oe_kanban_no_auto_height)').css('min-height', 0);
                if ($e.length) {
                    els.push($e[0]);
                    min_height = Math.max(min_height, $e.outerHeight());
                }
            });
            $(els).css('min-height', min_height);
        }
    },
    destroy: function() {
        this._super();
        if (this.$records) {
            this.$records.remove();
        }
    },
    do_show_more: function(evt) {
        var self = this;
        var ids = self.view.dataset.ids.splice(0);
        return this.dataset.read_slice(this.view.fields_keys.concat(['__last_update']), {
            'limit': self.view.limit,
            'offset': self.dataset_offset += self.view.limit
        }).then(function(records) {
            self.view.dataset.ids = ids.concat(self.dataset.ids);
            self.do_add_records(records);
            self.compute_cards_auto_height();
            self.view.postprocess_m2m_tags();
            return records;
        });
    },
    //添加每组下面的记录
    do_add_records: function(records, prepend) {
        var self = this;
        var $show_more = this.$('.oe_kanban_show_more');
        var $cards = this.$('.oe_kanban_column_cards');

        _.each(records, function(record) {
            //创建实例,调用init()
            var rec = new instance.web_kanban_subgrp.KanbanRecord(self, record);
            if (!prepend) {
                //添加到界面,调用start()
                rec.appendTo($cards);
                self.records.push(rec);
            } else {
                rec.prependTo($cards);
                self.records.unshift(rec);
            }
			if (!self.title1) {
				self.title1 = rec.record.name
				self.title2 = rec.record.state
				self.title1 = rec.record.product
			}
        });
        if ($show_more.length) {
            var size = this.dataset.size();
            $show_more.toggle(this.records.length < size).find('.oe_kanban_remaining').text(size - this.records.length);
        }
    },
    remove_record: function(id, remove_from_dataset) {
        for (var i = 0; i < this.records.length; i++) {
            if (this.records[i]['id'] === id) {
                this.records.splice(i, 1);
                i--;
            }
        }
    },
    do_save_sequences: function() {
        var self = this;
        if (_.indexOf(this.view.fields_keys, 'sequence') > -1) {
            var new_sequence = _.pluck(this.records, 'id');
            self.view.dataset.resequence(new_sequence);
        }
    },		
});
};