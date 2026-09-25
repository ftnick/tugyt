# Repository Agent Instructions

## Git Workflow

- After making a code or configuration update, create a local git commit grouped by the purpose of the change.
- Never push commits to a remote unless the user explicitly asks for a push.
- Before committing, run the narrowest relevant validation and report any failures.
- Do not combine unrelated fixes into one commit.

## Version Reminder

- Before finishing work that changes package behavior or release metadata, remind the user to update `__version__` in `ytget/ytget.py` when appropriate.
- The current version is defined by `__version__` in `ytget/ytget.py`.
