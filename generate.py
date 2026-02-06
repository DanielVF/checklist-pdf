"""Generate Apocalypse World / Dungeon World style PDF checklists from Markdown."""

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Flowable,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PAGE_W, PAGE_H = letter  # 612 x 792
MARGIN_LEFT = 54
MARGIN_RIGHT = 54
MARGIN_BOTTOM = 54
MARGIN_TOP = 72
GUTTER = 18

CONTENT_W = PAGE_W - MARGIN_LEFT - MARGIN_RIGHT  # 504
COL_W = (CONTENT_W - GUTTER) / 2  # 243

TITLE_AREA_H = 50  # space reserved for H1 title on title pages
TITLE_COL_H = PAGE_H - MARGIN_TOP - MARGIN_BOTTOM - TITLE_AREA_H  # 616
BODY_COL_H = PAGE_H - MARGIN_TOP - MARGIN_BOTTOM  # 666

DARK = HexColor("#1a1a1a")
TEXT_COLOR = HexColor("#222222")
WHITE = HexColor("#FFFFFF")
BOX_BG = HexColor("#F5F5F0")

FONT_DIR = Path(__file__).parent / "fonts"

# ---------------------------------------------------------------------------
# Font registration
# ---------------------------------------------------------------------------


def register_fonts():
    pdfmetrics.registerFont(TTFont("Inter", str(FONT_DIR / "Inter-Regular.ttf")))
    pdfmetrics.registerFont(TTFont("Inter-Bold", str(FONT_DIR / "Inter-Bold.ttf")))
    pdfmetrics.registerFontFamily("Inter", normal="Inter", bold="Inter-Bold")


# ---------------------------------------------------------------------------
# Paragraph styles
# ---------------------------------------------------------------------------

BODY_STYLE = ParagraphStyle(
    "body",
    fontName="Inter",
    fontSize=8,
    leading=11,
    textColor=TEXT_COLOR,
)

BULLET_STYLE = ParagraphStyle(
    "bullet",
    fontName="Inter",
    fontSize=8,
    leading=11,
    textColor=TEXT_COLOR,
    leftIndent=12,
    firstLineIndent=-12,
)

CHECKBOX_TEXT_STYLE = ParagraphStyle(
    "checkbox_text",
    fontName="Inter",
    fontSize=8,
    leading=11,
    textColor=TEXT_COLOR,
)

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class Element:
    kind: str  # "paragraph", "bullet", "checkbox"
    text: str


@dataclass
class Box:
    title: str
    elements: list[Element] = field(default_factory=list)


@dataclass
class Page:
    title: str
    boxes: list[Box] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Markdown parser
# ---------------------------------------------------------------------------


def md_to_markup(text: str) -> str:
    """Convert **bold** markdown to <b> tags for reportlab."""
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)


def parse_markdown(path: Path) -> list[Page]:
    lines = path.read_text().splitlines()
    pages: list[Page] = []
    current_page: Page | None = None
    current_box: Box | None = None
    para_lines: list[str] = []

    def flush_para():
        if para_lines and current_box is not None:
            current_box.elements.append(
                Element("paragraph", " ".join(para_lines))
            )
            para_lines.clear()

    def flush_box():
        nonlocal current_box
        flush_para()
        if current_box is not None and current_page is not None:
            current_page.boxes.append(current_box)
            current_box = None

    def flush_page():
        nonlocal current_page
        flush_box()
        if current_page is not None:
            pages.append(current_page)
            current_page = None

    for line in lines:
        if line.startswith("# ") and not line.startswith("## "):
            flush_page()
            current_page = Page(title=line[2:].strip())
        elif line.startswith("## "):
            flush_box()
            current_box = Box(title=line[3:].strip())
        elif line.startswith("- [ ] "):
            flush_para()
            if current_box is not None:
                current_box.elements.append(
                    Element("checkbox", line[6:].strip())
                )
        elif line.startswith("- "):
            flush_para()
            if current_box is not None:
                current_box.elements.append(
                    Element("bullet", line[2:].strip())
                )
        elif line.strip() == "":
            flush_para()
        else:
            para_lines.append(line.strip())

    flush_page()
    return pages


