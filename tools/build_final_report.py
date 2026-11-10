#!/usr/bin/env python3
"""Build the ERA5-first six-chapter report with a GloFAS extension and a QC benchmark appendix."""
from __future__ import annotations
import csv
import hashlib
import json
import re
import shutil
import sqlite3
import subprocess
from pathlib import Path

import numpy as np
from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT, WD_TAB_LEADER, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt
from docx.text.paragraph import Paragraph
from pypdf import PdfReader
from report_metadata import clean_application_properties
from office_runtime import convert_document
import report_extended as report_v2

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
ASSETS = DOCS / "report_assets"
SOURCE = DOCS / "report_src/noi_dung.md"
TARGET_DOCX = DOCS / "BAO_CAO_TIEU_LUAN_6_CHUONG.docx"
TARGET_PDF = DOCS / "BAO_CAO_TIEU_LUAN_6_CHUONG.pdf"
TEMPLATE_DOCX = ASSETS / "ptit_cover_template.docx"

TITLE = "Nghiên cứu dữ liệu lĩnh vực khí tượng thủy văn, thu thập và xử lý dữ liệu này cho hệ thống dự báo thời tiết"
HEADER_TEXT = "NHẬP MÔN KHOA HỌC DỮ LIỆU  |  NHÓM 13 – DỮ LIỆU KHÍ TƯỢNG THỦY VĂN & DỰ BÁO THỜI TIẾT"
BODY_WIDTH = 17.09


def js(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def csv_rows(rel: str):
    with (ROOT / rel).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def vn(n, d: int = 0) -> str:
    return f"{float(n):,.{d}f}".replace(",", "_").replace(".", ",").replace("_", ".")


# Native Office Math (OMML) builders
def mr(text: str):
    node = OxmlElement("m:r")
    pr = OxmlElement("m:rPr")
    sty = OxmlElement("m:sty")
    sty.set(qn("m:val"), "p")
    pr.append(sty)
    node.append(pr)
    t = OxmlElement("m:t")
    t.text = text
    node.append(t)
    return node


def wrapper(tag: str, items: list):
    node = OxmlElement(tag)
    for item in items:
        node.append(item)
    return node


def frac(a: list, b: list):
    return wrapper("m:f", [wrapper("m:num", a), wrapper("m:den", b)])


def sub(base: str, lower: str):
    return wrapper("m:sSub", [wrapper("m:e", [mr(base)]), wrapper("m:sub", [mr(lower)])])


def sup(base: str, upper: str):
    return wrapper("m:sSup", [wrapper("m:e", [mr(base)]), wrapper("m:sup", [mr(upper)])])


def sup_nodes(base_nodes: list, upper: str):
    return wrapper("m:sSup", [wrapper("m:e", base_nodes), wrapper("m:sup", [mr(upper)])])


def summation_nodes(lower_nodes: list, upper_nodes: list, body_nodes: list, hide_sup: bool = False):
    node = OxmlElement("m:nary")
    pr = OxmlElement("m:naryPr")
    char = OxmlElement("m:chr")
    char.set(qn("m:val"), "∑")
    pr.append(char)
    lim = OxmlElement("m:limLoc")
    lim.set(qn("m:val"), "undOvr")
    pr.append(lim)
    if hide_sup:
        sh = OxmlElement("m:supHide")
        sh.set(qn("m:val"), "1")
        pr.append(sh)
    node.append(pr)
    node.append(wrapper("m:sub", lower_nodes))
    node.append(wrapper("m:sup", upper_nodes if upper_nodes else [mr("")]))
    node.append(wrapper("m:e", body_nodes))
    return node


def equation_nodes(key: str) -> list:
    if key == "ridge_obj":
        return [mr("J_R(w,b) = "), summation_nodes([mr("i=1")],[mr("n")],[sup_nodes([mr("("),sub("y","i"),mr(" − b − "),sub("x","i"),mr("ᵀw)")],"2")]), mr(" + α‖w‖²")]
    if key == "logistic_obj":
        return [mr("J_L = −"), frac([mr("1")],[mr("n")]), summation_nodes([mr("i=1")],[mr("n")],[mr("["),sub("y","i"),mr(" ln "),sub("p","i"),mr(" + (1−"),sub("y","i"),mr(") ln(1−"),sub("p","i"),mr(")]" )]),mr(" + "),frac([mr("‖w‖²")],[mr("2Cn")])]
    if key == "brier_skill":
        return [mr("BS = "), frac([mr("1")],[mr("n")]),summation_nodes([mr("i=1")],[mr("n")],[sup_nodes([mr("("),sub("p","i"),mr(" − "),sub("y","i"),mr(")")],"2")]),mr(" ; BSS = 1 − "),frac([sub("BS","model")],[sub("BS","ref")])]
    if key == "magnus":
        return [
            sub("γ", "i"), mr(" = "),
            frac([mr("17,62 "), sub("T", "i")], [mr("243,12 + "), sub("T", "i")]),
            mr(" + ln("), sub("RH", "i"), mr(" / 100)  ;   "),
            sub("T", "d,i"), mr(" = "),
            frac([mr("243,12 "), sub("γ", "i")], [mr("17,62 − "), sub("γ", "i")]),
            mr(" ≤ "), sub("T", "i"),
        ]
    if key == "wind_vec":
        return [
            sub("u", "i"), mr(" = −"), sub("W", "i"), mr(" sin("), sub("θ", "i"), mr(")  ;   "),
            sub("v", "i"), mr(" = −"), sub("W", "i"), mr(" cos("), sub("θ", "i"), mr(")"),
        ]
    if key == "iqr":
        return [
            mr("IQR = "), sub("Q", "3"), mr(" − "), sub("Q", "1"),
            mr(" ;  L = "), sub("Q", "1"), mr(" − 1,5 IQR ;  U = "), sub("Q", "3"), mr(" + 1,5 IQR"),
        ]
    if key == "spearman":
        return [sub("ρ", "s"), mr(" = corr(R(X), R(Y))")]
    if key == "bootstrap":
        return [mr("CI = ["), sub("q", "0,025"), mr(" , "), sub("q", "0,975"), mr("] ;  B = 500")]
    if key == "zscore":
        return [
            sub("z", "ij"), mr(" = "),
            frac([sub("x", "ij"), mr(" − "), sub("μ", "j")], [sub("σ", "j")]),
            mr(" ;  j ∈ {RH, ln(P + 1)}"),
        ]
    if key == "kmeans":
        return [
            mr("J = "),
            summation_nodes(
                [mr("j=1")],
                [mr("k")],
                [
                    summation_nodes(
                        [mr("i∈"), sub("C", "j")],
                        [],
                        [sup_nodes([mr("‖"), sub("z", "i"), mr(" − "), sub("c", "j"), mr("‖")], "2")],
                        hide_sup=True,
                    )
                ],
            ),
        ]
    if key == "centroid":
        return [
            sub("c", "j"), mr(" = "),
            frac([mr("1")], [sub("n", "j")]), mr(" "),
            summation_nodes(
                [mr("i∈"), sub("C", "j")],
                [],
                [sub("z", "i")],
                hide_sup=True,
            ),
        ]
    if key == "silhouette":
        return [sub("s", "i"), mr(" = "), frac([sub("b", "i"), mr(" − "), sub("a", "i")], [mr("max("), sub("a", "i"), mr(", "), sub("b", "i"), mr(")")])]
    if key == "forecast_metrics":
        return [
            mr("MAE = "), frac([mr("1")], [mr("m")]), mr(" "),
            summation_nodes([mr("i=1")], [mr("m")], [mr("|"), sub("y", "i"), mr(" − "), sub("ŷ", "i"), mr("|")]),
            mr("  ;   "), sup("RMSE", "2"), mr(" = "), frac([mr("1")], [mr("m")]), mr(" "),
            summation_nodes([mr("i=1")], [mr("m")], [sup_nodes([mr("("), sub("y", "i"), mr(" − "), sub("ŷ", "i"), mr(")")], "2")]),
        ]
    if key == "classification_metrics":
        return [
            mr("Precision = "), frac([mr("TP")], [mr("TP + FP")]),
            mr(" ;  Recall = "), frac([mr("TP")], [mr("TP + FN")]),
            mr(" ;  "), sub("F", "1"), mr(" = "), frac([mr("2 ⋅ Precision ⋅ Recall")], [mr("Precision + Recall")]),
        ]
    raise KeyError(key)


def measured_tables(a):
    return report_v2.tables(a)

FIGURES = report_v2.figures()


def render_once(page_map: dict[str, int] | None = None) -> tuple[dict, dict]:
    a = js("outputs/analysis.json")
    tables = measured_tables(a)
    source = SOURCE.read_text(encoding="utf-8")
    chunks = [c.strip() for c in source.strip().split("\n\n") if c.strip()]

    indices = {"table": {}, "figure": {}, "equation": {}}
    for chunk in chunks:
        if chunk.startswith("@"):
            kind, key = chunk[1:].strip().split(" ", 1)
            if kind in indices:
                indices[kind][key] = len(indices[kind]) + 1

    def resolve(text: str) -> str:
        def repl(m):
            return str(indices[m[1]][m[2]])
        return re.sub(r"\[\[(table|figure|equation):([^\]]+)\]\]", repl, text)

    doc = Document(str(TEMPLATE_DOCX))
    normal=doc.styles['Normal']
    normal.font.name='Times New Roman';normal.font.size=Pt(12)
    normal.paragraph_format.line_spacing=1.15
    normal.paragraph_format.space_after=Pt(6)
    for style in ['Title','Heading 1','Heading 2','Caption']:
        from docx.shared import RGBColor
        doc.styles[style].font.color.rgb=RGBColor(0,0,0)
    doc.styles['Heading 2'].font.name='Times New Roman'
    doc.styles['Heading 2'].font.size=Pt(13)
    doc.styles['Heading 2'].font.bold=True
    doc.styles['Heading 2'].paragraph_format.space_before=Pt(10)
    doc.styles['Heading 2'].paragraph_format.space_after=Pt(6)
    doc.styles['Heading 2'].paragraph_format.keep_with_next=True
    for sec in doc.sections:
        for hp in sec.header.paragraphs:
            if hp.text.strip():
                hp.text = HEADER_TEXT
                for r in hp.runs:
                    r.font.name = "Times New Roman"
                    r.font.size = Pt(9)

    body = doc.element.body
    orig_paras = list(doc.paragraphs)

    orig_paras[4].text = TITLE
    orig_paras[4].style = doc.styles["Title"]
    for r in orig_paras[4].runs:
        r.font.name = "Times New Roman"
        r.font.size = Pt(18)
        r.font.bold = True

    orig_paras[5].text = "Giảng viên hướng dẫn: ThS. Nguyễn Ngọc Duy"
    orig_paras[6].text = "Nhóm thực hiện: Nhóm 13"
    orig_paras[7].text = "Đinh Quang Thái  —  MSSV: N22DCCN176"
    orig_paras[8].text = "Đặng Ngọc Sơn  —  MSSV: N22DCCN070"
    orig_paras[9].text = "Đặng Văn Chương  —  MSSV: N22DCCN012"
    orig_paras[10].text = "TP. Hồ Chí Minh, tháng 11 năm 2026"

    orig_paras[14].text = "Nhóm 13 xin cảm ơn giảng viên học phần Nhập môn Khoa học dữ liệu và Học viện Công nghệ Bưu chính Viễn thông đã tạo điều kiện học tập để nhóm thực hiện đề tài về dữ liệu khí tượng thủy văn."
    orig_paras[15].text = "Báo cáo trình bày quy trình thu thập, xử lý và đánh giá dữ liệu phục vụ thực nghiệm dự báo thời tiết. Nhóm chịu trách nhiệm giải thích nguồn dữ liệu, mã nguồn, kết quả và những giới hạn được nêu trong báo cáo."
    orig_paras[16].text = "Nhóm mong nhận được góp ý của giảng viên để hoàn thiện phương pháp nghiên cứu dữ liệu và kỹ năng trình bày kết quả thực nghiệm."

    n_tables = len(indices["table"])
    n_figs = len(indices["figure"])

    score = js("outputs/real/summary.json")["rain"]
    orig_paras[19].text = (
        "Đề tài chuẩn bị dữ liệu khí tượng thủy văn có truy nguyên cho dự báo thời tiết ngày kế tiếp. "
        "Nguồn chính gồm 9.861 địa điểm–ngày ERA5 tại ba ô lưới giai đoạn 2017–2025 và 5.478 địa điểm–ngày lưu lượng mô hình GloFAS v4 consolidated giai đoạn 2017–2021. "
        "Hai nguồn có hồ sơ truy vấn và SHA-256, được kiểm tra lịch, đơn vị, giá trị thiếu và miền hợp lệ, rồi lưu riêng trong SQLite."
    )
    orig_paras[20].text = (
        "Trên Test 2025 ERA5 (n=1.095), Ridge R3 đạt RMSE 0,9302 °C so quán tính 1,0741 °C; CI 95% của chênh lệch RMSE là [−0,1938; −0,0951] °C. "
        f"Phân lớp mưa đạt F1 81,67%, ROC-AUC 0,8593 và Brier 0,151316; Brier skill score so xác suất khí hậu Train là {vn(score['BSS_train_climatology'],4)}. "
        "CI chênh lệch F1 với quán tính chứa 0 nên chưa khẳng định ưu thế. Phân cụm chỉ dùng mô tả độ ẩm–mưa; lưu lượng được mô tả riêng theo ngày UTC."
    )
    orig_paras[21].text = (
        "ERA5 và GloFAS là sản phẩm mô hình/tái phân tích, chưa có đối chứng trạm độc lập. Chưa kiểm chứng chọn ô sông, dự báo lũ hoặc khả năng vận hành trực tiếp. "
        "Bộ mô phỏng 10.273 dòng chỉ phục vụ kiểm thử logic ở phụ lục; thiếu mã sinh/seed gốc nên phạm vi tái lập bắt đầu từ JSON kèm bài. "
        "Không coi lợi ích điền khuyết trên bộ mô phỏng là đóng góp dự báo đã chứng minh ngoài thực tế."
    )
    orig_paras[22].text = "Từ khóa: dữ liệu khí tượng thủy văn; kiểm soát chất lượng WMO-No. 8; QCVN 46:2022/BTNMT; tạo đặc trưng chuỗi thời gian; dự báo thời tiết; K-means; SQLite."
    orig_paras[23].text = "Phiên bản báo cáo tháng 11/2026. ERA5 2017–2025 và GloFAS 2017–2021; đánh giá hồi cứu phục vụ học tập."

    sect_break_p = orig_paras[73]._p
    for p_old in orig_paras[25:73]:
        p_old._p.getparent().remove(p_old._p)

    for child in list(body):
        if child is sect_break_p:
            continue
        if body.index(child) > body.index(sect_break_p) and child.tag != qn("w:sectPr"):
            body.remove(child)

    def make_p(text: str = "", style: str = "Normal", center: bool = False, small: bool = False) -> Paragraph:
        p = doc.add_paragraph(resolve(text), style=style)
        if center:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.first_line_indent = Cm(0)
        if small:
            p.paragraph_format.first_line_indent = Cm(0)
            p.paragraph_format.line_spacing = 1.0
            p.paragraph_format.space_after = Pt(6)
            for r in p.runs:
                r.font.size = Pt(10.5)
        return p

    def insert_before_sect(p: Paragraph):
        sect_break_p.addprevious(p._p)
        return p

    bookmarks = []

    def add_bookmark(p: Paragraph, name: str):
        idx = len(bookmarks) + 1
        bookmarks.append(name)
        start = OxmlElement("w:bookmarkStart")
        start.set(qn("w:id"), str(idx))
        start.set(qn("w:name"), name)
        end = OxmlElement("w:bookmarkEnd")
        end.set(qn("w:id"), str(idx))
        p._p.insert(0, start)
        p._p.append(end)

    def add_field(p: Paragraph, instr_text: str, cached_val: str = "1"):
        start = OxmlElement("w:fldChar")
        start.set(qn("w:fldCharType"), "begin")
        p.add_run()._r.append(start)
        instr = OxmlElement("w:instrText")
        instr.set(qn("xml:space"), "preserve")
        instr.text = f" {instr_text} "
        p.add_run()._r.append(instr)
        sep = OxmlElement("w:fldChar")
        sep.set(qn("w:fldCharType"), "separate")
        p.add_run()._r.append(sep)
        p.add_run(str(cached_val))
        end = OxmlElement("w:fldChar")
        end.set(qn("w:fldCharType"), "end")
        p.add_run()._r.append(end)

    def add_toc_line(label: str, bkmk: str, fallback_page: str = "1"):
        pg = str(page_map.get(bkmk, fallback_page)) if page_map else fallback_page
        p = insert_before_sect(make_p(label))
        p.paragraph_format.first_line_indent = Cm(0)
        p.paragraph_format.line_spacing = 1.05
        p.paragraph_format.space_after = Pt(3)
        p.paragraph_format.tab_stops.add_tab_stop(Cm(BODY_WIDTH), WD_TAB_ALIGNMENT.RIGHT, WD_TAB_LEADER.DOTS)
        p.add_run("\t")
        add_field(p, f"PAGEREF {bkmk} \\h", pg)
        for run in p.runs:
            run.font.size = Pt(12)

    def add_front_heading(title_text: str, page_break: bool = False):
        if page_break:
            pb = insert_before_sect(make_p(""))
            pb.paragraph_format.first_line_indent = Cm(0)
            pb.add_run().add_break(WD_BREAK.PAGE)
        p = insert_before_sect(make_p(title_text))
        p.paragraph_format.first_line_indent = Cm(0)
        p.paragraph_format.space_after = Pt(14)
        for r in p.runs:
            r.bold = True
            r.font.size = Pt(15)

    chapters = [c[2:] for c in chunks if c.startswith("# ")]
    add_front_heading("Mục lục", page_break=False)
    ch_index=0; sec_index=0
    for c in chunks:
        if c.startswith('@appendix'):break
        if c.startswith('# '):
            ch_index+=1;add_toc_line(c[2:],f'chapter_{ch_index}',str(ch_index))
        elif c.startswith('## '):
            sec_index+=1;add_toc_line('    '+c[3:],f'section_{sec_index}',str(ch_index))
    add_toc_line("Phụ lục A. Kiểm thử QC trên bộ mô phỏng", "appendix_benchmark", "24")
    add_toc_line("Tài liệu tham khảo", "references", "36")
    add_toc_line("Phụ lục tái lập và nguồn minh chứng", "appendix", "38")

    add_front_heading("Danh mục hình", page_break=True)
    for key, num in indices["figure"].items():
        add_toc_line(f"Hình {num}: {FIGURES[key]['caption']}", f"figure_{num}", str(num + 7))

    add_front_heading("Danh mục bảng", page_break=True)
    for key, num in indices["table"].items():
        add_toc_line(f"Bảng {num}: {tables[key]['caption']}", f"table_{num}", str(num + 2))

    chapter_no = 0
    section_no = 0
    for chunk in chunks:
        if chunk.startswith("# "):
            chapter_no += 1
            p = make_p(chunk[2:], style="Heading 1")
            add_bookmark(p, f"chapter_{chapter_no}")
            continue
        if chunk.startswith("## "):
            section_no+=1
            p=make_p(chunk[3:],style="Heading 2")
            add_bookmark(p,f"section_{section_no}")
            continue
        if not chunk.startswith("@"):

            make_p(chunk, style="Normal")
            continue

        kind, key = chunk[1:].strip().split(" ", 1)
        if kind == "appendix":
            p = make_p("Phụ lục A. Kiểm thử QC trên bộ mô phỏng", style="Heading 1")
            add_bookmark(p, "appendix_benchmark")
        elif kind == "table":
            t = tables[key]
            num = indices["table"][key]
            cap = make_p(f"Bảng {num}: {t['caption']}", style="Caption", center=True)
            cap.paragraph_format.keep_with_next = True
            add_bookmark(cap, f"table_{num}")

            tbl = doc.add_table(rows=1, cols=len(t["headers"]))
            tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
            tbl.autofit = False
            tot_w = sum(t["widths"])
            widths = [w / tot_w * BODY_WIDTH for w in t["widths"]]
            for col, w in zip(tbl.columns, widths):
                col.width = Cm(w)

            for row_vals in [t["headers"]] + t["rows"]:
                row = tbl.rows[0] if row_vals is t["headers"] else tbl.add_row()
                for i, (cell, val_str) in enumerate(zip(row.cells, row_vals)):
                    cell.width = Cm(widths[i])
                    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
                    cell.text = resolve(str(val_str))
                    cp = cell.paragraphs[0]
                    cp.paragraph_format.first_line_indent = Cm(0)
                    cp.paragraph_format.line_spacing = 1.05
                    cp.paragraph_format.space_before = Pt(3)
                    cp.paragraph_format.space_after = Pt(3)
                    cp.alignment = WD_ALIGN_PARAGRAPH.CENTER if (row_vals is t["headers"] or len(str(val_str)) < 20) else WD_ALIGN_PARAGRAPH.LEFT
                    for r in cp.runs:
                        r.font.name = "Times New Roman"
                        r.font.size = Pt(10.5)
                        r.bold = (row_vals is t["headers"])
                    tcpr = cell._tc.get_or_add_tcPr()
                    margins = OxmlElement("w:tcMar")
                    for edge in ("top", "left", "bottom", "right"):
                        el = OxmlElement(f"w:{edge}")
                        el.set(qn("w:w"), "75")
                        el.set(qn("w:type"), "dxa")
                        margins.append(el)
                    tcpr.append(margins)
                    borders = OxmlElement("w:tcBorders")
                    for edge in ("top", "left", "bottom", "right"):
                        el = OxmlElement(f"w:{edge}")
                        el.set(qn("w:val"), "single")
                        el.set(qn("w:sz"), "5")
                        el.set(qn("w:color"), "D9D9D9")
                        borders.append(el)
                    tcpr.append(borders)
                    if row_vals is t["headers"]:
                        shd = OxmlElement("w:shd")
                        shd.set(qn("w:fill"), "E2E9EF")
                        tcpr.append(shd)
                trpr = row._tr.get_or_add_trPr()
                trpr.append(OxmlElement("w:cantSplit"))
                if row_vals is t["headers"]:
                    trpr.append(OxmlElement("w:tblHeader"))
                    for c in row.cells:
                        for cp in c.paragraphs:
                            cp.paragraph_format.keep_with_next = True
            # Keep small tables together; always retain the source with the final row.
            for ri, row in enumerate(tbl.rows):
                if len(t['rows']) <= 7 or ri == len(tbl.rows)-1:
                    for cell in row.cells:
                        for pp in cell.paragraphs:pp.paragraph_format.keep_with_next=True
            make_p(t["source"], small=True)

        elif kind == "figure":
            f = FIGURES[key]
            num = indices["figure"][key]
            img_path = ROOT / f.get("path", f"outputs/charts/{key}.png")
            p_img = make_p("", center=True)
            p_img.paragraph_format.keep_with_next = True
            w_cm = 10.8 if key == "workbook_kpi" else (12.8 if key in {"08_spearman_correlation", "real_paired_bootstrap"} else 16.2)
            run = p_img.add_run()
            inline = run.add_picture(str(img_path), width=Cm(w_cm))
            inline._inline.docPr.set("descr", f["caption"])
            cap = make_p(f"Hình {num}: {f['caption']}", style="Caption", center=True)
            cap.paragraph_format.keep_with_next = True
            add_bookmark(cap, f"figure_{num}")
            src_prefix = f.get("prefix", "Nguồn: bộ mô phỏng QC KTTV 2017–2025 [18]. ")
            make_p(src_prefix + f["note"], small=True)

        elif kind == "equation":
            p_eq = make_p("", center=True)
            p_eq.paragraph_format.space_before = Pt(6)
            p_eq.paragraph_format.space_after = Pt(8)
            math_el = wrapper("m:oMath", equation_nodes(key))
            p_eq._p.append(math_el)
            r_num = p_eq.add_run(f"    ({indices['equation'][key]})")
            r_num.font.size = Pt(11)

        elif kind == "code":
            if key == "sql_search":
                code_str = a["sql_benchmark"]["query"] + ";"
                src_caption = "Nguồn: mã thực thi trong src/pipeline.py và sql/02_queries.sql."
            elif key == "wmo_qc_core":
                code_str = (
                    "if dewpoint is None:\n"
                    "    reject_reasons.append('missing_dewpoint')\n"
                    "elif temp_mean is not None and dewpoint > temp_mean + 0.05:\n"
                    "    reject_reasons.append('physical_violation_dewpoint_gt_temp')\n"
                    "elif temp_mean is not None and humidity is not None and (0.0 < humidity <= 100.0):\n"
                    "    td_theo = compute_wmo_dewpoint(temp_mean, humidity)  # WMO-No. 8 (a=17.62, b=243.12)\n"
                    "    if abs(dewpoint - td_theo) > 2.5:\n"
                    "        reject_reasons.append('physical_violation_magnus_mismatch')\n"
                    "if humidity is None or not (0.0 <= humidity <= 100.0):\n"
                    "    reject_reasons.append('wmo_gross_limit_humidity')"
                )
                src_caption = "Nguồn: trích hàm check_wmo_physical_consistency trong src/source_checks.py."
            else:
                code_str = (
                    "distances = ((x[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)\n"
                    "labels = distances.argmin(axis=1)\n"
                    "updated = np.array([\n"
                    "    x[labels == j].mean(axis=0) if np.any(labels == j)\n"
                    "    else x[np.argmax(distances.min(axis=1))]\n"
                    "    for j in range(k)\n"
                    "])"
                )
                src_caption = "Nguồn: phần gán nhãn và cập nhật tâm của hàm kmeans_numpy trong src/pipeline.py."
            for line in code_str.splitlines():
                p_c = make_p(line)
                p_c.alignment = WD_ALIGN_PARAGRAPH.LEFT
                p_c.paragraph_format.first_line_indent = Cm(0)
                p_c.paragraph_format.line_spacing = 1.05
                p_c.paragraph_format.space_after = Pt(1)
                p_c.paragraph_format.keep_with_next = True
                for r in p_c.runs:
                    r.font.name = "Consolas"
                    r.font.size = Pt(9.5)
            make_p(src_caption, small=True)

    p_ref = make_p("Tài liệu tham khảo", style="Heading 1")
    add_bookmark(p_ref, "references")
    refs = [
        "[1] Hersbach, H., et al. (2020). The ERA5 global reanalysis. Quarterly Journal of the Royal Meteorological Society, 146(730), 1999–2049. https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels.",
        "[2] Open-Meteo Developers (2024). Open-Meteo Historical Weather API Documentation (ERA5 & ERA5-Land Reanalysis). https://open-meteo.com/en/docs/historical-weather-api. Giấy phép CC BY 4.0.",
        "[3] World Meteorological Organization (WMO, 2021). Guide to Instruments and Methods of Observation (WMO-No. 8), Volume I: Measurement of Meteorological Variables (Chapter 2 Section 2.1.4.1 & Chapter 4 Annex 4.B: Magnus formula over liquid water, a = 17.62, b = 243.12 °C). Geneva. https://library.wmo.int/records/item/68695-guide-to-instruments-and-methods-of-observation.",
        "[4] World Meteorological Organization (WMO, 2021). Guidelines on Surface Station Data Quality Control and Quality Assurance for Climate Applications (WMO-No. 1269). Geneva. https://library.wmo.int/records/item/57727-guidelines-on-surface-station-data-quality-control-and-quality-assurance-for-climate-applications.",
        "[5] Zahumenský, I. (2004). Guidelines on Quality Control Procedures for Data from Automatic Weather Stations (WMO/TD-No. 1236, CIMO/OPAG-SURFACE). World Meteorological Organization. https://www.researchgate.net/publication/228826920_Guidelines_on_Quality_Control_Procedures_for_Data_from_Automatic_Weather_Stations.",
        "[6] Bộ Tài nguyên và Môi trường (2022). Quy chuẩn kỹ thuật quốc gia về quan trắc khí tượng, mã số QCVN 46:2022/BTNMT (Ban hành kèm theo Thông tư số 14/2022/TT-BTNMT ngày 27/10/2022 của Bộ trưởng Bộ Tài nguyên và Môi trường, có hiệu lực từ ngày 28/04/2023; Phần II: Quy định kỹ thuật). https://luatvietnam.vn/tai-nguyen/quy-chuan-viet-nam-qcvn-46-2022-btnmt-233289-d3.html.",
        "[7] Nhóm 13 (2026). Hồ sơ nguồn và phạm vi tái lập bộ mô phỏng kiểm thử QC: data/raw/kttv_metadata.json, data/raw/kttv_file_manifest.json và docs/NGUON_DU_LIEU_VA_GIOI_HAN_TAI_LAP.md. Bộ mô phỏng đóng băng được cung cấp cùng bài; không chứa quan trắc NOAA ISD/Meteostat.",
        "[8] Harris, C. R., et al. & NumPy Developers (2020). Array programming with NumPy (NumPy v2.3 Manual: Array Broadcasting & Linear Algebra). Nature, 585, 357–362. https://numpy.org/doc/2.3/user/basics.broadcasting.html.",
        "[9] pandas Developers. pandas 2.3 Documentation: Time Series / Date functionality (date_range, reindex, shift) & GroupBy split-apply-combine. https://pandas.pydata.org/pandas-docs/version/2.3/user_guide/timeseries.html.",
        "[10] Matplotlib Development Team. Matplotlib 3.10 Documentation: Statistical Plots & Figure Layout. https://matplotlib.org/3.10.6/api/_as_gen/matplotlib.pyplot.hist.html.",
        "[11] SQLite Consortium. Query Planning, Foreign Key Support, CREATE TABLE & EXPLAIN QUERY PLAN. https://www.sqlite.org/queryplanner.html; https://www.sqlite.org/foreignkeys.html; https://www.sqlite.org/eqp.html.",
        "[12] Arthur, D., và Vassilvitskii, S. (2007). k-means++: The Advantages of Careful Seeding. Proceedings of the Eighteenth Annual ACM-SIAM Symposium on Discrete Algorithms (SODA), 1027–1035. https://theory.stanford.edu/~sergei/papers/kMeansPP-soda.pdf.",
        "[13] Rousseeuw, P. J. (1987). Silhouettes: A graphical aid to the interpretation and validation of cluster analysis. Journal of Computational and Applied Mathematics, 20, 53–65. DOI 10.1016/0377-0427(87)90125-7.",
        "[14] Hubert, L., và Arabie, P. (1985). Comparing partitions (Adjusted Rand Index). Journal of Classification, 2, 193–218. DOI 10.1007/BF01908075.",
        "[15] Efron, B. (1979). Bootstrap Methods: Another Look at the Jackknife. The Annals of Statistics, 7(1), 1–26. DOI 10.1214/aos/1176344552.",
        "[16] Bộ Xây dựng (2022). Quy chuẩn kỹ thuật quốc gia về Số liệu điều kiện tự nhiên dùng trong xây dựng, mã số QCVN 02:2022/BXD (Ban hành kèm theo Thông tư số 02/2022/TT-BXD ngày 26/09/2022; Phụ lục A: dòng Hà Nội tại Bảng A.25 (mưa TB năm 1.670,1 mm) và A.28 (147,9 ngày mưa/năm)). https://datafiles.chinhphu.vn/cpp/files/vbpq/2022/10/02-bxd.pdf.",
        "[17] Ban Chỉ huy Phòng, chống thiên tai và Tìm kiếm cứu nạn TP. Hà Nội & Báo Chính phủ (08/09/2024). Báo cáo công tác triển khai ứng phó với bão số 3 (Yagi) tính đến 07 giờ ngày 08/09/2024 trên địa bàn thành phố Hà Nội. https://nguoihanoi.vn/ha-noi-cong-tac-trien-khai-ung-pho-voi-bao-so-3-tinh-den-7-gio-ngay-8-9-2024-86738.html và https://baochinhphu.vn/bao-so-3-manh-cap-14-giat-cap-17-khu-vuc-bac-bo-mua-lon-dien-rong-102240907061701111.htm.",
        "[18] Nhóm 13 (2026). Mã nguồn và bộ dữ liệu kèm báo cáo: KHDL-KhiTuongThuyVan-main.zip, README.md, data/era5 và data/raw (mốc run_id 20261108T120000Z-kttv34vn; hồ sơ băm SHA-256 tại outputs/run_manifest.json). Tài liệu nội bộ bàn giao cùng bài nộp; chưa có URL kho mã công khai được xác nhận.",
        "[19] Virtanen, P., et al. (2020). SciPy 1.0: Fundamental Algorithms for Scientific Computing in Python. Nature Methods 17, 261–272. https://doi.org/10.1038/s41592-019-0686-2. scipy.optimize.minimize dùng L-BFGS-B để tối ưu hàm mục tiêu Logistic trong nhánh ERA5.",
        "[20] Pedregosa, F., et al. (2011). Scikit-learn: Machine Learning in Python. Journal of Machine Learning Research, 12, 2825–2830. https://scikit-learn.org/stable/modules/linear_model.html. Công thức hàm mục tiêu chuẩn của Ridge, Logistic và K-means++ được cài đặt trực tiếp bằng NumPy/SciPy trong dự án để đảm bảo tái lập độc lập.",
        "[21] SciPy Developers. scipy.stats.spearmanr. https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.spearmanr.html. Hệ số tương quan hạng đơn điệu; dự án tính qua thứ hạng trung bình và đối chiếu độc lập bằng SciPy.",
        "[22] Open-Meteo. Global Flood API documentation. https://open-meteo.com/en/docs/flood-api. Tham số dùng thực tế: daily=river_discharge, models=consolidated_v4, timezone=GMT; lưu phản hồi và request trong data/hydrology.",
        "[23] Copernicus CEMS / ECMWF. River discharge and related historical data from the Global Flood Awareness System. https://ewds.climate.copernicus.eu/datasets/cems-glofas-historical. Lưu lượng mô hình LISFLOOD dùng ERA5 làm đầu vào; không phải quan trắc trạm độc lập.",
        "[24] Bộ Tài nguyên và Môi trường (2022). QCVN 47:2022/BTNMT – Quy chuẩn kỹ thuật quốc gia về quan trắc thủy văn, ban hành kèm Thông tư 22/2022/TT-BTNMT ngày 20/12/2022, hiệu lực 20/06/2023. https://vanban.chinhphu.vn/?docid=207442&pageid=27160. Chỉ dẫn bối cảnh quan trắc, không chứng nhận API tuân thủ quy chuẩn.",
    ]
    for r_txt in refs:
        pr = make_p(r_txt)
        pr.paragraph_format.line_spacing = 1.05
        pr.paragraph_format.space_after = Pt(4)
        for run in pr.runs:
            run.font.size = Pt(11)

    p_app = make_p("Phụ lục tái lập và nguồn minh chứng", style="Heading 1")
    add_bookmark(p_app, "appendix")
    app_paras = [
        "Ba nguồn đầu vào có hồ sơ riêng: data/era5/*.json (ERA5, 2017–2025, UTC+7), data/hydrology/*.json (GloFAS v4 consolidated, 2017–2021, UTC) và data/raw/vietnam_kttv_2017_2025_raw.json (mẫu kiểm thử mô phỏng đóng băng). Mỗi JSON dùng nguyên bytes để kiểm SHA-256 trước xử lý; không có mã sinh benchmark gốc.",
        f"Báo cáo có {n_tables} bảng và {n_figs} hình. Nguồn kết quả chính: outputs/real/*.csv và summary.json; outputs/hydrology/*.csv và provenance.json; SQLite ở outputs/kttv_weather.sqlite. Bằng chứng QC phụ lục lấy từ outputs/analysis.json và row_lineage.csv. Các đầu ra mô phỏng cũ còn được lưu để kiểm tra mã nhưng không được coi là kết quả khí quyển thực.",
        "Cài Python và pip install -r requirements.txt, sau đó chạy python scripts/run_project.py --skip-download để phát lại từ JSON. Cần LibreOffice nếu dựng lại báo cáo PDF hoặc dùng --workbook để tính lại Excel benchmark. Dựng báo cáo: python tools/build_final_report.py; kiểm tra: python tools/audit_report_consistency.py. Chỉ dùng --refresh khi chủ động tải phiên bản nguồn mới.",
        "Nội dung cần tiếp quản khi bảo vệ: nguồn và QC; chia tập và mô hình; diễn giải bảng/hình và giới hạn. Mỗi thành viên cần tự giải thích được mã và kết quả thuộc phần mình trình bày. Không suy diễn phân công này thành lịch sử đóng góp đã được xác nhận.",
    ]
    for ap_txt in app_paras:
        make_p(ap_txt)

    doc.core_properties.keywords = "khí tượng thủy văn, ERA5, kiểm soát chất lượng, dự báo thời tiết, Nhóm 13"
    doc.core_properties.last_modified_by = "Nhóm 13"
    doc.core_properties.comments = ""
    doc.core_properties.category = "Báo cáo học phần Nhập môn Khoa học dữ liệu"
    doc.core_properties.title = TITLE
    doc.core_properties.subject = "Báo cáo Tiểu luận 6 Chương - Nhập môn Khoa học dữ liệu (PTIT)"
    doc.core_properties.author = "Nhóm 13 (Đinh Quang Thái N22DCCN176, Đặng Ngọc Sơn N22DCCN070, Đặng Văn Chương N22DCCN012)"
    doc.save(str(TARGET_DOCX))
    clean_application_properties(TARGET_DOCX)

    convert_document(TARGET_DOCX, DOCS, "pdf")
    return indices, tables


def compute_exact_page_map(indices: dict, tables: dict) -> dict[str, int]:
    reader = PdfReader(str(TARGET_PDF))
    page_texts = [page.extract_text() or "" for page in reader.pages]
    ch1_pdf_idx = 6
    for idx, page in enumerate(reader.pages):
        if "Một hệ thống dự báo thời tiết cần dữ liệu" in page_texts[idx]:
            ch1_pdf_idx = idx
            break

    page_map: dict[str, int] = {}
    chapter_titles = re.findall(r"^# (.+)$", SOURCE.read_text(encoding="utf-8"), re.M)
    chapters = [(f"chapter_{i}", title) for i, title in enumerate(chapter_titles, 1)] + [
        ("appendix_benchmark", "Phụ lục A. Kiểm thử QC trên bộ mô phỏng"),
        ("references", "Tài liệu tham khảo"),
        ("appendix", "Phụ lục tái lập và nguồn minh chứng"),
    ]
    sections=re.findall(r"^## (.+)$",SOURCE.read_text(encoding="utf-8"),re.M)
    chapters += [(f"section_{i}",title) for i,title in enumerate(sections,1)]
    for bkmk, marker in chapters:
        for idx in range(ch1_pdf_idx, len(reader.pages)):
            txt = page_texts[idx]
            if " ".join(marker.split()) in " ".join(txt.split()):
                page_map[bkmk] = idx - ch1_pdf_idx + 1
                break

    for key, num in indices["figure"].items():
        marker = f"Hình {num}:"
        for idx in range(ch1_pdf_idx, len(reader.pages)):
            if marker in (page_texts[idx]):
                page_map[f"figure_{num}"] = idx - ch1_pdf_idx + 1
                break

    for key, num in indices["table"].items():
        marker = f"Bảng {num}:"
        for idx in range(ch1_pdf_idx, len(reader.pages)):
            if marker in (page_texts[idx]):
                page_map[f"table_{num}"] = idx - ch1_pdf_idx + 1
                break

    return page_map


def main() -> None:
    report_v2.write_source()
    indices, tables = render_once(page_map=None)
    exact_map = compute_exact_page_map(indices, tables)
    for _ in range(3):
        render_once(page_map=exact_map)
        new_map = compute_exact_page_map(indices, tables)
        if new_map == exact_map:
            break
        exact_map = new_map
    else:
        raise RuntimeError("TOC page map did not converge")
    reader = PdfReader(str(TARGET_PDF))
    print(f"Final PDF built: {len(reader.pages)} total pages. Exact TOC page map synchronized:", json.dumps(exact_map))


if __name__ == "__main__":
    main()
