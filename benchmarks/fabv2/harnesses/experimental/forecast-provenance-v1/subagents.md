The root agent owns the obligation checklist, arithmetic, verification, and final submission. Delegate only independent retrieval branches that would otherwise compete for root context, such as two unrelated companies or a filing lookup versus a price series.

Use at most two concurrent specialist children through Prime's preloaded `rlm` callable. Each call returns an admission handle, not an answer. Give each child one bounded question, required period and definition, and explicitly require it to reply with:

`await agent_message.send(message, receiver_role="parent")`

The reply must contain value, unit, date, primary URL, supporting excerpt, and uncertainty. Example:

```python
left = await rlm("Find only CRWD FY2023/FY2025 revenue; reply to parent with values, periods, units, direct filing URLs, excerpts, and uncertainty.", name="crwd-research")
right = await rlm("Find only PANW FY2023/FY2025 revenue; reply to parent with values, periods, units, direct filing URLs, excerpts, and uncertainty.", name="panw-research")
```

End the turn after admission; child replies arrive as later parent messages. Continue useful root work rather than polling. Do not delegate final synthesis, spawn nested children, or duplicate a lookup. Reconcile every returned fact before use. All child usage is attributed to the parent budget.
