# Test Spec — StorageTracker — Sprint02_ShoppingTasks

## Scope
Tests cover shopping task CRUD, auto-task creation on item state transitions, task completion item-state reset logic, and the by_source grouped view. Item CRUD from Sprint01 is out of scope for this spec (covered by test_items.py).

## Scenarios

### Manual Task Creation
- **Given:** A fixture item 'stored_item' exists with state=stored and source_tags=['Rewe']
- **When:** POST /api/shopping-tasks with body {item_id: stored_item.id}
- **Then:** Response is 201 with Dataset containing one ShoppingTaskRow; task status=open; task source_tags=['Rewe']; task.completed_at is null

### Duplicate Open Task Rejected
- **Given:** A fixture item 'low_stock_item' has an existing open shopping task 'open_task'
- **When:** POST /api/shopping-tasks with body {item_id: low_stock_item.id}
- **Then:** Response is 409 ApiError

### Auto Task Creation On Low Stock Transition
- **Given:** A fixture item 'watch_item' exists with state=stored and no open shopping task
- **When:** PATCH /api/items/{watch_item.id} with body {state: 'low_stock'}
- **Then:** GET /api/shopping-tasks?status=open returns a task for watch_item; task.source_tags matches watch_item.source_tags at time of patch

### Auto Task Not Duplicated On Repeated Low Stock
- **Given:** A fixture item 'low_stock_item' with state=low_stock and an existing open task 'open_task'
- **When:** PATCH /api/items/{low_stock_item.id} with body {notes: 'updated notes'} (state remains low_stock)
- **Then:** GET /api/shopping-tasks?status=open returns exactly one task for low_stock_item (no duplicate created)

### Task Done With Restock Quantity
- **Given:** A fixture item 'milk' exists with quantity=1, min_quantity=3, restock_quantity=6; an open task 'milk_task' exists for milk
- **When:** PATCH /api/shopping-tasks/{milk_task.id} with body {status: 'done'}
- **Then:** task.status=done; task.completed_at is not null; item.quantity=6; item.state=stored (since 6 > 3)

### Task Done Restock Still Low Stock
- **Given:** A fixture item 'low_restock_item' exists with quantity=1, min_quantity=5, restock_quantity=4; an open task exists for it
- **When:** PATCH /api/shopping-tasks/{task.id} with body {status: 'done'}
- **Then:** task.status=done; item.quantity=4; item.state=low_stock (since 4 <= 5); item.state is NOT set to stored

### Task Done Without Restock Quantity
- **Given:** A fixture item 'cable' exists with item_type=object, no quantity tracking, state=out_of_stock; an open task 'cable_task' exists for it
- **When:** PATCH /api/shopping-tasks/{cable_task.id} with body {status: 'done'}
- **Then:** task.status=done; task.completed_at is not null; item.state=stored; item.quantity unchanged (null)

### Task Dismissed
- **Given:** An open task 'dismiss_task' exists for item 'dismiss_item' with state=low_stock
- **When:** PATCH /api/shopping-tasks/{dismiss_task.id} with body {status: 'dismissed'}
- **Then:** task.status=dismissed; task.completed_at is not null; dismiss_item.state unchanged (still low_stock)

### List Tasks Default Open
- **Given:** Fixture tasks exist: one open, one done, one dismissed
- **When:** GET /api/shopping-tasks (no params)
- **Then:** Dataset contains only the open task; done and dismissed tasks not included

### List Tasks By Status Done
- **Given:** Same fixture tasks as above
- **When:** GET /api/shopping-tasks?status=done
- **Then:** Dataset contains only the done task

### By Source Grouping No Tags
- **Given:** An open task 'notag_task' exists for an item with source_tags=[]
- **When:** GET /api/shopping-tasks/views/by_source
- **Then:** Dataset contains a row with source_tag='Other' that includes notag_task

### By Source Grouping Single Tag
- **Given:** An open task 'rewe_task' exists for an item with source_tags=['Rewe']
- **When:** GET /api/shopping-tasks/views/by_source
- **Then:** Dataset contains a row with source_tag='Rewe' that includes rewe_task

### By Source Multi Tag Duplication
- **Given:** An open task 'multi_task' exists for an item with source_tags=['Rewe', 'Amazon']
- **When:** GET /api/shopping-tasks/views/by_source
- **Then:** multi_task appears in both the 'Rewe' group and the 'Amazon' group

### Delete Task
- **Given:** An open task 'delete_task' exists
- **When:** DELETE /api/shopping-tasks/{delete_task.id}
- **Then:** Response is 200 with empty Dataset; subsequent GET /api/shopping-tasks does not include delete_task

### Delete Nonexistent Task
- **Given:** Task id 'fix-nonexistent-task' does not exist
- **When:** DELETE /api/shopping-tasks/fix-nonexistent-task
- **Then:** Response is 404 ApiError

### Item Delete Cascades To Tasks
- **Given:** An item 'cascade_item' exists with an open shopping task
- **When:** DELETE /api/items/{cascade_item.id}
- **Then:** Response is 200 with empty Dataset; GET /api/shopping-tasks shows no task for cascade_item
