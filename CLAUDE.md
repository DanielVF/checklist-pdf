This project creates an Apocalypse World / Dungeon World style PDF from a markdown document.

It is primarily intended to create incident response checklists and cheat sheets.

A sample markdown document lives in `samples/sample_fire_response.md`.

Fonts live in `fonts`

The project uses UV, python, and reportlab.

The main script is `checklistpdf.py`.

To regenerate the sample PDF:

```
uv run checklistpdf.py samples/sample_fire_response.md samples/sample_fire_response.pdf
```

To regenerate the sample screenshot (1700x990, top of first page):

```
pdftoppm -r 200 -f 1 -l 1 -x 0 -y 0 -W 1700 -H 990 -singlefile -png samples/sample_fire_response.pdf samples/sample_screenshot
```
