## Summary

<!-- What does this PR change, and why? -->

## Changelog

- [ ] I updated **CHANGELOG.md** under `[Unreleased]` (or the release section) for **user-visible** changes.

## Testing

- [ ] `pytest`
- [ ] `ruff check src tests scripts`
- [ ] `python scripts/verify_changelog.py`

If converter output changed **on purpose**:

- [ ] I reviewed the golden diff and regenerated it with `python scripts/update_goldens.py`

If this touches format decoding, say what the change is based on. New byte
offsets should be backed by more than one file, or be gated and documented as
unverified — see the "Format coverage and known limitations" section of the
README.