# ---------------------------------------------------------------------------
# Custom flowables
# ---------------------------------------------------------------------------


class SetTitle(Flowable):
    """Zero-height flowable that stores the H1 title on the doc template."""

    def __init__(self, title: str):
        super().__init__()
        self.title = title
        self.width = 0
        self.height = 0

    def wrap(self, availWidth, availHeight):
        return (0, 0)

    def draw(self):
        doc = self.canv._doctemplate
        doc.current_title = self.title


class CheckboxItem(Flowable):
    """A checkbox square followed by text."""

    BOX_SIZE = 7
    GAP = 5

    def __init__(self, text: str):
        super().__init__()
        self._para = Paragraph(md_to_markup(text), CHECKBOX_TEXT_STYLE)

    def wrap(self, availWidth, availHeight):
        para_w = availWidth - self.BOX_SIZE - self.GAP
        w, h = self._para.wrap(para_w, availHeight)
        self.height = max(h, self.BOX_SIZE + 2)
        self.width = availWidth
        return (self.width, self.height)

    def split(self, availWidth, availHeight):
        return []

    def draw(self):
        c = self.canv
        # Draw checkbox square
        c.setStrokeColor(DARK)
        c.setLineWidth(0.75)
        box_y = self.height - self.BOX_SIZE - 1
        c.rect(0, box_y, self.BOX_SIZE, self.BOX_SIZE)
        # Draw text
        self._para.drawOn(c, self.BOX_SIZE + self.GAP, 0)


class BoxFlowable(Flowable):
    """Bordered box with a dark title bar and child flowables inside."""

    PADDING = 8
    TITLE_H = 20
    BORDER_W = 1.5
    ITEM_SPACING = 4

    def __init__(self, title: str, children: list[Flowable]):
        super().__init__()
        self.box_title = title
        self.children = children
        self._wrapped = False

    def wrap(self, availWidth, availHeight):
        self.width = availWidth
        inner_w = availWidth - 2 * self.PADDING
        total_h = self.TITLE_H + self.PADDING
        for child in self.children:
            _, h = child.wrap(inner_w, availHeight)
            total_h += h + self.ITEM_SPACING
        # Remove last item spacing, add bottom padding
        if self.children:
            total_h -= self.ITEM_SPACING
        total_h += self.PADDING
        self.height = total_h
        self._wrapped = True
        return (self.width, self.height)

    def split(self, availWidth, availHeight):
        # Never split — move to next column/page
        return []

    def draw(self):
        c = self.canv

        # Box background
        c.setFillColor(BOX_BG)
        c.setStrokeColor(DARK)
        c.setLineWidth(self.BORDER_W)
        c.rect(0, 0, self.width, self.height, fill=1)

        # Dark title bar at top
        c.setFillColor(DARK)
        title_y = self.height - self.TITLE_H
        c.rect(0, title_y, self.width, self.TITLE_H, fill=1)

        # Title text
        c.setFillColor(WHITE)
        c.setFont("Inter-Bold", 10)
        c.drawString(self.PADDING, title_y + 6, self.box_title)

        # Draw children
        inner_w = self.width - 2 * self.PADDING
        y = title_y - self.PADDING
        for child in self.children:
            _, h = child.wrap(inner_w, 0)
            y -= h
            child.drawOn(c, self.PADDING, y)
            y -= self.ITEM_SPACING


# ---------------------------------------------------------------------------
# Document template
# ---------------------------------------------------------------------------


