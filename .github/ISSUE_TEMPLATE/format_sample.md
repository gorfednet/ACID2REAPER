---
name: Format sample / decoding problem
about: A project that converts incorrectly, or an ACID variant that is not handled
title: "[Format] "
labels: format
---

## What came out wrong

<!-- e.g. wrong tempo, wrong time signature, clips in the wrong place, media not
found, a one-shot that got stretched -->

## What it should be

<!-- The project's real tempo and time signature, and how you know -- opening it
in ACID, or a rendered mixdown that matches. -->

## Conversion diagnostics

Output of:

```bash
acid2reaper your-project.acd out.rpp -v
```

<!-- This reports the decoded tempo and meter, any sources left unstretched, and
any media that could not be found. -->

## ACID version

Which ACID release saved the project, if you know. Different builds store the
same information in different places, so this matters.

## Sample file

The most useful thing you can attach is the `.acd` itself — especially a project
in a meter other than x/4, which nothing in the current corpus covers.

If you cannot share the project, a structural fingerprint carries no audio, no
file names and no project bytes, and is still useful:

```bash
python scripts/build_corpus_manifest.py --corpus-dir /folder/with/the/project --out sample.json
```
