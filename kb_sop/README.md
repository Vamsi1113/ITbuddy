# Organisation SOPs

Tobi answers "what is the rule?" questions and (from Phase 2) checks actions against the SOPs in this folder.
Only the SOPs that apply to the user's ODC and security groups are used, and every answer cites the SOP id, version
and section.

The three SOPs here are **samples** for the demo ODCs `HYD-ODC-2` and `PUNE-ODC-1` (see `organisation.odcs` in
`config.yaml`). Replace them with your organisation's real SOPs.

## Adding an SOP

Supported formats: Markdown (`.md`), Word (`.docx`) and PDF (`.pdf`). Each SOP needs this metadata, as front matter
at the top of a Markdown file, or in a side file with the same name ending in `.yaml` for Word and PDF:

```yaml
sop_id: SOP-IT-PRN-004          # required, unique
title: Printing in Hyderabad ODC 2
version: "3.1"
effective_date: 2026-09-01
owner: IT Service Desk
odc: [HYD-ODC-2]                # or "all"
department: all
access_groups: []               # empty = everyone
status: approved                # "draft" SOPs are never used in answers
```

Use `##` headings (or Word "Heading 2") for sections: each section is cited separately. Tobi re-indexes changed
SOPs when it starts; to do it now run `python scripts/init_rag.py`.
