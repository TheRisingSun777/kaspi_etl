.PHONY: bundle

bundle:
	./scripts/make_repo_bundle.sh

.PHONY: orders

orders:
	@echo "Running ETL for active orders..."
	@python scripts/etl_orders_api.py

.PHONY: size-recs

size-recs:
	@echo "Linking orders with size recommendations..."
	@python scripts/link_orders_and_sizes.py
