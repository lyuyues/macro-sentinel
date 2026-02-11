"""Generate Chinese Semiconductor Industry Report PDF."""
import os
from fpdf import FPDF

OUTPUT_PATH = "output/Semiconductor_Industry_Report_CN.pdf"
FONT_PATH = "/Library/Fonts/Arial Unicode.ttf"


class SemiPDF(FPDF):
    def __init__(self):
        super().__init__()
        self.add_font("CJK", "", FONT_PATH)
        self.add_font("CJK", "B", FONT_PATH)
        self.add_font("CJK", "I", FONT_PATH)

    def header(self):
        if self.page_no() > 1:
            self.set_font("CJK", "I", 7)
            self.set_text_color(150, 150, 150)
            self.cell(95, 5, "\u534a\u5bfc\u4f53\u4ea7\u4e1a\u94fe\u6df1\u5ea6\u62a5\u544a")
            self.cell(95, 5, f"Page {self.page_no()}", align="R")
            self.ln(8)

    def ch_title(self, t):
        self.set_font("CJK", "B", 16)
        self.set_text_color(20, 50, 100)
        self.multi_cell(0, 10, t)
        y = self.get_y()
        self.set_draw_color(20, 50, 100)
        self.set_line_width(0.8)
        self.line(10, y, 200, y)
        self.set_line_width(0.2)
        self.ln(5)

    def sec(self, t):
        self.set_font("CJK", "B", 13)
        self.set_text_color(30, 70, 130)
        self.multi_cell(0, 8, t)
        self.ln(2)

    def sub(self, t):
        self.set_font("CJK", "B", 11)
        self.set_text_color(60, 60, 60)
        self.multi_cell(0, 7, t)
        self.ln(1)

    def p(self, t):
        self.set_font("CJK", "", 9.5)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, 5.2, t)
        self.ln(2)

    def bp(self, t):
        self.set_font("CJK", "B", 9.5)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, 5.2, t)
        self.ln(2)

    def li(self, t):
        self.set_font("CJK", "", 9.5)
        self.set_text_color(30, 30, 30)
        x = self.get_x()
        self.set_x(x + 4)
        self.multi_cell(0, 5, "- " + t)
        self.ln(0.5)

    def code(self, t):
        self.set_font("Courier", "", 8)
        self.set_fill_color(242, 242, 242)
        self.set_text_color(40, 40, 40)
        for line in t.split("\n"):
            s = line.encode("latin-1", errors="replace").decode("latin-1")
            self.cell(190, 4.5, "  " + s, fill=True)
            self.ln(4.5)
        self.ln(2)

    def tbl(self, headers, rows, cw=None):
        if cw is None:
            cw = [190 / len(headers)] * len(headers)
        if self.get_y() + 8 + len(rows) * 6 > 270:
            self.add_page()
        self.set_font("CJK", "B", 8)
        self.set_fill_color(20, 50, 100)
        self.set_text_color(255, 255, 255)
        for i, h in enumerate(headers):
            self.cell(cw[i], 7, h, border=1, fill=True, align="C")
        self.ln()
        self.set_font("CJK", "", 8)
        self.set_text_color(30, 30, 30)
        alt = False
        for row in rows:
            if self.get_y() + 6 > 275:
                self.add_page()
                self.set_font("CJK", "B", 8)
                self.set_fill_color(20, 50, 100)
                self.set_text_color(255, 255, 255)
                for i, h in enumerate(headers):
                    self.cell(cw[i], 7, h, border=1, fill=True, align="C")
                self.ln()
                self.set_font("CJK", "", 8)
                self.set_text_color(30, 30, 30)
                alt = False
            self.set_fill_color(240, 243, 250) if alt else self.set_fill_color(255, 255, 255)
            for i, c in enumerate(row):
                self.cell(cw[i], 6, str(c), border=1, fill=True, align="C")
            self.ln()
            alt = not alt
        self.ln(3)

    def box(self, label, text, rgb=(30, 80, 140)):
        r, g, b = rgb
        self.set_fill_color(min(r+210,255), min(g+180,255), min(b+210,255))
        self.set_draw_color(r, g, b)
        self.set_line_width(0.5)
        y = self.get_y()
        h = max(len(text) / 28 * 5 + 6, 16)
        self.rect(10, y, 190, h, style="DF")
        self.set_xy(14, y + 2)
        self.set_text_color(r, g, b)
        self.set_font("CJK", "B", 9)
        self.cell(0, 5, label)
        self.ln(5)
        self.set_x(14)
        self.set_font("CJK", "", 8.5)
        self.multi_cell(180, 4.5, text)
        self.set_y(y + h + 3)
        self.set_line_width(0.2)

    def chk(self, n=40):
        if self.get_y() + n > 270:
            self.add_page()


def build_pdf():
    pdf = SemiPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_margins(10, 10, 10)

    # COVER
    pdf.add_page()
    pdf.ln(30)
    pdf.set_font("CJK", "B", 30)
    pdf.set_text_color(20, 50, 100)
    pdf.multi_cell(0, 14, "\u534a\u5bfc\u4f53\u4ea7\u4e1a\u94fe\u6df1\u5ea6\u62a5\u544a", align="C")
    pdf.ln(3)
    pdf.set_font("CJK", "B", 18)
    pdf.set_text_color(60, 60, 60)
    pdf.cell(0, 10, "\u4ece\u6c99\u5b50\u5230\u82af\u7247\u7684\u5168\u4ef7\u503c\u94fe\u89e3\u6790", align="C")
    pdf.ln(15)
    pdf.set_draw_color(20, 50, 100)
    pdf.set_line_width(1)
    pdf.line(50, pdf.get_y(), 160, pdf.get_y())
    pdf.set_line_width(0.2)
    pdf.ln(15)
    pdf.set_font("CJK", "", 11)
    pdf.set_text_color(80, 80, 80)
    pdf.multi_cell(0, 7, (
        "\u4f5c\u8005\u89c6\u89d2\uff1a\u62e5\u6709\u4e24\u5ea7\u665f\u5706\u5382\uff0828nm + 5nm\uff09\u7684\u4ece\u4e1a\u8005\n"
        "\u76ee\u6807\u8bfb\u8005\uff1a\u5e0c\u671b\u7cfb\u7edf\u6027\u7406\u89e3\u534a\u5bfc\u4f53\u4ea7\u4e1a\u7684\u6295\u8d44\u4eba\n"
        "\u62a5\u544a\u65e5\u671f\uff1a2026\u5e742\u6708"
    ), align="C")
    pdf.ln(25)
    pdf.set_font("CJK", "I", 8)
    pdf.set_text_color(150, 150, 150)
    pdf.multi_cell(0, 4.5, "\u514d\u8d23\u58f0\u660e\uff1a\u672c\u62a5\u544a\u57fa\u4e8e\u516c\u5f00\u4fe1\u606f\u548c\u884c\u4e1a\u7ecf\u9a8c\u64b0\u5199\uff0c\u4e0d\u6784\u6210\u6295\u8d44\u5efa\u8bae\u3002\u6240\u6709\u8d22\u52a1\u6570\u636e\u4e3a\u4f30\u8ba1\u503c\u3002", align="C")

    # TOC
    pdf.add_page()
    pdf.ch_title("\u76ee\u5f55")
    pdf.set_font("CJK", "", 10)
    pdf.set_text_color(30, 30, 30)
    for ch, t in [
        ("Ch 1", "\u4ea7\u4e1a\u94fe\u5168\u666f\u56fe"),
        ("Ch 2", "\u4e0a\u6e38\uff1a\u6750\u6599\u4e0e\u8bbe\u5907"),
        ("Ch 3", "\u4e2d\u6e38\uff08\u4e00\uff09\uff1aEDA \u4e0e IP"),
        ("Ch 4", "\u4e2d\u6e38\uff08\u4e8c\uff09\uff1aIC \u8bbe\u8ba1"),
        ("Ch 5", "\u4e2d\u6e38\uff08\u4e09\uff09\uff1a\u665f\u5706\u5236\u9020"),
        ("Ch 6", "\u4e0b\u6e38\uff1a\u5c01\u88c5\u6d4b\u8bd5\u4e0e\u5148\u8fdb\u5c01\u88c5"),
        ("Ch 7", "\u7ec8\u7aef\u5e94\u7528\uff1a\u9700\u6c42\u9a71\u52a8\u529b\u5206\u6790"),
        ("Ch 8", "\u4e09\u79cd\u5546\u4e1a\u6a21\u5f0f\u5bf9\u6bd4"),
        ("Ch 9", "\u4ea7\u4e1a\u683c\u5c40\u4e0e\u53d1\u5c55\u8d8b\u52bf"),
        ("Ch 10", "\u6838\u5fc3\u98ce\u9669\u4e0e\u6311\u6218"),
        ("Ch 11", "\u672a\u6765\u673a\u4f1a\u4e0e\u6295\u8d44\u903b\u8f91"),
        ("\u9644\u5f55", "\u5173\u952e\u516c\u53f8\u901f\u67e5\u8868"),
    ]:
        pdf.cell(22, 8, ch)
        pdf.cell(0, 8, t)
        pdf.ln(8)

    # ===== CH1 =====
    pdf.add_page()
    pdf.ch_title("\u7b2c\u4e00\u7ae0\uff1a\u4ea7\u4e1a\u94fe\u5168\u666f\u56fe")
    pdf.p("\u534a\u5bfc\u4f53\u4ea7\u4e1a\u94fe\u662f\u4eba\u7c7b\u5386\u53f2\u4e0a\u6700\u590d\u6742\u7684\u5de5\u4e1a\u94fe\u6761\u3002\u4e00\u9897\u5148\u8fdb\u82af\u7247\u7684\u8bde\u751f\u9700\u8981\u8de8\u8d8a16\u4e2a\u56fd\u5bb6\u300170+\u6b21\u8de8\u5883\u8fd0\u8f93\u30011000+\u9053\u5de5\u5e8f\uff0c\u5386\u65f64-6\u4e2a\u6708\u3002")
    pdf.sec("\u4ef7\u503c\u5206\u914d\uff08\u4ee5\u4e00\u9897$100\u7684\u624b\u673aSoC\u4e3a\u4f8b\uff09")
    pdf.tbl(
        ["\u73af\u8282", "\u4ef7\u503c\u5360\u6bd4", "\u6bdb\u5229\u7387", "\u7279\u5f81"],
        [
            ["EDA/IP", "~3%", "75-85%", "\u9ad8\u5229\u6da6\uff0c\u5c0f\u5e02\u573a"],
            ["IC \u8bbe\u8ba1", "~35-50%", "50-70%", "\u5229\u6da6\u6700\u9ad8\uff0c\u8f7b\u8d44\u4ea7"],
            ["\u8bbe\u5907", "~8-12%", "45-65%", "\u5468\u671f\u6027\u5f3a\uff0c\u58c1\u5792\u6781\u9ad8"],
            ["\u6750\u6599", "~10-15%", "30-50%", "\u54c1\u7c7b\u7e41\u591a\uff0c\u65e5\u672c\u4e3b\u5bfc"],
            ["\u665f\u5706\u5236\u9020", "~15-25%", "40-60%", "\u8d44\u672c\u6700\u5bc6\u96c6"],
            ["\u5c01\u88c5\u6d4b\u8bd5", "~5-10%", "15-50%", "\u5148\u8fdb\u5c01\u88c5\u6539\u53d8\u683c\u5c40"],
        ],
        [38, 35, 35, 82],
    )

    # ===== CH2 =====
    pdf.add_page()
    pdf.ch_title("\u7b2c\u4e8c\u7ae0\uff1a\u4e0a\u6e38 \u2014 \u6750\u6599\u4e0e\u8bbe\u5907")
    pdf.sec("2.1 \u534a\u5bfc\u4f53\u6750\u6599\uff08300+\u79cd\uff09")
    pdf.sub("\u7845\u665f\u5706\uff08\u5360\u6750\u6599\u6210\u672c~35%\uff09")
    pdf.p("\u82af\u7247\u7684\u201c\u753b\u5e03\u201d\u3002\u4e3b\u6d41300mm\uff0812\u82f1\u5bf8\uff09\uff0c\u6bcf\u7247\u53ef\u5207\u51fa~500\u9897\u624b\u673a\u82af\u7247\u3002\u4e00\u7247\u665f\u5706\u7ea6$100-150\uff0c\u4f46\u5b83\u5c06\u53d8\u6210\u4ef7\u503c$5,000-50,000\u7684\u82af\u7247\u3002")
    pdf.tbl(
        ["\u516c\u53f8", "\u5e02\u5360\u7387", "\u7279\u70b9"],
        [
            ["\u4fe1\u8d8a\u5316\u5b66 Shin-Etsu", "~30%", "\u5168\u7403\u6700\u5927\uff0c\u8d28\u91cf\u6807\u6746"],
            ["SUMCO", "~25%", "\u65e5\u672c\u7b2c\u4e8c"],
            ["\u73af\u7403\u665f\u5706 GlobalWafers", "~15%", "\u53f0\u6e7e\uff0c\u6536\u8d2d\u4e86Siltronic"],
            ["SK Siltron", "~13%", "\u97e9\u56fd\uff0cSK\u96c6\u56e2\u65d7\u4e0b"],
            ["\u6caa\u7845\u4ea7\u4e1a", "~3%", "\u4e2d\u56fd\u5927\u9646\u6700\u5927"],
        ],
        [65, 35, 90],
    )
    pdf.box("\u5de5\u5382\u89c6\u89d2\uff1a", "\u7845\u665f\u5706\u662f\u6700\u5927\u7684\u5355\u9879\u6750\u6599\u652f\u51fa\u3002\u665f\u5706\u4f9b\u7ed9\u7d27\u5f20\u65f6\u6211\u4eec\u8981\u63d0\u524d12-18\u4e2a\u6708\u9501\u5b9a\u5408\u7ea6\u3002")

    pdf.chk(45)
    pdf.sub("\u5149\u523b\u80f6 Photoresist\uff08\u5361\u8116\u5b50\u6750\u6599\uff09")
    pdf.p("\u5149\u523b\u5de5\u827a\u6838\u5fc3\u8017\u6750\uff0c\u5c06\u7535\u8def\u56fe\u6848\u8f6c\u5370\u5230\u665f\u5706\u4e0a\u3002\u65e5\u672c\u51e0\u4e4e\u5784\u65ad\uff1aJSR(~25%), TOK(~22%), \u4fe1\u8d8a\u5316\u5b66(~15%)\u3002EUV\u5149\u523b\u80f6\u4e00\u74f6\u7ea61\u5347\uff0c\u552e\u4ef7$5,000-10,000\u3002")
    pdf.tbl(
        ["\u6750\u6599", "\u7528\u9014", "\u5173\u952e\u4f9b\u5e94\u5546"],
        [
            ["\u7279\u79cd\u6c14\u4f53", "\u8680\u523b\u3001\u6c89\u79ef", "Air Liquide, Linde"],
            ["CMP\u7814\u78e8\u6db2", "\u5316\u5b66\u673a\u68b0\u629b\u5149", "Cabot Micro, Fujimi"],
            ["\u6e85\u5c04\u9776\u6750", "\u91d1\u5c5e\u8584\u819c\u6c89\u79ef", "JX\u91d1\u5c5e, Honeywell"],
            ["\u5149\u63a9\u6a21\u57fa\u677f", "\u5149\u7f69\u8f7d\u4f53", "HOYA, AGC"],
        ],
        [50, 55, 85],
    )

    pdf.add_page()
    pdf.sec("2.2 \u534a\u5bfc\u4f53\u8bbe\u5907\uff08\u58c1\u5792\u6700\u9ad8\u3001\u62a4\u57ce\u6cb3\u6700\u6df1\uff09")
    pdf.tbl(
        ["\u5de5\u827a\u6b65\u9aa4", "\u4f5c\u7528", "\u9f99\u5934", "\u5e02\u5360\u7387", "\u5355\u53f0\u4ef7\u683c"],
        [
            ["\u5149\u523b", "\u66dd\u5149\u56fe\u6848", "ASML(\u8377\u5170)", "~90%", "EUV:$3.5-4\u4ebf"],
            ["\u523b\u8680", "\u53bb\u9664\u6750\u6599", "Lam Research", "~45%", "$500-1500\u4e07"],
            ["\u6c89\u79ef", "\u8584\u819c\u6c89\u79ef", "Applied Materials", "~40%", "$300-1000\u4e07"],
            ["\u79bb\u5b50\u6ce8\u5165", "\u6539\u53d8\u7535\u5b66\u6027\u8d28", "Applied Materials", "~70%", "$300-500\u4e07"],
            ["CMP", "\u5e73\u5766\u5316\u8868\u9762", "Applied Materials", "~60%", "$500\u4e07"],
            ["\u6e05\u6d17", "\u53bb\u9664\u6c61\u67d3\u7269", "Screen(\u65e5)", "~50%", "$200-500\u4e07"],
            ["\u68c0\u6d4b/\u91cf\u6d4b", "\u7f3a\u9677\u68c0\u6d4b", "KLA(\u7f8e)", "~55%", "$500-3000\u4e07"],
        ],
        [28, 28, 38, 26, 36, 34],
    )

    pdf.sub("ASML\uff1a\u4ea7\u4e1a\u94fe\u6700\u5173\u952e\u7684\u201c\u54bd\u5589\u201d")
    pdf.p("ASML\u662f\u5168\u7403\u552f\u4e00\u80fd\u5236\u9020EUV\uff08\u6781\u7d2b\u5916\u5149\u523b\u673a\uff09\u7684\u516c\u53f8\u3002\u6ca1\u6709EUV\uff0c\u5c31\u65e0\u6cd5\u5236\u90207nm\u4ee5\u4e0b\u7684\u5148\u8fdb\u82af\u7247\u3002")
    pdf.li("\u4e00\u53f0EUV\u5149\u523b\u673a\uff1a\u91cd~150\u5428\uff0c\u542b~10\u4e07\u4e2a\u96f6\u90e8\u4ef6\uff0c40\u4e2a\u96c6\u88c5\u7bb1\u8fd0\u8f93\uff0c\u5b89\u88c5\u8c03\u8bd56\u4e2a\u6708")
    pdf.li("\u4ea7\u80fd\uff1a\u6bcf\u5e74\u53ea\u80fd\u751f\u4ea7~50\u53f0EUV\uff0c\u4f9b\u4e0d\u5e94\u6c42")
    pdf.li("\u5ba2\u6237\uff1a\u5168\u7403\u53ea\u6709TSMC\u3001Samsung\u3001Intel\u4e09\u5bb6\u4e70\u5f97\u8d77")
    pdf.li("High-NA EUV\uff1a\u552e\u4ef7\u7ea6$3.5-4\u4ebf/\u53f0\uff0c2025\u5e74\u5f00\u59cb\u51fa\u8d27")
    pdf.box("\u5de5\u5382\u89c6\u89d2\uff1a", "\u6211\u76845nm\u4ea7\u7ebf\u914d\u7f6e\u4e8610\u53f0EUV\uff0c\u4ec5\u5149\u523b\u673a\u5c31\u6295\u5165$15-20\u4ebf\u3002ASML\u8bbe\u5907\u4ea4\u671f18-24\u4e2a\u6708\u3002\u6269\u4ea7\u4e0d\u662f\u6709\u94b1\u5c31\u80fd\u529e\u5230\u7684\u2014\u2014\u8bbe\u5907\u5c31\u90a3\u4e48\u591a\u3002")

    pdf.chk(50)
    pdf.sub("\u5efa\u8bbe\u4e00\u5ea75nm\u665f\u5706\u5382\u7684\u8bbe\u5907\u6e05\u5355")
    pdf.tbl(
        ["\u8bbe\u5907\u7c7b\u522b", "\u6570\u91cf", "\u603b\u6295\u5165"],
        [
            ["EUV\u5149\u523b\u673a", "10-15\u53f0", "$35-60\u4ebf"],
            ["DUV\u5149\u523b\u673a", "30-50\u53f0", "$10-15\u4ebf"],
            ["\u523b\u8680\u8bbe\u5907", "80-120\u53f0", "$10-15\u4ebf"],
            ["\u6c89\u79ef\u8bbe\u5907", "100-150\u53f0", "$8-12\u4ebf"],
            ["\u68c0\u6d4b\u91cf\u6d4b", "50-80\u53f0", "$5-10\u4ebf"],
            ["\u5176\u4ed6", "200+\u53f0", "$10-15\u4ebf"],
            ["\u603b\u8ba1", "~500-600\u53f0", "$80-130\u4ebf"],
        ],
        [63, 63, 64],
    )
    pdf.p("\u52a0\u4e0a\u5382\u623f\u3001\u6d01\u51c0\u5ba4\u5efa\u8bbe\uff0c\u4e00\u5ea7\u5148\u8fdb\u5236\u7a0b\u665f\u5706\u5382\u603b\u6295\u8d44\u5728$150-200\u4ebf\u7ea7\u522b\u3002")

    # ===== CH3 =====
    pdf.add_page()
    pdf.ch_title("\u7b2c\u4e09\u7ae0\uff1aEDA \u4e0e IP")
    pdf.sec("3.1 EDA\uff08\u7535\u5b50\u8bbe\u8ba1\u81ea\u52a8\u5316\uff09")
    pdf.p("EDA\u662f\u82af\u7247\u8bbe\u8ba1\u5e08\u7528\u6765\u8bbe\u8ba1\u82af\u7247\u7684\u8f6f\u4ef6\u5de5\u5177\uff0c\u7c7b\u4f3c\u4e8e\u5efa\u7b51\u5e08\u7684CAD\u8f6f\u4ef6\uff0c\u4f46\u590d\u6742\u5ea6\u9ad8\u51fa\u51e0\u4e2a\u6570\u91cf\u7ea7\u3002\u4e00\u9897\u73b0\u4ee3SoC\u5305\u542b\u6570\u767e\u4ebf\u4e2a\u664b\u4f53\u7ba1\uff0c\u4e0d\u53ef\u80fd\u624b\u5de5\u8bbe\u8ba1\u3002")
    pdf.bp("\u5e02\u573a\u683c\u5c40\uff1a\u7f8e\u56fd\u4e09\u5de8\u5934\u5784\u65ad")
    pdf.tbl(
        ["\u516c\u53f8", "Ticker", "2025\u6536\u5165", "\u5e02\u5360\u7387", "\u6838\u5fc3\u5f3a\u9879"],
        [
            ["Synopsys", "SNPS", "~$65\u4ebf", "~33%", "\u7efc\u5408\u3001\u4eff\u771f\u3001IP"],
            ["Cadence", "CDNS", "~$45\u4ebf", "~30%", "\u6a21\u62df\u8bbe\u8ba1\u3001\u9a8c\u8bc1"],
            ["Siemens EDA", "\u79c1\u6709", "~$20\u4ebf", "~15%", "PCB\u3001IC\u5c01\u88c5"],
        ],
        [35, 25, 30, 28, 72],
    )
    pdf.bp("\u4e3a\u4ec0\u4e48EDA\u662f\u597d\u751f\u610f\uff1f")
    pdf.li("\u8ba2\u9605\u6a21\u5f0f\uff08SaaS\uff09\uff0c\u6536\u5165\u7a33\u5b9a\u53ef\u9884\u6d4b")
    pdf.li("\u5ba2\u6237\u8f6c\u6362\u6210\u672c\u6781\u9ad8\uff08\u5de5\u7a0b\u5e08\u57f9\u8bad + \u8bbe\u8ba1\u6d41\u7a0b\u7ed1\u5b9a\uff09")
    pdf.li("\u7814\u53d1\u58c1\u5792\uff1a40+\u5e74\u79ef\u7d2f\u7684\u7b97\u6cd5\u548c\u5de5\u827a\u5e93")
    pdf.li("\u6bdb\u5229\u7387~80%\uff0c\u7ecf\u8425\u5229\u6da6\u7387~30-35%")

    pdf.sec("3.2 IP\u6838\uff08\u77e5\u8bc6\u4ea7\u6743\uff09")
    pdf.p("IP\u6838\u662f\u9884\u5148\u8bbe\u8ba1\u597d\u7684\u3001\u53ef\u590d\u7528\u7684\u7535\u8def\u6a21\u5757\u3002\u82af\u7247\u8bbe\u8ba1\u516c\u53f8\u8d2d\u4e70IP\u6838\u6765\u52a0\u901f\u5f00\u53d1\uff0c\u5c31\u50cf\u7a0b\u5e8f\u5458\u4f7f\u7528\u5f00\u6e90\u5e93\u4e00\u6837\u3002")
    pdf.sub("ARM\uff1a\u6700\u91cd\u8981\u7684IP\u516c\u53f8")
    pdf.li("ARM\u4e0d\u5236\u9020\u4efb\u4f55\u82af\u7247\uff0c\u53ea\u8bbe\u8ba1CPU\u67b6\u6784\u5e76\u6388\u6743")
    pdf.li("\u5168\u740999%\u667a\u80fd\u624b\u673a\u300195%\u7269\u8054\u7f51\u82af\u7247\u90fd\u7528ARM\u67b6\u6784")
    pdf.li("\u5546\u4e1a\u6a21\u5f0f\uff1a\u6388\u6743\u8d39($1-10M/\u5ba2\u6237) + \u7248\u7a0e($0.01-0.05/\u9897)")
    pdf.li("2025\u5e74\u6536\u5165\u7ea6$38\u4ebf\uff0c\u4f46\u5f71\u54cd\u7684\u82af\u7247\u5e02\u573a\u4ef7\u503c\u8d85$2000\u4ebf")

    # ===== CH4 =====
    pdf.add_page()
    pdf.ch_title("\u7b2c\u56db\u7ae0\uff1aIC \u8bbe\u8ba1\uff08Fabless\uff09")
    pdf.bp("\u8fd9\u662f\u534a\u5bfc\u4f53\u4ef7\u503c\u94fe\u4e2d\u5229\u6da6\u7387\u6700\u9ad8\u3001\u6210\u957f\u6027\u6700\u5f3a\u7684\u73af\u8282\u3002")
    pdf.p("IC\u8bbe\u8ba1\u516c\u53f8\uff08Fabless\uff09\u53ea\u505a\u82af\u7247\u8bbe\u8ba1\uff0c\u4e0d\u62e5\u6709\u5de5\u5382\uff0c\u5c06\u5236\u9020\u5916\u5305\u7ed9TSMC\u7b49\u4ee3\u5de5\u5382\u3002")

    pdf.sec("4.1 \u4e3b\u8981\u82af\u7247\u54c1\u7c7b\u4e0e\u9f99\u5934")
    pdf.tbl(
        ["\u54c1\u7c7b", "\u9f99\u5934", "2025\u6536\u5165", "\u6bdb\u5229\u7387", "\u6838\u5fc3\u58c1\u5792"],
        [
            ["GPU/AI\u52a0\u901f\u5668", "NVIDIA", "~$1300\u4ebf", "73-78%", "CUDA\u751f\u6001"],
            ["\u624b\u673aSoC", "Qualcomm", "~$420\u4ebf", "55-58%", "\u57fa\u5e26\u4e13\u5229"],
            ["\u624b\u673aSoC#2", "MediaTek", "~$180\u4ebf", "45-48%", "\u6027\u4ef7\u6bd4"],
            ["\u6570\u636e\u4e2d\u5fc3CPU", "Intel/AMD", "~$150\u4ebf", "50-55%", "x86\u751f\u6001"],
            ["\u7f51\u7edc\u82af\u7247", "Broadcom", "~$510\u4ebf", "65-70%", "\u5e76\u8d2d+\u591a\u5143\u5316"],
            ["\u81ea\u7814\u82af\u7247", "Apple/Google", "N/A", "N/A", "\u5782\u76f4\u6574\u5408"],
        ],
        [35, 30, 30, 25, 70],
    )

    pdf.sec("4.2 \u82af\u7247\u8bbe\u8ba1\u6210\u672c\u98d9\u5347")
    pdf.tbl(
        ["\u5236\u7a0b\u8282\u70b9", "\u8bbe\u8ba1\u6210\u672c", "\u56e2\u961f\u89c4\u6a21", "\u8bbe\u8ba1\u5468\u671f"],
        [
            ["28nm", "~$5000\u4e07", "100-200\u4eba", "12-18\u6708"],
            ["7nm", "~$3\u4ebf", "300-500\u4eba", "18-24\u6708"],
            ["5nm", "~$5\u4ebf", "500-800\u4eba", "18-24\u6708"],
            ["3nm", "~$7-10\u4ebf", "800-1500\u4eba", "24-30\u6708"],
            ["2nm(GAA)", "~$10-15\u4ebf", "1000+\u4eba", "24-36\u6708"],
        ],
        [40, 50, 50, 50],
    )
    pdf.box("\u5de5\u5382\u89c6\u89d2\uff1a", "3nm\u5149\u7f69\u8d39\u5c31\u8981$2000-3000\u4e07\u3002\u53ea\u6709\u5e74\u8425\u6536\u8fc7\u767e\u4ebf\u7684\u516c\u53f8\u624d\u80fd\u6301\u7eed\u6295\u5165\u6700\u5148\u8fdb\u5236\u7a0b\u3002\u5148\u8fdb\u5236\u7a0b\u5ba2\u6237\u4ece28nm\u65f6\u4ee3\u7684\u6570\u767e\u5bb6\u7f29\u51cf\u52303nm\u7684\u4e0d\u523010\u5bb6\u3002")

    pdf.chk(50)
    pdf.sec("4.3 NVIDIA\uff1aAI\u65f6\u4ee3\u7684\u201c\u5370\u949e\u673a\u201d")
    pdf.li("\u5e02\u503c\uff1a~$3\u4e07\u4ebf\uff08\u5168\u7403\u524d\u4e09\uff09")
    pdf.li("\u6838\u5fc3\u4ea7\u54c1\uff1aH100/H200/B100/B200 GPU\uff0c\u7528\u4e8eAI\u8bad\u7ec3\u548c\u63a8\u7406")
    pdf.li("\u62a4\u57ce\u6cb3\uff1a\u4e0d\u662f\u786c\u4ef6\u672c\u8eab\uff0c\u800c\u662fCUDA\u8f6f\u4ef6\u751f\u6001\u2014\u2014\u5168\u7403\u6570\u767e\u4e07AI\u5f00\u53d1\u8005\u7684\u4ee3\u7801\u90fd\u57fa\u4e8eCUDA")
    pdf.li("\u6bdb\u5229\u7387\uff1a75%+\uff0c\u6bcf\u5356$1\u7684\u82af\u7247\uff0c$0.75\u662f\u6bdb\u5229")
    pdf.li("\u5236\u9020\uff1a100%\u5916\u5305\u7ed9TSMC\uff085nm/4nm\uff09")

    # ===== CH5 =====
    pdf.add_page()
    pdf.ch_title("\u7b2c\u4e94\u7ae0\uff1a\u665f\u5706\u5236\u9020")
    pdf.sec("5.1 \u5236\u9020\u7684\u672c\u8d28\uff1a\u5728\u539f\u5b50\u5c3a\u5ea6\u4e0a\u96d5\u523b")
    pdf.p("\u5236\u9020\u4e00\u9897\u82af\u7247\u9700\u89811000+\u9053\u5de5\u5e8f\u3002\u6838\u5fc3\u6b65\u9aa4\u5faa\u73af50-80\u6b21\uff08\u5c42\uff09\u3002")
    pdf.li("3nm\u5236\u7a0b\uff1a\u664b\u4f53\u7ba1\u6805\u6781\u5bbd\u5ea6\u7ea63nm\uff0c\u76f8\u5f53\u4e8e15\u4e2a\u539f\u5b50\u6392\u5217\u7684\u5bbd\u5ea6")
    pdf.li("\u6d01\u51c0\u5ea6\u8981\u6c42\uff1aClass 1\u6d01\u51c0\u5ba4\uff0c\u6bd4\u624b\u672f\u5ba4\u6d01\u51c010,000\u500d")
    pdf.li("\u6c34\u548c\u7535\uff1a\u4e00\u5ea7\u5148\u8fdb\u665f\u5706\u5382\u6bcf\u5929\u7528\u6c34~5\u4e07\u5428\uff0c\u5e74\u7528\u7535~20-30\u4ebf\u5ea6")

    pdf.sec("5.2 \u5236\u7a0b\u8282\u70b9\u6f14\u8fdb")
    pdf.tbl(
        ["\u8282\u70b9", "\u91cf\u4ea7\u5e74\u4efd", "\u7ed3\u6784", "\u4e3b\u8981\u73a9\u5bb6", "\u5178\u578b\u4ea7\u54c1"],
        [
            ["28nm", "2011", "Planar", "TSMC,SS,GF,SMIC", "IoT,\u6c7d\u8f66"],
            ["14/16nm", "2014", "FinFET", "TSMC,SS,Intel,GF", "\u4e2d\u7aef\u624b\u673a"],
            ["7nm", "2018", "FinFET", "TSMC, Samsung", "\u65d7\u8230,AMD CPU"],
            ["5nm", "2020", "FinFET", "TSMC, Samsung", "iPhone,M1,AI"],
            ["3nm", "2022", "FinFET/GAA", "TSMC, Samsung", "iPhone15Pro,M3"],
            ["2nm", "2025", "GAA", "TSMC,SS,Intel", "\u4e0b\u4e00\u4ee3\u65d7\u8230"],
        ],
        [22, 25, 28, 55, 40, 20],
    )
    pdf.p("\u5173\u952e\u8f6c\u6298\u70b9\uff1a\u4eceFinFET\u5230GAA\uff08\u5168\u73af\u7ed5\u6805\u6781\uff09\u662f\u81ea2011\u5e74FinFET\u4ee5\u6765\u6700\u5927\u7684\u7ed3\u6784\u53d8\u9769\u3002")

    pdf.sec("5.3 \u5168\u7403\u4ee3\u5de5\u683c\u5c40")
    pdf.bp("TSMC\uff08\u53f0\u79ef\u7535\uff09\uff1a\u7edd\u5bf9\u7684\u738b\u8005")
    pdf.tbl(
        ["\u4ee3\u5de5\u5382", "\u6700\u5148\u8fdb\u5236\u7a0b", "\u5e02\u5360\u7387", "\u6838\u5fc3\u5ba2\u6237", "\u5730\u4f4d"],
        [
            ["TSMC", "3nm/2nm", "~60%", "Apple,NVIDIA,AMD", "\u6280\u672f+\u826f\u7387\u78be\u538b"],
            ["Samsung", "3nm GAA", "~12%", "Qualcomm,Google", "GAA\u5148\u884c\u4f46\u826f\u7387\u4f4e"],
            ["Intel Foundry", "18A(~2nm)", "~3%", "\u81ea\u7528\u4e3a\u4e3b", "\u8f6c\u578b\u4e2d\uff0c\u524d\u666f\u4e0d\u786e\u5b9a"],
            ["GlobalFoundries", "12nm", "~6%", "AMD,\u6c7d\u8f66", "\u4e13\u6ce8\u6210\u719f+\u7279\u6b8a\u5de5\u827a"],
            ["SMIC", "7nm(DUV)", "~6%", "\u534e\u4e3a,\u4e2d\u56fd", "\u88ab\u5236\u88c1\uff0c\u65e0\u6cd5\u83b7\u53d6EUV"],
            ["UMC", "14nm", "~7%", "\u9a71\u52a8IC,WiFi", "\u6210\u719f\u5236\u7a0b\uff0c\u5229\u6da6\u7a33\u5b9a"],
        ],
        [35, 28, 22, 42, 42, 21],
    )

    pdf.add_page()
    pdf.sec("5.4 \u5de5\u5382\u6210\u672c\u7ed3\u6784\uff08\u771f\u5b9e\u89c6\u89d2\uff09")
    pdf.sub("28nm\u5de5\u5382\uff08\u6708\u4ea7\u80fd4\u4e07\u7247\uff0c\u603b\u6295\u8d44~$50\u4ebf\uff09")
    pdf.tbl(
        ["\u6210\u672c\u9879", "\u5e74\u5ea6\u652f\u51fa", "\u5360\u6bd4"],
        [
            ["\u6298\u65e7\uff08\u8bbe\u5907+\u5382\u623f\uff09", "$6\u4ebf", "40%"],
            ["\u6750\u6599", "$3\u4ebf", "20%"],
            ["\u4eba\u5de5", "$2.5\u4ebf", "17%"],
            ["\u6c34\u7535\u6c14", "$1.5\u4ebf", "10%"],
            ["\u7ef4\u62a4\u4fdd\u517b", "$1\u4ebf", "7%"],
            ["\u5176\u4ed6", "$1\u4ebf", "6%"],
            ["\u603b\u8fd0\u8425\u6210\u672c", "~$15\u4ebf", "100%"],
        ],
        [75, 55, 60],
    )
    pdf.li("\u6bcf\u7247\u665f\u5706\u6210\u672c~$3,000 | \u552e\u4ef7~$4,500-5,000 | \u6bdb\u5229\u7387~35-40%")
    pdf.li("\u6298\u65e7\u5b8c\u6bd5\u540e\u5229\u6da6\u7387\u53ef\u8fbe50%+\uff0c\u662f\u4e00\u53f0\u73b0\u91d1\u5236\u9020\u673a\u5668\uff01")

    pdf.chk(50)
    pdf.sub("5nm\u5de5\u5382\uff08\u6708\u4ea7\u80fd5\u4e07\u7247\uff0c\u603b\u6295\u8d44~$180\u4ebf\uff09")
    pdf.tbl(
        ["\u6210\u672c\u9879", "\u5e74\u5ea6\u652f\u51fa", "\u5360\u6bd4"],
        [
            ["\u6298\u65e7", "$25\u4ebf", "50%"],
            ["\u6750\u6599", "$8\u4ebf", "16%"],
            ["\u4eba\u5de5", "$5\u4ebf", "10%"],
            ["\u6c34\u7535\u6c14", "$3\u4ebf", "6%"],
            ["\u7ef4\u62a4+\u5907\u4ef6", "$4\u4ebf", "8%"],
            ["EUV\u5149\u6e90\u66f4\u6362\u7b49", "$2\u4ebf", "4%"],
            ["\u5176\u4ed6", "$3\u4ebf", "6%"],
            ["\u603b\u8fd0\u8425\u6210\u672c", "~$50\u4ebf", "100%"],
        ],
        [75, 55, 60],
    )
    pdf.li("\u6bcf\u7247\u6210\u672c~$8,500 | \u552e\u4ef7~$16,000-18,000 | \u6bdb\u5229\u7387~50-55%")
    pdf.li("\u826f\u7387\u4ece50%(\u521d\u671f)\u523090%+(\u6210\u719f)\u51b3\u5b9a\u76c8\u4e8f")

    # ===== CH6 =====
    pdf.add_page()
    pdf.ch_title("\u7b2c\u516d\u7ae0\uff1a\u5c01\u88c5\u6d4b\u8bd5\u4e0e\u5148\u8fdb\u5c01\u88c5")
    pdf.sec("6.1 \u4f20\u7edf\u5c01\u88c5\u6d4b\u8bd5\uff08OSAT\uff09")
    pdf.tbl(
        ["\u516c\u53f8", "\u603b\u90e8", "2025\u6536\u5165", "\u5e02\u5360\u7387", "\u6838\u5fc3\u5ba2\u6237"],
        [
            ["\u65e5\u6708\u5149 ASE", "\u53f0\u6e7e", "~$200\u4ebf", "~30%", "Apple,NVIDIA,AMD"],
            ["\u5b89\u9760 Amkor", "\u7f8e\u56fd", "~$70\u4ebf", "~15%", "Apple,Qualcomm"],
            ["\u957f\u7535\u79d1\u6280 JCET", "\u4e2d\u56fd", "~$40\u4ebf", "~10%", "\u4e2d\u56fd\u5ba2\u6237"],
            ["\u901a\u5bcc\u5fae\u7535", "\u4e2d\u56fd", "~$25\u4ebf", "~6%", "AMD"],
        ],
        [35, 22, 30, 25, 78],
    )

    pdf.sec("6.2 \u5148\u8fdb\u5c01\u88c5\uff1a\u6e38\u620f\u89c4\u5219\u7684\u6539\u53d8\u8005")
    pdf.p("\u5f53\u5355\u9897\u82af\u7247\u7684\u5236\u7a0b\u8fdb\u6b65\u8d8a\u6765\u8d8a\u96be\uff08\u6469\u5c14\u5b9a\u5f8b\u653e\u7f13\uff09\u65f6\uff0c\u628a\u591a\u9897\u82af\u7247\u5c01\u88c5\u5728\u4e00\u8d77\u6210\u4e3a\u63d0\u5347\u6027\u80fd\u7684\u65b0\u8def\u5f84\u3002\u8fd9\u5c31\u662f\u201cMore than Moore\u201d\u3002")
    pdf.tbl(
        ["\u6280\u672f", "\u63d0\u4f9b\u8005", "\u5e94\u7528", "\u7279\u70b9"],
        [
            ["CoWoS", "TSMC", "NVIDIA H100/B100", "GPU+HBM\u5e76\u6392\u5728\u7845\u4e2d\u4ecb\u5c42"],
            ["InFO", "TSMC", "iPhone AP", "\u65e0\u57fa\u677f\uff0c\u66f4\u8584\u66f4\u4fbf\u5b9c"],
            ["EMIB", "Intel", "Intel GPU", "\u5c0f\u578b\u7845\u6865\u8fde\u63a5"],
            ["Foveros", "Intel", "Meteor Lake", "3D\u5806\u53e0"],
            ["HBM", "SK Hynix/SS", "AI GPU", "\u5185\u5b58\u58068-12\u5c42\uff0cTSV\u4e92\u8fde"],
            ["Chiplet", "AMD/Intel/Apple", "EPYC,M3 Ultra", "\u591a\u4e2a\u5c0f\u82af\u7247\u4e92\u8fde"],
        ],
        [28, 38, 48, 76],
    )
    pdf.bp("CoWoS\u7684\u74f6\u9888\u6548\u5e94\uff1a")
    pdf.li("2024\u5e74CoWoS\u6708\u4ea7\u80fd~3.5\u4e07\u7247 -> 2025\u5e74\u8ba1\u5212\u6269\u81f3~6\u4e07\u7247")
    pdf.li("\u9700\u6c42\u4ecd\u8fdc\u8d85\u4f9b\u7ed9")
    pdf.li("TSMC CoWoS\u6536\u5165\uff1a~$20\u4ebf(2022) -> ~$100\u4ebf+(2025)")

    pdf.chk(45)
    pdf.sec("6.3 HBM\uff1aAI\u65f6\u4ee3\u7684\u201c\u5f39\u836f\u201d")
    pdf.tbl(
        ["HBM\u4ee3\u6b21", "\u5e26\u5bbd", "\u5806\u53e0\u5c42\u6570", "\u5bb9\u91cf", "\u4e3b\u8981\u7528\u9014"],
        [
            ["HBM2e", "460 GB/s", "8\u5c42", "16GB", "A100"],
            ["HBM3", "819 GB/s", "8\u5c42", "24GB", "H100"],
            ["HBM3e", "1.2 TB/s", "8-12\u5c42", "36-48GB", "H200,B100"],
            ["HBM4", "2+ TB/s", "12-16\u5c42", "48-64GB", "2026\u5e74"],
        ],
        [32, 35, 30, 35, 58],
    )
    pdf.tbl(
        ["\u516c\u53f8", "HBM\u5e02\u5360\u7387", "\u4f18\u52bf"],
        [
            ["SK Hynix", "~50%", "\u6280\u672f\u9886\u51481-2\u4ee3\uff0cNVIDIA\u9996\u9009"],
            ["Samsung", "~35%", "\u4ea7\u80fd\u5927\uff0c\u8ffd\u8d76\u4e2d"],
            ["Micron", "~15%", "\u540e\u53d1\u5165\u5c40\uff0c\u4ef7\u683c\u7ade\u4e89"],
        ],
        [50, 45, 95],
    )
    pdf.p("SK Hynix\u7684HBM\u4e1a\u52a1\u6bdb\u5229\u7387\u9ad8\u8fbe70%+\uff08\u666e\u901dDRAM~40%\uff09\uff0cHBM\u5df2\u6210\u4e3a\u5176\u6700\u8d5a\u94b1\u7684\u4e1a\u52a1\u3002")

    # ===== CH7 =====
    pdf.add_page()
    pdf.ch_title("\u7b2c\u4e03\u7ae0\uff1a\u7ec8\u7aef\u5e94\u7528\u4e0e\u9700\u6c42\u9a71\u52a8\u529b")
    pdf.sec("7.1 \u9700\u6c42\u7ed3\u6784\uff082025\u5e74\u5168\u7403\u534a\u5bfc\u4f53\u5e02\u573a~$6000-6500\u4ebf\uff09")
    pdf.tbl(
        ["\u7ec8\u7aef\u5e02\u573a", "\u5360\u6bd4", "\u589e\u957f\u9a71\u52a8", "\u6838\u5fc3\u82af\u7247\u7c7b\u578b"],
        [
            ["\u6570\u636e\u4e2d\u5fc3/AI", "~30%", "AI\u8bad\u7ec3\u548c\u63a8\u7406\u9700\u6c42\u7206\u53d1", "GPU,ASIC,HBM"],
            ["\u667a\u80fd\u624b\u673a", "~22%", "\u7aef\u4fa7AI, 5G\u5347\u7ea7", "\u79fb\u52a8SoC,\u5185\u5b58"],
            ["PC/\u670d\u52a1\u5668CPU", "~15%", "AI PC, \u4f01\u4e1a\u66f4\u65b0\u5468\u671f", "CPU, GPU"],
            ["\u6c7d\u8f66", "~12%", "\u7535\u52a8\u5316, \u81ea\u52a8\u9a7e\u9a76", "\u529f\u7387\u534a\u5bfc\u4f53,MCU"],
            ["\u5de5\u4e1a/IoT", "~10%", "\u5de5\u4e1a\u81ea\u52a8\u5316", "MCU,\u4f20\u611f\u5668"],
            ["\u6d88\u8d39\u7535\u5b50", "~8%", "AR/VR, \u53ef\u7a7f\u6234", "\u5404\u7c7b\u82af\u7247"],
            ["\u901a\u4fe1\u57fa\u7840\u8bbe\u65bd", "~3%", "5G\u57fa\u7ad9, \u5149\u901a\u4fe1", "FPGA, DSP"],
        ],
        [40, 18, 52, 55, 25],
    )
    pdf.sec("7.2 AI\uff1a\u5f53\u524d\u6700\u5f3a\u9a71\u52a8\u529b")
    pdf.p("AI\u8bad\u7ec3\u548c\u63a8\u7406\u5bf9\u7b97\u529b\u7684\u9700\u6c42\u6b63\u5728\u4ee5\u6bcf\u5e744-5\u500d\u7684\u901f\u5ea6\u589e\u957f\uff1a")
    pdf.li("2024\u5e74\uff1a\u5168\u7403AI\u82af\u7247\u5e02\u573a~$600\u4ebf")
    pdf.li("2025\u5e74\uff1a\u9884\u8ba1~$900-1000\u4ebf")
    pdf.li("2028\u5e74\uff1a\u9884\u8ba1~$2000-3000\u4ebf")

    pdf.sec("7.3 \u6c7d\u8f66\uff1a\u6700\u88ab\u4f4e\u4f30\u7684\u589e\u91cf\u5e02\u573a")
    pdf.li("\u4f20\u7edf\u71c3\u6cb9\u8f66\u542b$300-500\u534a\u5bfc\u4f53")
    pdf.li("\u9ad8\u7aef\u7535\u52a8\u8f66\uff08Tesla Model S\uff09\u542b$1,500-3,000")
    pdf.li("L4\u81ea\u52a8\u9a7e\u9a76\u8f66\u8f86\u53ef\u80fd\u8fbe$5,000+")

    # ===== CH8 =====
    pdf.add_page()
    pdf.ch_title("\u7b2c\u516b\u7ae0\uff1a\u4e09\u79cd\u5546\u4e1a\u6a21\u5f0f\u5bf9\u6bd4")
    pdf.sec("IDM\uff08\u5782\u76f4\u6574\u5408\uff09\u2014 \u4ece\u8bbe\u8ba1\u5230\u5236\u9020\u5230\u5c01\u88c5\u5168\u90e8\u81ea\u5df1\u505a")
    pdf.tbl(
        ["\u516c\u53f8", "\u6838\u5fc3\u4ea7\u54c1", "\u4f18\u52bf", "\u52a3\u52bf"],
        [
            ["Intel", "CPU, FPGA", "\u8bbe\u8ba1-\u5236\u9020\u534f\u540c\u4f18\u5316", "\u8d44\u672c\u5f00\u652f\u5de8\u5927"],
            ["Samsung", "\u5185\u5b58, \u4ee3\u5de5", "\u89c4\u6a21\u7ecf\u6d4e", "\u4e0e\u5ba2\u6237\u7ade\u4e89\u51b2\u7a81"],
            ["TI", "\u6a21\u62dfIC", "\u957f\u751f\u547d\u5468\u671f\uff0c\u7a33\u5b9a", "\u589e\u957f\u7f13\u6162"],
            ["Infineon", "\u529f\u7387\u534a\u5bfc\u4f53", "\u5782\u76f4\u6574\u5408\u964d\u672c", "\u53d7\u6c7d\u8f66/\u5de5\u4e1a\u5468\u671f\u5f71\u54cd"],
        ],
        [30, 40, 55, 65],
    )
    pdf.sec("Fabless\uff08\u65e0\u5de5\u5382\u8bbe\u8ba1\uff09\u2014 \u53ea\u505a\u8bbe\u8ba1\uff0c\u5236\u9020\u5916\u5305")
    pdf.tbl(
        ["\u516c\u53f8", "\u4ea7\u54c1", "\u4f18\u52bf", "\u52a3\u52bf"],
        [
            ["NVIDIA", "GPU, AI", "\u8f7b\u8d44\u4ea7\uff0c\u4e13\u6ce8\u521b\u65b0", "\u53d7\u4ee3\u5de5\u4ea7\u80fd\u5236\u7ea6"],
            ["AMD", "CPU, GPU", "\u7075\u6d3b\u9009\u62e9\u5236\u7a0b", "\u4e0eNVIDIA\u7ade\u4e89\u52a0\u5267"],
            ["Qualcomm", "\u79fb\u52a8SoC", "\u4e13\u5229+\u82af\u7247\u53cc\u6536\u5165", "\u82f9\u679c\u81ea\u7814\u66ff\u4ee3\u98ce\u9669"],
            ["Broadcom", "\u7f51\u7edc,ASIC", "\u591a\u5143\u5316+\u5e76\u8d2d\u6574\u5408", "\u6574\u5408\u98ce\u9669"],
        ],
        [30, 35, 55, 70],
    )
    pdf.sec("Foundry\uff08\u7eaf\u4ee3\u5de5\uff09\u2014 \u53ea\u505a\u5236\u9020\uff0c\u4e0d\u8bbe\u8ba1\u81ea\u6709\u82af\u7247")
    pdf.tbl(
        ["\u516c\u53f8", "\u4f18\u52bf", "\u52a3\u52bf"],
        [
            ["TSMC", "\u4e0d\u4e0e\u5ba2\u6237\u7ade\u4e89\uff0c\u4fe1\u4efb\u5ea6\u9ad8", "\u5ba2\u6237\u96c6\u4e2d\u5ea6\u9ad8"],
            ["GlobalFoundries", "\u7279\u6b8a\u5de5\u827a\u5dee\u5f02\u5316", "\u653e\u5f03\u5148\u8fdb\u5236\u7a0b\uff0c\u589e\u957f\u53d7\u9650"],
            ["UMC", "\u6210\u719f\u5236\u7a0b\u5229\u6da6\u7a33\u5b9a", "\u589e\u957f\u5929\u82b1\u677f\u660e\u663e"],
        ],
        [50, 70, 70],
    )
    pdf.box("\u6295\u8d44\u542f\u793a\uff1a", "Fabless\u6a21\u5f0f\u5728AI\u65f6\u4ee3\u80dc\u51fa\u3002\u4f46\u7ec8\u7aef\u7cfb\u7edf\u516c\u53f8\uff08Apple, Google, Amazon\uff09\u4e5f\u5728\u81ea\u7814\u82af\u7247\uff0c\u8fd9\u5bf9\u4f20\u7edf\u82af\u7247\u516c\u53f8\u6784\u6210\u5a01\u80c1\u3002", (20, 100, 60))

    # ===== CH9 =====
    pdf.add_page()
    pdf.ch_title("\u7b2c\u4e5d\u7ae0\uff1a\u4ea7\u4e1a\u683c\u5c40\u4e0e\u53d1\u5c55\u8d8b\u52bf")
    pdf.sec("\u8d8b\u52bf\u4e00\uff1aAI\u9a71\u52a8\u7684\u8d85\u7ea7\u5468\u671f")
    pdf.li("AI\u8bad\u7ec3\u7b97\u529b\u6bcf3.4\u4e2a\u6708\u7ffb\u4e00\u500d\uff08\u8fdc\u8d85\u6469\u5c14\u5b9a\u5f8b\u76842\u5e74\uff09")
    pdf.li("\u6bcf\u5ea7AI\u6570\u636e\u4e2d\u5fc3\u6295\u8d44$50-100\u4ebf\uff0c60-70%\u662f\u534a\u5bfc\u4f53")
    pdf.li("\u5fae\u8f6f+Google+Meta+Amazon AI\u8d44\u672c\u652f\u51fa\uff1a~$1000\u4ebf(2022)->~$2500\u4ebf(2025)")

    pdf.sec("\u8d8b\u52bf\u4e8c\uff1a\u5730\u7f18\u653f\u6cbb\u91cd\u5851\u4f9b\u5e94\u94fe")
    pdf.tbl(
        ["\u653f\u7b56", "\u56fd\u5bb6", "\u91d1\u989d", "\u5f71\u54cd"],
        [
            ["CHIPS Act", "\u7f8e\u56fd", "$527\u4ebf", "TSMC/Samsung/Intel\u5728\u7f8e\u5efa\u5382"],
            ["\u6b27\u6d32\u82af\u7247\u6cd5\u6848", "\u6b27\u76df", "$490\u4ebf", "\u76ee\u68072030\u5e74\u4efd\u989d20%"],
            ["\u5927\u57fa\u91d1\u4e09\u671f", "\u4e2d\u56fd", "$470\u4ebf", "\u6276\u6301\u56fd\u4ea7\u66ff\u4ee3"],
            ["\u51fa\u53e3\u7ba1\u5236", "\u7f8e\u56fd", "N/A", "\u9650\u5236\u5148\u8fdb\u82af\u7247/\u8bbe\u5907\u5bf9\u534e\u51fa\u53e3"],
        ],
        [38, 22, 32, 98],
    )
    pdf.box("\u5de5\u5382\u89c6\u89d2\uff1a", "\u5730\u7f18\u653f\u6cbb\u8ba9\u4e00\u5207\u53d8\u8d35\u4e86\u3002TSMC\u4e9a\u5229\u6851\u90a3\u5382\u7684\u5efa\u8bbe\u6210\u672c\u662f\u53f0\u6e7e\u76844-5\u500d\u3002\u4f46\u5ba2\u6237\u613f\u610f\u4e3a\u201c\u4f9b\u5e94\u94fe\u5b89\u5168\u201d\u4ed8\u6ea2\u4ef7\u3002")

    pdf.sec("\u8d8b\u52bf\u4e09\uff1aChiplet\u4e0e\u5f02\u6784\u96c6\u6210")
    pdf.li("\u4e0d\u540c\u529f\u80fd\u6a21\u5757\u7528\u4e0d\u540c\u5236\u7a0b\uff08\u8ba1\u7b973nm\uff0cI/O\u75287nm\uff09\uff0c\u964d\u4f4e\u6210\u672c\uff0c\u63d0\u9ad8\u826f\u7387")
    pdf.li("UCIe\u6807\u51c6\u6b63\u5728\u63a8\u8fdb\u8de8\u516c\u53f8Chiplet\u4e92\u64cd\u4f5c\u6027")
    pdf.li("\u4ee3\u8868\uff1aAMD EPYC\uff0cApple M3 Ultra\uff08\u4e24\u4e2aM3 Max\u62fc\u63a5\uff09")

    pdf.sec("\u8d8b\u52bf\u56db\uff1a\u6210\u719f\u5236\u7a0b\u7684\u201c\u9690\u5f62\u4ef7\u503c\u201d")
    pdf.li("\u5168\u7403~60%\u7684\u82af\u7247\u4ecd\u7136\u4f7f\u752828nm\u53ca\u4ee5\u4e0a\u7684\u6210\u719f\u5236\u7a0b")
    pdf.li("\u6298\u65e7\u5b8c\u6bd5\u7684\u6210\u719f\u5236\u7a0b\u5de5\u5382\u5229\u6da6\u7387\u53ef\u8fbe50%+")
    pdf.li("\u98ce\u9669\uff1a\u4e2d\u56fd\u5927\u9646\u6b63\u5728\u5927\u91cf\u6269\u5efa\u6210\u719f\u5236\u7a0b\u4ea7\u80fd")

    pdf.sec("\u8d8b\u52bf\u4e94\uff1a\u7b2c\u4e09\u4ee3\u534a\u5bfc\u4f53\uff08\u5bbd\u7981\u5e26\uff09")
    pdf.tbl(
        ["\u6750\u6599", "\u7279\u70b9", "\u5e94\u7528", "\u4e3b\u8981\u516c\u53f8"],
        [
            ["SiC(\u78b3\u5316\u7845)", "\u9ad8\u538b\u3001\u9ad8\u6e29\u3001\u4f4e\u635f\u8017", "\u7535\u52a8\u8f66\u9006\u53d8\u5668", "Wolfspeed,ST,Infineon"],
            ["GaN(\u6c2e\u5316\u9553)", "\u9ad8\u9891\u3001\u9ad8\u6548\u7387", "\u5feb\u5145,5G\u57fa\u7ad9", "EPC, Navitas"],
        ],
        [32, 45, 50, 63],
    )
    pdf.p("SiC\u5e02\u573a\uff1a~$20\u4ebf(2022) -> ~$100\u4ebf(2027)\uff0cCAGR~35%\u3002")

    pdf.sec("\u8d8b\u52bf\u516d\uff1a\u5149\u5b50\u82af\u7247\u4e0e\u91cf\u5b50\u8ba1\u7b97")
    pdf.li("\u7845\u5149\u5b50\uff1a\u7528\u5149\u4ee3\u66ff\u7535\u4f20\u8f93\u6570\u636e\uff0c\u89e3\u51b3\u6570\u636e\u4e2d\u5fc3\u5e26\u5bbd\u74f6\u9888")
    pdf.li("\u91cf\u5b50\u8ba1\u7b97\uff1aIBM, Google, IonQ\u63a8\u8fdb\u4e2d\uff0c\u4f46\u8ddd\u79bb\u5546\u4e1a\u5316\u4ecd\u67095-10\u5e74")

    # ===== CH10 =====
    pdf.add_page()
    pdf.ch_title("\u7b2c\u5341\u7ae0\uff1a\u6838\u5fc3\u98ce\u9669\u4e0e\u6311\u6218")
    pdf.sec("\u98ce\u9669\u4e00\uff1a\u5730\u7f18\u653f\u6cbb\u5347\u7ea7")
    pdf.tbl(
        ["\u60c5\u666f", "\u6982\u7387", "\u5f71\u54cd"],
        [
            ["\u5bf9\u534e\u51fa\u53e3\u7ba1\u5236\u8fdb\u4e00\u6b65\u6536\u7d27", "\u9ad8", "ASML/Lam/AMAT\u4e2d\u56fd\u6536\u5165\u4e0b\u964d15-25%"],
            ["\u53f0\u6d77\u7d27\u5f20\u5c40\u52bf\u5347\u7ea7", "\u4e2d", "TSMC\u4f9b\u5e94\u94fe\u4e2d\u65ad\u6050\u614c\uff0c\u5168\u7403\u82af\u7247\u77ed\u7f3a"],
            ["\u7f8e\u56fd\u8981\u6c42\u76df\u53cb\u8ddf\u8fdb\u7981\u4ee4", "\u9ad8", "\u65e5\u672c\u3001\u8377\u5170\u8bbe\u5907\u5382\u5546\u53d7\u5f71\u54cd"],
            ["\u4e2d\u56fd\u82af\u7247\u5168\u9762\u81ea\u4e3b\u66ff\u4ee3", "\u4f4e(\u77ed\u671f)", "\u6539\u53d8\u5168\u7403\u7ade\u4e89\u683c\u5c40"],
        ],
        [55, 30, 105],
    )
    pdf.bp("\u53f0\u6d77\u98ce\u9669\uff1a")
    pdf.li("TSMC\u751f\u4ea7\u4e86\u5168\u7403~60%\u7684\u82af\u7247\u548c~90%\u7684\u5148\u8fdb\u82af\u7247")
    pdf.li("\u4efb\u4f55\u4f9b\u5e94\u4e2d\u65ad\uff1a\u624b\u673a\u4ea7\u91cf-60%+\uff0cAI\u82af\u7247\u4f9b\u5e94\u5f52\u96f6\uff0c\u7ecf\u6d4e\u635f\u5931\u6570\u4e07\u4ebf\u7f8e\u5143")

    pdf.sec("\u98ce\u9669\u4e8c\uff1aAI\u9700\u6c42\u53ef\u6301\u7eed\u6027")
    pdf.li("AI\u8d44\u672c\u652f\u51fa\u662f\u5426\u53ef\u6301\u7eed\uff1f\u5982\u679cROI\u4e0d\u53ca\u9884\u671f\uff0c\u79d1\u6280\u5de8\u5934\u53ef\u80fd\u524a\u51cf\u652f\u51fa")
    pdf.li("NVIDIA GPU\u9ad8\u5b9a\u4ef7\uff08H100~$3\u4e07, B100~$6\u4e07\uff09\u662f\u5426\u4f1a\u56e0\u7ade\u4e89\u52a0\u5267\u800c\u4e0b\u964d\uff1f")
    pdf.li("\u66ff\u4ee3\u65b9\u6848\uff08Google TPU, AWS Trainium, AMD MI300\uff09\u80fd\u5426\u5206\u8d70\u4efd\u989d\uff1f")

    pdf.sec("\u98ce\u9669\u4e09\uff1a\u4e2d\u56fd\u6210\u719f\u5236\u7a0b\u4ea7\u80fd\u8fc7\u5269")
    pdf.li("2024-2026\u5e74\u65b0\u589e~30\u5ea7\u665f\u5706\u5382\uff0c\u96c6\u4e2d\u572828nm-55nm")
    pdf.li("\u53ef\u80fd\u5bfc\u81f4\u5168\u7403\u6210\u719f\u5236\u7a0b\u4ef7\u683c\u6218")
    pdf.li("\u53d7\u5f71\u54cd\u6700\u5927\uff1aUMC, GlobalFoundries, TSMC\u6210\u719f\u4ea7\u7ebf")

    pdf.sec("\u98ce\u9669\u56db\uff1a\u6280\u672f\u74f6\u9888")
    pdf.tbl(
        ["\u6311\u6218", "\u73b0\u72b6", "\u5e94\u5bf9"],
        [
            ["\u6469\u5c14\u5b9a\u5f8b\u653e\u7f13", "\u6bcf\u4ee3\u6027\u80fd\u63d0\u5347\u4ece40%\u964d\u81f315-20%", "Chiplet, 3D\u5c01\u88c5"],
            ["EUV\u6210\u672c\u98d9\u5347", "High-NA EUV $3.5\u4ebf/\u53f0", "\u53ea\u6709\u5c11\u6570\u516c\u53f8\u8d1f\u62c5\u5f97\u8d77"],
            ["\u529f\u8017\u5899", "AI\u82af\u7247\u529f\u8017500-1000W", "\u6db2\u51b7, \u65b0\u67b6\u6784"],
            ["\u91cf\u4ea7\u826f\u7387", "2nm GAA\u826f\u7387\u6311\u6218", "\u9700\u8981\u65f6\u95f4\u548c\u7ecf\u9a8c\u79ef\u7d2f"],
        ],
        [48, 65, 77],
    )

    pdf.sec("\u98ce\u9669\u4e94\uff1a\u5468\u671f\u6027")
    pdf.p("\u534a\u5bfc\u4f53\u662f\u5f3a\u5468\u671f\u884c\u4e1a\u3002\u5386\u53f2\u4e0a\u6bcf3-4\u5e74\u4e00\u4e2a\u5b8c\u6574\u5468\u671f\uff1a2018-19\u8d38\u6613\u6218+\u5185\u5b58\u4e0b\u884c -> 2020 COVID\u51b2\u51fb\u540e\u9700\u6c42\u66b4\u6da8 -> 2021\u5168\u7403\u82af\u7247\u77ed\u7f3a -> 2022-23\u5e93\u5b58\u8fc7\u5269 -> 2024-25 AI\u9a71\u52a8\u590d\u82cf -> 2026-? \u5982\u679cAI\u652f\u51fa\u653e\u7f13...?")

    # ===== CH11 =====
    pdf.add_page()
    pdf.ch_title("\u7b2c\u5341\u4e00\u7ae0\uff1a\u672a\u6765\u673a\u4f1a\u4e0e\u6295\u8d44\u903b\u8f91")
    pdf.sec("11.1 \u6295\u8d44\u6846\u67b6\uff1a\u6309\u786e\u5b9a\u6027\u548c\u65f6\u95f4\u7ef4\u5ea6")
    pdf.sub("\u9ad8\u786e\u5b9a\u6027 / \u77ed\u671f\uff081-2\u5e74\uff09")
    pdf.tbl(
        ["\u673a\u4f1a", "\u6838\u5fc3\u6807\u7684", "\u903b\u8f91"],
        [
            ["AI\u7b97\u529b\u9700\u6c42\u6301\u7eed", "NVDA, AVGO, MRVL", "AI\u8bad\u7ec3/\u63a8\u7406\u4ecd\u5728\u7206\u53d1"],
            ["HBM\u4f9b\u4e0d\u5e94\u6c42", "SK Hynix", "HBM\u6bdb\u5229\u738770%+"],
            ["CoWoS\u4ea7\u80fd\u74f6\u9888", "TSM(TSMC)", "\u5148\u8fdb\u5c01\u88c5\u662f\u7a00\u7f3a\u8d44\u6e90"],
            ["EUV\u8bbe\u5907\u9700\u6c42", "ASML", "High-NA EUV\uff0cbacklog>$300\u4ebf"],
        ],
        [48, 48, 94],
    )
    pdf.sub("\u9ad8\u786e\u5b9a\u6027 / \u4e2d\u671f\uff082-5\u5e74\uff09")
    pdf.tbl(
        ["\u673a\u4f1a", "\u6807\u7684", "\u903b\u8f91"],
        [
            ["AI\u63a8\u7406\u5e02\u573a\u7206\u53d1", "NVDA,AVGO,MRVL", "\u63a8\u7406\u53ef\u80fd\u6bd4\u8bad\u7ec3\u66f4\u5927"],
            ["\u6c7d\u8f66\u534a\u5bfc\u4f53\u589e\u957f", "ON,MBLY,ADI,NXPI", "\u7535\u52a8\u5316+ADAS\u6e17\u900f"],
            ["SiC\u5bbd\u7981\u5e26", "WOLF,ON,STM", "\u7535\u52a8\u8f66\u529f\u7387\u9700\u6c42"],
            ["\u6210\u719f\u5236\u7a0b\u6574\u5408", "GFS, UMC", "\u4ef7\u683c\u6218\u540e\u5f3a\u8005\u6052\u5f3a"],
        ],
        [48, 48, 94],
    )
    pdf.sub("\u4e2d\u7b49\u786e\u5b9a\u6027 / \u957f\u671f\uff085-10\u5e74\uff09")
    pdf.tbl(
        ["\u673a\u4f1a", "\u6807\u7684", "\u903b\u8f91"],
        [
            ["Edge AI/\u7aef\u4fa7\u63a8\u7406", "QCOM, ARM", "AI\u4ece\u4e91\u7aef\u8d70\u5411\u7ec8\u7aef"],
            ["\u7845\u5149\u5b50", "AVGO,MRVL,LITE", "\u6570\u636e\u4e2d\u5fc3\u5149\u4e92\u8054"],
            ["Chiplet\u751f\u6001", "AMD,SNPS,CDNS", "UCIe\u6807\u51c6\u63a8\u52a8"],
            ["\u91cf\u5b50\u8ba1\u7b97", "IONQ, IBM", "\u8d85\u957f\u671f\u770b\u70b9\uff0c\u9ad8\u98ce\u9669"],
        ],
        [48, 48, 94],
    )

    pdf.add_page()
    pdf.sec("11.2 \u4e03\u6761\u6838\u5fc3\u6295\u8d44\u8bba\u70b9")
    pdf.bp("\u8bba\u70b9\u4e00\uff1a\u201c\u5356\u6c34\u4eba\u201d\u4f18\u4e8e\u201c\u6dd8\u91d1\u8005\u201d")
    pdf.p("\u82af\u7247\u8bbe\u8ba1\u516c\u53f8\u6709\u8d62\u6709\u8f93\uff0c\u4f46\u8bbe\u5907\u548cEDA\u516c\u53f8\u662f\u201c\u5356\u94f2\u5b50\u7ed9\u6240\u6709\u4eba\u201d\u3002ASML, LRCX, AMAT, KLAC, SNPS, CDNS\u65e0\u8bba\u8c01\u8d62\u90fd\u53d7\u76ca\u3002\u4f46\u4f30\u503c\u5df2\u4e0d\u4fbf\u5b9c\u3002")
    pdf.bp("\u8bba\u70b9\u4e8c\uff1aTSMC\u662f\u534a\u5bfc\u4f53\u754c\u7684\u201c\u57fa\u7840\u8bbe\u65bd\u201d")
    pdf.p("\u7c7b\u4f3c\u4e92\u8054\u7f51\u65f6\u4ee3\u7684AWS\u2014\u2014\u6240\u6709\u4eba\u90fd\u5728\u4e0a\u9762\u8fd0\u884c\u3002\u5148\u8fdb\u5236\u7a0b+\u5148\u8fdb\u5c01\u88c5\u53cc\u91cd\u5784\u65ad\u3002\u98ce\u9669\uff1a\u53f0\u6d77\u5730\u7f18\u653f\u6cbb\u3002")
    pdf.bp("\u8bba\u70b9\u4e09\uff1aAI\u94fe\u6761\u6295\u8d44\u4f18\u5148\u7ea7")
    pdf.p("GPU/\u52a0\u901f\u5668(NVDA) > HBM(SKH) > \u4ee3\u5de5(TSM) > \u5c01\u88c5(CoWoS) > \u8bbe\u5907(ASML) > \u6750\u6599\u3002\u8d8a\u9760\u8fd1\u9700\u6c42\u7aef\uff0c\u5f39\u6027\u8d8a\u5927\uff1b\u8d8a\u9760\u8fd1\u4e0a\u6e38\uff0c\u7a33\u5b9a\u6027\u8d8a\u9ad8\u3002")
    pdf.bp("\u8bba\u70b9\u56db\uff1a\u5185\u5b58\u662f\u9ad8\u5f39\u6027\u5468\u671f\u80a1")
    pdf.p("SK Hynix, Samsung, Micron\u5728\u5468\u671f\u5e95\u90e8\u4e70\u5165\uff0c\u9876\u90e8\u5356\u51fa\u3002HBM\u7ed9\u4e86SK Hynix\u7ed3\u6784\u6027\u6ea2\u4ef7\u3002Micron(MU)\u4f5c\u4e3a\u7f8e\u56fd\u552f\u4e00\u5185\u5b58\u516c\u53f8\uff0c\u6709\u653f\u7b56\u652f\u6301\u6ea2\u4ef7\u3002")
    pdf.bp("\u8bba\u70b9\u4e94\uff1a\u6c7d\u8f66\u534a\u5bfc\u4f53\u662f\u6162\u725b")
    pdf.p("\u589e\u901f\u4e0d\u5982AI\uff0c\u4f46\u786e\u5b9a\u6027\u9ad8\u3002Infineon, NXP, ON Semi, STMicro\u662f\u6838\u5fc3\u6807\u7684\u3002SiC\u662f\u589e\u901f\u6700\u5feb\u7684\u5b50\u8d5b\u9053\u3002")
    pdf.bp("\u8bba\u70b9\u516d\uff1aEDA/IP\u662f\u201c\u6c34\u7535\u7164\u201d\uff0c\u9002\u5408\u957f\u671f\u6301\u6709")
    pdf.p("Synopsys, Cadence, ARM\u7684\u5546\u4e1a\u6a21\u5f0f\u6700\u63a5\u8fd1SaaS\u3002\u9ad8\u8ba2\u9605\u6536\u5165\uff0c\u9ad8\u7c98\u6027\uff0c\u9ad8\u5229\u6da6\u7387\u3002\u4f30\u503c\u8d35\u4f46\u914d\u5f97\u4e0a\uff08P/E~50-60x\uff09\u3002")
    pdf.bp("\u8bba\u70b9\u4e03\uff1a\u4e0d\u8981\u5ffd\u89c6\u6210\u719f\u5236\u7a0b\u7684\u73b0\u91d1\u6d41")
    pdf.p("UMC, GlobalFoundries\u6298\u65e7\u5b8c\u6bd5\u540e\u5229\u6da6\u7387\u5f88\u9ad8\u3002\u6c7d\u8f66\u3001\u5de5\u4e1a\u7b49\u957f\u5c3e\u9700\u6c42\u4fdd\u5e95\u3002\u98ce\u9669\u662f\u4e2d\u56fd\u4ea7\u80fd\u51b2\u51fb\u3002")

    pdf.chk(60)
    pdf.sec("11.3 \u6211\u4e2a\u4eba\u6700\u770b\u597d\u76845\u4e2a\u673a\u4f1a")
    pdf.bp("1. TSMC (TSM)")
    pdf.p("\u6700\u7a33\u7684\u534a\u5bfc\u4f53\u6295\u8d44\u3002\u5148\u8fdb\u5236\u7a0b\u5784\u65ad+\u5148\u8fdb\u5c01\u88c5\u7a00\u7f3a\u6027+AI\u8d85\u7ea7\u5468\u671f\u7684\u6700\u5927\u53d7\u76ca\u8005\u3002\u552f\u4e00\u98ce\u9669\u662f\u53f0\u6d77\u3002")
    pdf.bp("2. ASML")
    pdf.p("\u6ca1\u6709\u66ff\u4ee3\u54c1\u7684\u8bbe\u5907\u516c\u53f8\u3002High-NA EUV\u662f\u552f\u4e00\u91cf\u4ea7\u65b9\u6848\uff0c\u8ba2\u5355\u6392\u52302027+\u3002\u5468\u671f\u6027\u6bd4\u5176\u4ed6\u8bbe\u5907\u5546\u5f31\u3002")
    pdf.bp("3. NVIDIA (NVDA) \u6216 Broadcom (AVGO)")
    pdf.p("AI\u82af\u7247\u7684\u4e24\u5927\u8def\u7ebf\u2014\u2014\u901a\u7528GPU vs \u5b9a\u5236ASIC\u3002NVDA\u751f\u6001\u58c1\u5792\u6df1\u4f46\u4f30\u503c\u8d35\uff0cAVGO\u901a\u8fc7\u4e3aGoogle/Meta\u505a\u5b9a\u5236AI ASIC\u5207\u5165\u3002")
    pdf.bp("4. SK Hynix (000660.KS)")
    pdf.p("HBM\u7684\u7edd\u5bf9\u9f99\u5934\u3002AI\u82af\u7247\u9700\u8981\u591a\u5c11GPU\u5c31\u9700\u8981\u591a\u5c11HBM\u3002HBM\u5229\u6da6\u7387\u8fdc\u9ad8\u4e8e\u666e\u901a\u5185\u5b58\u3002\u97e9\u56fd\u80a1\u5e02\u4f30\u503c\u4f4e\u662f\u989d\u5916\u5b89\u5168\u8fb9\u9645\u3002")
    pdf.bp("5. ARM Holdings (ARM)")
    pdf.p("AI\u7ec8\u7aef\u5316\u7684\u957f\u671f\u53d7\u76ca\u8005\u3002\u65e0\u8bbfAI PC\u3001AI\u624b\u673a\u8fd8\u662fAI\u6c7d\u8f66\uff0cARM\u67b6\u6784\u65e0\u5904\u4e0d\u5728\u3002\u7eafIP\u516c\u53f8\u65e0\u5236\u9020\u98ce\u9669\uff0c\u4f46\u5f53\u524d\u4f30\u503c\u975e\u5e38\u8d35\u3002")

    # ===== APPENDIX =====
    pdf.add_page()
    pdf.ch_title("\u9644\u5f55\uff1a\u5173\u952e\u516c\u53f8\u901f\u67e5\u8868")
    pdf.sec("\u8bbe\u8ba1\uff08Fabless / \u7cfb\u7edf\u516c\u53f8\u81ea\u7814\uff09")
    pdf.tbl(
        ["\u516c\u53f8", "Ticker", "\u6838\u5fc3\u4ea7\u54c1", "2025\u6536\u5165", "\u5236\u7a0b"],
        [
            ["NVIDIA", "NVDA", "GPU,AI\u52a0\u901f\u5668", "~$1300\u4ebf", "5/4nm TSMC"],
            ["Broadcom", "AVGO", "\u7f51\u7edc,ASIC,VMware", "~$510\u4ebf", "5/3nm TSMC"],
            ["AMD", "AMD", "CPU,GPU,FPGA", "~$260\u4ebf", "5/4/3nm TSMC"],
            ["Qualcomm", "QCOM", "\u79fb\u52a8SoC,RF", "~$420\u4ebf", "4nm TSMC"],
            ["MediaTek", "2454.TW", "\u79fb\u52a8/IoT SoC", "~$180\u4ebf", "4/3nm TSMC"],
            ["Marvell", "MRVL", "\u6570\u636e\u4e2d\u5fc3,ASIC", "~$60\u4ebf", "5/3nm TSMC"],
        ],
        [28, 26, 44, 30, 36, 26],
    )
    pdf.sec("\u5236\u9020\uff08Foundry / IDM\uff09")
    pdf.tbl(
        ["\u516c\u53f8", "Ticker", "\u6a21\u5f0f", "\u6700\u5148\u8fdb\u5236\u7a0b", "2025\u6536\u5165"],
        [
            ["TSMC", "TSM", "\u7eaf\u4ee3\u5de5", "3nm/2nm", "~$900\u4ebf"],
            ["Samsung", "005930.KS", "IDM+\u4ee3\u5de5", "3nm GAA", "~$2400\u4ebf(\u96c6\u56e2)"],
            ["Intel", "INTC", "IDM+\u4ee3\u5de5", "Intel 18A", "~$540\u4ebf"],
            ["GlobalFoundries", "GFS", "\u7eaf\u4ee3\u5de5", "12nm", "~$75\u4ebf"],
            ["SMIC", "0981.HK", "\u7eaf\u4ee3\u5de5", "7nm(DUV)", "~$80\u4ebf"],
            ["UMC", "UMC", "\u7eaf\u4ee3\u5de5", "14nm", "~$70\u4ebf"],
        ],
        [38, 30, 30, 32, 38, 22],
    )
    pdf.sec("\u8bbe\u5907")
    pdf.tbl(
        ["\u516c\u53f8", "Ticker", "\u6838\u5fc3\u8bbe\u5907", "2025\u6536\u5165", "\u5e02\u5360\u7387"],
        [
            ["ASML", "ASML", "EUV/DUV\u5149\u523b\u673a", "~$300\u4ebf", "\u5149\u523b~90%"],
            ["Applied Materials", "AMAT", "\u6c89\u79ef,\u523b\u8680,CMP", "~$280\u4ebf", "\u7efc\u5408#1"],
            ["Lam Research", "LRCX", "\u523b\u8680,\u6c89\u79ef", "~$180\u4ebf", "\u523b\u8680~45%"],
            ["Tokyo Electron", "8035.T", "\u6d82\u80f6\u663e\u5f71,\u6c89\u79ef", "~$180\u4ebf", "\u6d82\u80f6~90%"],
            ["KLA", "KLAC", "\u68c0\u6d4b,\u91cf\u6d4b", "~$110\u4ebf", "\u68c0\u6d4b~55%"],
        ],
        [38, 24, 42, 30, 36, 20],
    )

    pdf.chk(50)
    pdf.sec("\u5185\u5b58")
    pdf.tbl(
        ["\u516c\u53f8", "Ticker", "\u6838\u5fc3\u4ea7\u54c1", "2025\u6536\u5165", "HBM\u5730\u4f4d"],
        [
            ["SK Hynix", "000660.KS", "DRAM,HBM,NAND", "~$550\u4ebf", "#1"],
            ["Samsung", "005930.KS", "DRAM,HBM,NAND", "~$700\u4ebf(\u534a\u5bfc\u4f53)", "#2"],
            ["Micron", "MU", "DRAM,HBM,NAND", "~$300\u4ebf", "#3"],
        ],
        [30, 30, 44, 48, 38],
    )
    pdf.sec("EDA / IP")
    pdf.tbl(
        ["\u516c\u53f8", "Ticker", "\u6838\u5fc3\u4ea7\u54c1", "2025\u6536\u5165", "\u6bdb\u5229\u7387"],
        [
            ["Synopsys", "SNPS", "EDA + IP", "~$65\u4ebf", "~80%"],
            ["Cadence", "CDNS", "EDA + IP", "~$45\u4ebf", "~88%"],
            ["ARM Holdings", "ARM", "CPU\u67b6\u6784IP", "~$38\u4ebf", "~95%"],
        ],
        [35, 25, 48, 40, 42],
    )
    pdf.sec("\u6a21\u62df / \u529f\u7387 / \u6c7d\u8f66")
    pdf.tbl(
        ["\u516c\u53f8", "Ticker", "\u6838\u5fc3\u4ea7\u54c1", "2025\u6536\u5165"],
        [
            ["Texas Instruments", "TXN", "\u6a21\u62dfIC", "~$160\u4ebf"],
            ["Analog Devices", "ADI", "\u9ad8\u6027\u80fd\u6a21\u62df", "~$100\u4ebf"],
            ["Infineon", "IFNNY", "\u529f\u7387\u534a\u5bfc\u4f53,\u6c7d\u8f66", "~$170\u4ebf"],
            ["NXP", "NXPI", "\u6c7d\u8f66MCU/\u5904\u7406\u5668", "~$130\u4ebf"],
            ["ON Semi", "ON", "SiC,\u529f\u7387,\u56fe\u50cf\u4f20\u611f\u5668", "~$75\u4ebf"],
            ["STMicro", "STM", "\u6c7d\u8f66, \u5de5\u4e1a", "~$140\u4ebf"],
        ],
        [42, 25, 65, 45, 13],
    )

    # FINAL
    pdf.ln(10)
    pdf.set_font("CJK", "I", 8)
    pdf.set_text_color(150, 150, 150)
    pdf.multi_cell(0, 4, "\u4f5c\u8005\u6ce8\uff1a\u4f5c\u4e3a\u8fd0\u8425\u4e24\u5ea7\u665f\u5706\u5382\u7684\u4ece\u4e1a\u8005\uff0c\u6211\u6bcf\u5929\u7684\u5de5\u4f5c\u5c31\u662f\u76ef\u7740\u826f\u7387\u3001\u4ea7\u80fd\u5229\u7528\u7387\u3001\u5ba2\u6237\u8ba2\u5355\u548c\u8bbe\u5907\u4ea4\u671f\u3002\u8fd9\u4efd\u62a5\u544a\u529b\u6c42\u4ece\u4ea7\u4e1a\u5185\u90e8\u89c6\u89d2\u7ed9\u6295\u8d44\u8005\u4e00\u4e2a\u771f\u5b9e\u7684\u56fe\u666f\u3002\u82af\u7247\u8fd9\u4e2a\u884c\u4e1a\uff0c\u6c34\u5f88\u6df1\uff0c\u4f46\u770b\u61c2\u4e86\uff0c\u673a\u4f1a\u4e5f\u5f88\u5927\u3002", align="C")

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    pdf.output(OUTPUT_PATH)
    print(f"PDF saved to: {OUTPUT_PATH}")
    print(f"Pages: {pdf.page_no()}")


if __name__ == "__main__":
    build_pdf()
