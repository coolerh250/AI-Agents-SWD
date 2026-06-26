# Delivery-package / Project Linkage (Step 57)

Links a delivery package to project_id / work_item_id / dispatch_id with an acceptance
status (pending / operator_review / accepted_nonproduction / rejected). See
[`infra/delivery/delivery-package-project-linkage.yaml`](../../infra/delivery/delivery-package-project-linkage.yaml).

Load-bearing invariants: delivery-package-ready ≠ production approval; work-item
completed ≠ human acceptance; human acceptance ≠ deployment approval; project completed
≠ production release. `productionReady=false`.
