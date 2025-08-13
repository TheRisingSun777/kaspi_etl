.PHONY: bundle

bundle:
	./scripts/make_repo_bundle.sh

.PHONY: group-labels

group-labels:
	@echo "Grouping Kaspi label PDFs by SKU and size..."
	@./venv/bin/python scripts/crm_kaspi_labels_group.py --input "$(INPUT)" ${PROCESSED:+--processed $(PROCESSED)} ${OUT_DATE:+--out-date $(OUT_DATE)}