def _draw_title_page(canvas, doc):
    """onPage callback for title pages — draws H1 title and rule."""
    title = getattr(doc, "current_title", "")
    if not title:
        return
    canvas.saveState()
    canvas.setFont("Inter-Bold", 24)
    canvas.setFillColor(DARK)
    title_y = PAGE_H - MARGIN_TOP + 10
    canvas.drawString(MARGIN_LEFT, title_y, title.upper())
    # Horizontal rule
    rule_y = title_y - 8
    canvas.setStrokeColor(DARK)
    canvas.setLineWidth(2)
    canvas.line(MARGIN_LEFT, rule_y, PAGE_W - MARGIN_RIGHT, rule_y)
    canvas.restoreState()


def _draw_body_page(canvas, doc):
    """onPage callback for continuation pages — no title."""
    pass


def build_doc(output_path: str) -> BaseDocTemplate:
    doc = BaseDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=MARGIN_LEFT,
        rightMargin=MARGIN_RIGHT,
        topMargin=MARGIN_TOP,
        bottomMargin=MARGIN_BOTTOM,
    )
    doc.current_title = ""

    col_x_left = MARGIN_LEFT
    col_x_right = MARGIN_LEFT + COL_W + GUTTER

    # Title page: shorter columns to leave room for H1 title
    title_frames = [
        Frame(col_x_left, MARGIN_BOTTOM, COL_W, TITLE_COL_H,
              id="title_left", leftPadding=0, rightPadding=0,
              topPadding=0, bottomPadding=0),
        Frame(col_x_right, MARGIN_BOTTOM, COL_W, TITLE_COL_H,
              id="title_right", leftPadding=0, rightPadding=0,
              topPadding=0, bottomPadding=0),
    ]

    # Body page: full-height columns
    body_frames = [
        Frame(col_x_left, MARGIN_BOTTOM, COL_W, BODY_COL_H,
              id="body_left", leftPadding=0, rightPadding=0,
              topPadding=0, bottomPadding=0),
        Frame(col_x_right, MARGIN_BOTTOM, COL_W, BODY_COL_H,
              id="body_right", leftPadding=0, rightPadding=0,
              topPadding=0, bottomPadding=0),
    ]

    doc.addPageTemplates([
        PageTemplate(id="title_page", frames=title_frames, onPage=_draw_title_page),
        PageTemplate(id="body_page", frames=body_frames, onPage=_draw_body_page),
    ])

    return doc


# ---------------------------------------------------------------------------
# Story builder
# ---------------------------------------------------------------------------


def build_box_children(box: Box) -> list[Flowable]:
    children: list[Flowable] = []
    for el in box.elements:
        if el.kind == "paragraph":
            children.append(Paragraph(md_to_markup(el.text), BODY_STYLE))
        elif el.kind == "bullet":
            text = f"\u2022\u2002{md_to_markup(el.text)}"
            children.append(Paragraph(text, BULLET_STYLE))
        elif el.kind == "checkbox":
            children.append(CheckboxItem(el.text))
    return children


def build_story(pages: list[Page]) -> list[Flowable]:
    story: list[Flowable] = []
    for i, page in enumerate(pages):
        if i > 0:
            # Set title BEFORE page break so onPage callback sees it
            story.append(SetTitle(page.title))
            story.append(NextPageTemplate("title_page"))
            story.append(PageBreak())
        story.append(NextPageTemplate("body_page"))
        for j, box in enumerate(page.boxes):
            if j > 0:
                story.append(Spacer(1, 10))
            children = build_box_children(box)
            story.append(BoxFlowable(box.title, children))
    return story


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    if len(sys.argv) != 3:
        print("Usage: python generate.py <input.md> <output.pdf>", file=sys.stderr)
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])

    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    register_fonts()
    pages = parse_markdown(input_path)
    story = build_story(pages)
    doc = build_doc(str(output_path))
    # Set first page title before build so onPage callback sees it
    if pages:
        doc.current_title = pages[0].title
    doc.build(story)
    print(f"Generated {output_path} ({len(pages)} sections)")


if __name__ == "__main__":
    main()
