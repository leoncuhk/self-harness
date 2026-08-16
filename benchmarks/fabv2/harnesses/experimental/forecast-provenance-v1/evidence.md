Maintain `evidence.json` as compact computational memory. Use this shape:

```json
{
  "obligations": [{"id": "O1", "need": "...", "status": "open|supported|blocked"}],
  "facts": [{"id": "F1", "value": "...", "unit": "...", "period": "...", "source": "URL", "quote": "short supporting context"}],
  "calculations": [{"id": "C1", "expression": "...", "result": "...", "inputs": ["F1"]}],
  "risks": ["definition, date, unit, or missing-evidence concern"]
}
```

Update rather than duplicate facts. Keep excerpts short. A fact is supported only when its source, period, unit, and meaning are all recorded. This file is working memory, not the final response.
