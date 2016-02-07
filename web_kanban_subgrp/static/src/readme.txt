1.增加instance.web_kanban_subgrp.KanbanSubGroup
KanbanSubGroup上面属于instance.web_kanban_subgrp.KanbanGroup,下面包含instance.web_kanban_subgrp.KanbanRecord
it is to add the SubGruop between the original KanbanGroup and KanbanRecord

Add 'sub_group_by' to kanban_subgrp view xml

<kanban_subgrp default_group_by="dept_id" sub_group_by="production_id" quick_create="0">