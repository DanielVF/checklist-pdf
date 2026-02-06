This project creates an Apocalypse World / Dungeon World style PDF from a markdown document.

It is primarily intended to create incident response checklists and cheat sheets.

A sample markdown document lives in `samples/sample_fire_response.md`.

Fonts live in `fonts`

The project uses UV, python, and reportlab.

The main script is `checklistpdf.py`.

To regenerate the sample PDF and screenshot:

```
uv run checklistpdf.py samples/sample_fire_response.md samples/sample_fire_response.pdf
```
