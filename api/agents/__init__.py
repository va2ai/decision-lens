"""Agents — one Python module per pipeline stage.

Every agent exports:
  - PROMPT_VERSION: str           # bumped when the prompt changes
  - run(context, *, client) -> X  # pure function returning a typed output
"""
