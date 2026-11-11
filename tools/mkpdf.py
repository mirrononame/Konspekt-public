"""Markdown-конспект -> гарний PDF (DejaVu, кирилиця й польські літери).

Запуск (у хмарному середовищі Claude, де є reportlab і шрифти DejaVu):
    python3 mkpdf.py notes.md notes.pdf "Підпис у колонтитулі" "Заголовок PDF"
Підтримує: # ## ###, абзаци, **жирний**, *курсив*, списки (- / 1.) з вкладеністю,
таблиці |a|b|, цитати > (як виноски), блоки коду ```.
"""
import re, sys
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Preformatted, BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Table, TableStyle,
                                ListFlowable, ListItem, KeepTogether)
import os
def _fonts():
    """DejaVu (хмара/Linux або встановлені у Windows) → інакше Arial + Consolas з Windows (кирилиця й польські літери є)."""
    win = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
    local = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Windows", "Fonts")
    for d in ("/usr/share/fonts/truetype/dejavu", os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts"), win, local):
        names = ["DejaVuSans.ttf", "DejaVuSans-Bold.ttf", "DejaVuSans-Oblique.ttf", "DejaVuSans-BoldOblique.ttf", "DejaVuSansMono.ttf"]
        if all(os.path.isfile(os.path.join(d, n)) for n in names):
            return [os.path.join(d, n) for n in names]
    names = ["arial.ttf", "arialbd.ttf", "ariali.ttf", "arialbi.ttf", "consola.ttf"]
    if all(os.path.isfile(os.path.join(win, n)) for n in names):
        return [os.path.join(win, n) for n in names]
    raise SystemExit("mkpdf: не знайдено шрифтів DejaVu чи Arial")
_F = _fonts()
pdfmetrics.registerFont(TTFont("D", _F[0])); pdfmetrics.registerFont(TTFont("DB", _F[1]))
pdfmetrics.registerFont(TTFont("DI", _F[2])); pdfmetrics.registerFont(TTFont("DBI", _F[3]))
from reportlab.pdfbase.pdfmetrics import registerFontFamily
registerFontFamily("D", normal="D", bold="DB", italic="DI", boldItalic="DBI")
ACC=colors.HexColor("#0ea5e9"); DARK=colors.HexColor("#0f172a"); MUTED=colors.HexColor("#64748b"); SOFT=colors.HexColor("#f0f9ff"); LINE=colors.HexColor("#e2e8f0")
base=ParagraphStyle("b", fontName="D", fontSize=9.6, leading=14, textColor=DARK, spaceAfter=4)
H1=ParagraphStyle("h1", parent=base, fontName="DB", fontSize=17, leading=22, spaceAfter=6, textColor=DARK)
H2=ParagraphStyle("h2", parent=base, fontName="DB", fontSize=12.5, leading=17, spaceBefore=12, spaceAfter=5, keepWithNext=1, textColor=colors.HexColor("#0369a1"))
H3=ParagraphStyle("h3", parent=base, fontName="DB", fontSize=10.5, leading=14, spaceBefore=7, spaceAfter=3, keepWithNext=1)
META=ParagraphStyle("m", parent=base, textColor=MUTED, fontSize=9)
CELL=ParagraphStyle("c", parent=base, fontSize=8.8, leading=12, spaceAfter=0)
CELLH=ParagraphStyle("ch", parent=CELL, fontName="DB", textColor=colors.white)
pdfmetrics.registerFont(TTFont("M", _F[4]))
CODE=ParagraphStyle("code", fontName="M", fontSize=8.4, leading=11.5, textColor=DARK)
NOTE=ParagraphStyle("n", parent=base, fontSize=9, leading=13, textColor=colors.HexColor("#075985"), spaceAfter=0)
def inl(s):
    s=s.replace("🔧", "► ").replace("⭐", "(!) ")  # 2.5: значущі позначки — символами, які є і в DejaVu, і в Arial
    s=re.sub(r"[\U0001F000-\U0001FFFF\uFE0F]\s?", "", s)  # емодзі немає в шрифтах PDF
    s=s.replace("\\|", "|")
    s=s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
    s=re.sub(r"`([^`]+)`", lambda m: '<font name="M" size="8.6" color="#0f4c81">'+m.group(1).replace("*","&#42;")+'</font>', s)
    s=re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s=re.sub(r"(?<!\*)\*(?!\s)(.+?)\*", r"<i>\1</i>", s)
    return s
def split_row(line):
    r"""2.5: комірки таблиці; екранований \| і | усередині `коду` комірку не ділять."""
    cells, cur, code, i, s = [], "", False, 0, line.strip().strip("|")
    while i < len(s):
        if s[i] == "\\" and s[i+1:i+2] == "|":
            cur += "\\|"; i += 2; continue
        if s[i] == "`": code = not code
        if s[i] == "|" and not code: cells.append(cur.strip()); cur = ""
        else: cur += s[i]
        i += 1
    cells.append(cur.strip())
    return cells
def mklist(items, ordered):
    flow=[]
    for text, sub in items:
        content=[Paragraph(inl(text), base)]
        if sub: content.append(mklist(sub, False))
        flow.append(ListItem(content, leftIndent=14))
    if ordered:
        return ListFlowable(flow, bulletType="1", bulletFontName="D", bulletFontSize=9.6, leftIndent=16, spaceAfter=4, bulletFormat="%s.")
    return ListFlowable(flow, bulletType="bullet", start="•", bulletFontName="D", bulletFontSize=8.5, leftIndent=14, bulletColor=ACC, spaceAfter=4)
md=open(sys.argv[1],encoding="utf-8").read().splitlines()
story=[]; i=0
while i<len(md):
    l=md[i]
    if not l.strip(): i+=1; continue
    if l.startswith("```"):
        code=[]; i+=1
        while i<len(md) and not md[i].startswith("```"): code.append(md[i]); i+=1
        i+=1
        t=Table([[Preformatted("\n".join(code), CODE)]], colWidths=[170*mm])
        t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#f1f5f9")),("BOX",(0,0),(-1,-1),0.5,LINE),("LEFTPADDING",(0,0),(-1,-1),9),("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6)]))
        story += [Spacer(1,2), KeepTogether(t), Spacer(1,6)]; continue
    if l.startswith("# "):
        story.append(Paragraph(inl(l[2:]),H1)); i+=1; continue
    if l.startswith("## "):
        story.append(Paragraph(inl(l[3:]),H2)); i+=1; continue
    if l.startswith("### "):
        story.append(Paragraph(inl(l[4:]),H3)); i+=1; continue
    if l.startswith(">"):
        txt=[]
        while i<len(md) and md[i].startswith(">"): txt.append(md[i].lstrip("> ").strip()); i+=1
        t=Table([[Paragraph(inl(" ".join(txt)),NOTE)]], colWidths=[170*mm])
        t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),SOFT),("LINEBEFORE",(0,0),(0,-1),3,ACC),("LEFTPADDING",(0,0),(-1,-1),9),("RIGHTPADDING",(0,0),(-1,-1),9),("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6)]))
        story += [Spacer(1,3), t, Spacer(1,6)]; continue
    if l.startswith("|"):
        rows=[]
        while i<len(md) and md[i].startswith("|"):
            if not re.match(r"^\|\s*:?-", md[i]): rows.append(split_row(md[i]))
            i+=1
        n=len(rows[0]); w=170*mm
        widths=[w*0.24, w*0.76] if n==2 else [w*0.2, w*0.27, w*0.53] if n==3 else [w*0.12, w*0.22, w*0.28, w*0.38] if n==4 else [w/n]*n
        data=[[Paragraph(inl(c), CELLH if r==0 else CELL) for c in row] for r,row in enumerate(rows)]
        t=Table(data, colWidths=widths, repeatRows=1)
        t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#0369a1")),("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white, colors.HexColor("#f8fafc")]),
            ("GRID",(0,0),(-1,-1),0.5,LINE),("VALIGN",(0,0),(-1,-1),"TOP"),("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),("LEFTPADDING",(0,0),(-1,-1),6)]))
        story += [Spacer(1,2), t, Spacer(1,8)]; continue
    m=re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)", l)
    if m:
        ordered=m.group(2)[0].isdigit(); items=[]
        while i<len(md):
            m=re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)", md[i])
            if not m: break
            if len(m.group(1))>=2 and items: items[-1][1].append((m.group(3),[]))
            elif len(m.group(1))<2: items.append((m.group(3),[]))
            i+=1
        story.append(mklist(items, ordered)); continue
    para=[]
    while i<len(md) and md[i].strip() and not re.match(r"^(#|>|\||\s*[-*] |\s*\d+\. )", md[i]): para.append(md[i].strip()); i+=1
    style = META if para and para[0].startswith("**Przedmiot") else base
    story.append(Paragraph(inl(" ".join(para)), style))
def deco(c, doc):
    c.saveState(); c.setFillColor(ACC); c.rect(0, A4[1]-6*mm, A4[0], 6*mm, fill=1, stroke=0)
    c.setFont("D",7.5); c.setFillColor(MUTED)
    c.drawString(20*mm, 10*mm, sys.argv[3])
    c.drawRightString(A4[0]-20*mm, 10*mm, f"{doc.page}"); c.restoreState()
doc=BaseDocTemplate(sys.argv[2], pagesize=A4, leftMargin=20*mm, rightMargin=20*mm, topMargin=16*mm, bottomMargin=18*mm,
                    title=sys.argv[4], author="Claude")
doc.addPageTemplates([PageTemplate(frames=[Frame(20*mm,18*mm,A4[0]-40*mm,A4[1]-34*mm,id="f")], onPage=deco)])
doc.build(story)
