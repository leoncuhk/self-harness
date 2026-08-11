"""Editable tool surface.

Contract: define make_tools(task_root: str) -> list of LangChain tools. They are
added to the agent alongside its built-in filesystem tools (ls, read_file,
write_file, edit_file), which are always available and rooted at the task
directory. Return [] for no extra tools.
"""


def make_tools(task_root: str) -> list:
    del task_root
    return []