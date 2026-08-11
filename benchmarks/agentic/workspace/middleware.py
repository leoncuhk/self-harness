"""Editable middleware surface.

Contract: define MIDDLEWARE as a list of LangChain agent middleware objects
(e.g. functions decorated with @wrap_tool_call / @wrap_model_call from
langchain.agents.middleware). They are passed to create_deep_agent(middleware=...).
Leave empty for none.
"""

MIDDLEWARE: list = []