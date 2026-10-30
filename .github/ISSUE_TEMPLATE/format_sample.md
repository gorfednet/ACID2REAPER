---
name: Format sample / decoding problem
about: A project that converts incorrectly, or an ACID variant ACID2Reaper doesn't handle
title: "[Format] "
labels: format
---

## What came out wrong

<!-- e.g. wrong tempo, wrong time signature, clips in the wrong place, media not
found, a one-shot that got stretched -->

## What it should be

<!-- The project's real tempo and time signature, and how you know: you opened
it in ACID, or a rendered mixdown matches. -->

## Conversion diagnostics

Output of:

```bash
acid2reaper your-project.acd out.rpp -v
```

<!-- This reports the decoded tempo and meter, any sources left unstretched, and
any media that couldn't be found. -->

## ACID version

Which ACID release saved the project, if you know. Different builds store the
same information in different places.

## Sample file

The most useful attachment is the `.acd` itself, above all a project in a meter
other than x/4, which nothing in the current corpus covers.

If you can't share the project, a structural fingerprint is still useful. It
carries no audio, no file names and no project bytes:

```bash
python scripts/build_corpus_manifest.py --corpus-dir /folder/with/the/project --out sample.json
```
