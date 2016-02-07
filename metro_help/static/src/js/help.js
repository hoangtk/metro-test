
openerp.metro_help = function(session) {

session.web.ViewManagerAction.include({
    start: function() {
        var self = this;
        self.$el.find('a.model_help').click(self.on_click_help_link);
        return this._super.apply(this, arguments);
    },
    on_click_help_link: function(e) {
        e.preventDefault();
        window.open('/?ts=1394867466091#id=1&view_type=form&model=document.page&menu_id=530&action=650');
    },
});

};

