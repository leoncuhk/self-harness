# model-library source reference

The inspected checkout was clean and exactly matched its public upstream, so a
second 5.7 MB source copy would add redundancy without preserving unique data.

- Repository: <https://github.com/vals-ai/model-library.git>
- Commit: `b0cd8732c1ebc7cb901935b6aaf4b86c3d43d400`
- Tag: `v0.1.29`
- Inspected: 2026-08-15
- Working tree: clean

The FAB v2 evaluator environment currently pins the published package
`model-library==0.1.25`; the newer checkout was used only as reference material.
Recreate the inspected source with:

```bash
git clone https://github.com/vals-ai/model-library.git
git -C model-library checkout b0cd8732c1ebc7cb901935b6aaf4b86c3d43d400
```

