/*############################################################################
#
#    TreeView Copy Buttons
#    Copyright 2013 wangbuke <wangbuke@gmail.com>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
############################################################################*/

openerp.web_treeview_copy = function(instance) {

    instance.web.form.One2ManyListView = instance.web.form.One2ManyListView.extend({
        do_copy_record: function (record) {
            var self = this;
            if (record) {
                self.$el.find('table:first').show();
                self.$el.find('.oe_view_nocontent').remove();
                var new_record_id =_.uniqueId(self.dataset.virtual_id_prefix); 
                var new_record = self.make_empty_record(false);
                new_record.attributes = _.clone(record.attributes);
                new_record.attributes.id = new_record_id;
                var data = _.clone(new_record.attributes), options = {};
                delete data.id;
                _.each(data, function(value, name) {
                    if (value instanceof Array &&  (value.length == 2) &&  value[0] && value[1]){
                        data[name] = value[0];
                    }
                });
                var cached = {
                    id: new_record_id,
                    values: _.extend({}, data, (options || {}).readonly_fields || {}),
                    defaults:{}
                };
                self.dataset.to_create.push(_.extend(_.clone(cached), {values: _.clone(data)}));
                self.dataset.cache.push(cached);
                //for new oe7 version
                //self.dataset.remove_ids([new_record_id]);
                //for old oe7 version
                self.dataset.alter_ids(_(self.dataset.ids).difference([new_record_id]));
                self.dataset.ids.push(new_record_id);
                self.records.add(new_record, {at: self.records.length});
                // set edit state
                //self.start_edition(new_record);
                self.$el.find('[data-id=' + new_record_id + ']').click();
            }
        },
    });

    instance.web.ListView.List.include({
        init: function () {
            this._super.apply(this, arguments);
            var self = this;
            self.$current = self.$current.delegate('td.oe_list_record_copy button', 'click', function (e) {
                e.stopPropagation();
                var $target = $(e.target), 
                    $row = $target.closest('tr'), 
                    record_id = self.row_id($row),
                    record = self.records.get(record_id);

                self.view.do_copy_record(record);
            })
            .delegate('td.oe_list_record_delete_multi button', 'click', function (e) {
                e.stopPropagation();
                var $row = $(e.target).closest('tr');
                if (self.get_selection().ids == undefined || !self.get_selection().ids.length){
                	alert("Please select records to delete!")                
                    return;	
                }                	
                if (!confirm(_t("Do you really want to remove the selected records?"))) {
                     return;
                }                
                $(self).trigger('deleted', [self.get_selection().ids]);           
            });
        },
    });

};

// vim:et fdc=0 fdl=0 foldnestmax=3 fdm=syntax:
