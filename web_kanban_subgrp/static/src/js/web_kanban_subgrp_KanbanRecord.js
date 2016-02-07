openerp.web_kanban_subgrp_KanbanRecord = function (instance) {
var _t = instance.web._t,
   _lt = instance.web._lt;
var QWeb = instance.web.qweb;
instance.web_kanban_subgrp.KanbanRecord = instance.web.Widget.extend({
    template: 'KanbanView_subgrp.record',
    init: function (parent, record) {
        this._super(parent);
        this.group = parent;
        this.view = parent.view;
        this.id = null;
        this.set_record(record);
        if (!this.view.state.records[this.id]) {
            this.view.state.records[this.id] = {
                folded: false
            };
        }
        this.state = this.view.state.records[this.id];
    },
    set_record: function(record) {
        var self = this;
        this.id = record.id;
        this.values = {};
        _.each(record, function(v, k) {
            self.values[k] = {
                value: v
            };
        });
        this.record = this.transform_record(record);
    },
    start: function() {
        this._super();
        this.$el.data('widget', this);
        this.bind_events();
    },
    transform_record: function(record) {
        var self = this,
            new_record = {};
        _.each(record, function(value, name) {
            var r = _.clone(self.view.fields_view.fields[name] || {});
            if ((r.type === 'date' || r.type === 'datetime') && value) {
                r.raw_value = instance.web.auto_str_to_date(value);
            } else {
                r.raw_value = value;
            }
            r.value = instance.web.format_value(value, r);
            new_record[name] = r;
        });
        return new_record;
    },
    renderElement: function() {
        this.qweb_context = {
            instance: instance,
            record: this.record,
            widget: this,
            read_only_mode: this.view.options.read_only_mode,
        };
        for (var p in this) {
            if (_.str.startsWith(p, 'kanban_')) {
                this.qweb_context[p] = _.bind(this[p], this);
            }
        }
        var $el = instance.web.qweb.render(this.template, {
            'widget': this,
            'content': this.view.qweb.render('kanban-box', this.qweb_context)
        });
        this.replaceElement($el);
    },
    bind_events: function() {
        var self = this;
        this.setup_color_picker();
        this.$el.find('[tooltip]').tipsy({
            delayIn: 500,
            delayOut: 0,
            fade: true,
            title: function() {
                var template = $(this).attr('tooltip');
                if (!self.view.qweb.has_template(template)) {
                    return false;
                }
                return self.view.qweb.render(template, self.qweb_context);
            },
            gravity: 's',
            html: true,
            opacity: 0.8,
            trigger: 'hover'
        });

        // If no draghandle is found, make the whole card as draghandle (provided one can edit)
        if (!this.$el.find('.oe_kanban_draghandle').length) {
            this.$el.children(':first')
                .toggleClass('oe_kanban_draghandle', this.view.is_action_enabled('edit'));
        }

        this.$el.find('.oe_kanban_action').click(function(ev) {
            ev.preventDefault();
            var $action = $(this),
                type = $action.data('type') || 'button',
                method = 'do_action_' + (type === 'action' ? 'object' : type);
            if ((type === 'edit' || type === 'delete') && ! self.view.is_action_enabled(type)) {
                self.view.open_record(self.id, true);
            } else if (_.str.startsWith(type, 'switch_')) {
                self.view.do_switch_view(type.substr(7));
            } else if (typeof self[method] === 'function') {
                self[method]($action);
            } else {
                self.do_warn("Kanban: no action for type : " + type);
            }
        });
        //for the elements click ,no need to open the record, johnw, 09/17/2014
        this.$el.find('.oe_kanban_noaction').click(function(ev) {
        	return
        });        
        if (this.$el.find('.oe_kanban_global_click,.oe_kanban_global_click_edit').length) {
            this.$el.on('click', function(ev) {
                if (!ev.isTrigger && !$._data(ev.target, 'events')) {
                    var trigger = true;
                    var elem = ev.target;
                    var ischild = true;
                    var children = [];
                    while (elem) {
                        var events = $._data(elem, 'events');
                        if (elem == ev.currentTarget) {
                            ischild = false;
                        }
                        if (ischild) {
                            children.push(elem);
                            if (events && events.click) {
                                // do not trigger global click if one child has a click event registered
                                trigger = false;
                            }
                        }
                        if (trigger && events && events.click) {
                            _.each(events.click, function(click_event) {
                                if (click_event.selector) {
                                    // For each parent of original target, check if a
                                    // delegated click is bound to any previously found children
                                    _.each(children, function(child) {
                                        if ($(child).is(click_event.selector)) {
                                            trigger = false;
                                        }
                                    });
                                }
                            });
                        }
                        elem = elem.parentElement;
                    }
                    if (trigger) {
                        self.on_card_clicked(ev);
                    }
                }
            });
        }
    },
    /* actions when user click on the block with a specific class
     *  open on normal view : oe_kanban_global_click
     *  open on form/edit view : oe_kanban_global_click_edit
     */
    on_card_clicked: function(ev) {
        if(this.$el.find('.oe_kanban_global_click_edit').size()>0)
            this.do_action_edit();
        else
            this.do_action_open();
    },
    setup_color_picker: function() {
        var self = this;
        var $el = this.$el.find('ul.oe_kanban_colorpicker');
        if ($el.length) {
            $el.html(QWeb.render('KanbanColorPicker_subgroup', {
                widget: this
            }));
            $el.on('click', 'a', function(ev) {
                ev.preventDefault();
                var color_field = $(this).parents('.oe_kanban_colorpicker').first().data('field') || 'color';
                var data = {};
                data[color_field] = $(this).data('color');
                self.view.dataset.write(self.id, data, {}).done(function() {
                    self.record[color_field] = $(this).data('color');
                    self.do_reload();
                });
            });
        }
    },
    do_action_delete: function($action) {
        var self = this;
        function do_it() {
            return $.when(self.view.dataset.unlink([self.id])).done(function() {
                self.group.remove_record(self.id);
                self.destroy();
            });
        }
        if (this.view.options.confirm_on_delete) {
            if (confirm(_t("Are you sure you want to delete this record ?"))) {
                return do_it();
            }
        } else
            return do_it();
    },
    do_action_edit: function($action) {
        this.view.open_record(this.id, true);
    },
    do_action_open: function($action) {
        this.view.open_record(this.id);
    },
    do_action_object: function ($action) {
        var button_attrs = $action.data();
        this.view.do_execute_action(button_attrs, this.view.dataset, this.id, this.do_reload);
    },
    do_reload: function() {
        var self = this;
        this.view.dataset.read_ids([this.id], this.view.fields_keys.concat(['__last_update'])).done(function(records) {
            if (records.length) {
                self.set_record(records[0]);
                self.renderElement();
                self.$el.data('widget', self);
                self.bind_events();
                self.group.compute_cards_auto_height();
                self.view.postprocess_m2m_tags();
            } else {
                self.destroy();
            }
        });
    },
    kanban_getcolor: function(variable) {
        var index = 0;
        switch (typeof(variable)) {
            case 'string':
                for (var i=0, ii=variable.length; i<ii; i++) {
                    index += variable.charCodeAt(i);
                }
                break;
            case 'number':
                index = Math.round(variable);
                break;
            default:
                return '';
        }
        var color = (index % this.view.number_of_color_schemes);
        return color;
    },
    kanban_color: function(variable) {
        var color = this.kanban_getcolor(variable);
        return color === '' ? '' : 'oe_kanban_color_' + color;
    },
    kanban_gravatar: function(email, size) {
        size = size || 22;
        email = _.str.trim(email || '').toLowerCase();
        var default_ = _.str.isBlank(email) ? 'mm' : 'identicon';
        var email_md5 = $.md5(email);
        return 'http://www.gravatar.com/avatar/' + email_md5 + '.png?s=' + size + '&d=' + default_;
    },
    kanban_image: function(model, field, id, cache, options) {
        options = options || {};
        var url;
        if (this.record[field] && this.record[field].value && !instance.web.form.is_bin_size(this.record[field].value)) {
            url = 'data:image/png;base64,' + this.record[field].value;
        } else if (this.record[field] && ! this.record[field].value) {
            url = "/web/static/src/img/placeholder.png";
        } else {
            id = JSON.stringify(id);
            if (options.preview_image)
                field = options.preview_image;
            url = this.session.url('/web/binary/image', {model: model, field: field, id: id});
            if (cache !== undefined) {
                // Set the cache duration in seconds.
                url += '&cache=' + parseInt(cache, 10);
            }
        }
        return url;
    },
    kanban_text_ellipsis: function(s, size) {
        size = size || 160;
        if (!s) {
            return '';
        } else if (s.length <= size) {
            return s;
        } else {
            return s.substr(0, size) + '...';
        }
    },
    kanban_compute_domain: function(domain) {
        return instance.web.form.compute_domain(domain, this.values);
    }
});
};