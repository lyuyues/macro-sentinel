#!/usr/bin/env python3
"""Generate EB3 I-485 Interview Preparation Guide PDF with Chinese support."""

from fpdf import FPDF

# Fonts
FONT_HEITI = "/System/Library/Fonts/STHeiti Medium.ttc"
FONT_SONGTI = "/System/Library/Fonts/Supplemental/Songti.ttc"
OUTPUT_PATH = "output/EB3_I485_Interview_Guide.pdf"


class GuidePDF(FPDF):
    def __init__(self):
        super().__init__()
        # Register Chinese fonts
        self.add_font("Heiti", "", FONT_HEITI)
        self.add_font("Songti", "", FONT_SONGTI)
        self.set_auto_page_break(auto=True, margin=20)

    def header(self):
        if self.page_no() > 1:
            self.set_font("Heiti", size=8)
            self.set_text_color(128, 128, 128)
            self.cell(0, 8, "EB3 I-485 面试准备完整指南", align="C", new_x="LMARGIN", new_y="NEXT")
            self.set_draw_color(200, 200, 200)
            self.line(10, self.get_y(), 200, self.get_y())
            self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("Songti", size=8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f"第 {self.page_no()}/{{nb}} 页", align="C")

    def title_page(self):
        self.add_page()
        self.ln(60)
        self.set_font("Heiti", size=28)
        self.set_text_color(20, 60, 120)
        self.cell(0, 16, "EB3 I-485", align="C", new_x="LMARGIN", new_y="NEXT")
        self.cell(0, 16, "面试准备完整指南", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(10)
        self.set_draw_color(20, 60, 120)
        self.set_line_width(0.8)
        self.line(60, self.get_y(), 150, self.get_y())
        self.ln(10)
        self.set_font("Songti", size=14)
        self.set_text_color(80, 80, 80)
        self.cell(0, 10, "Adjustment of Status Interview Preparation", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(5)
        self.cell(0, 10, "Seattle Field Office", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(30)
        self.set_font("Songti", size=10)
        self.set_text_color(180, 0, 0)
        self.multi_cell(0, 6, "免责声明：本文件仅供参考，不构成法律建议。\n请务必咨询持牌移民律师确认您的具体情况。", align="C")

    def section_title(self, text):
        self.ln(6)
        self.set_font("Heiti", size=16)
        self.set_text_color(20, 60, 120)
        self.cell(0, 10, text, new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(20, 60, 120)
        self.set_line_width(0.5)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)

    def sub_title(self, text):
        self.ln(3)
        self.set_font("Heiti", size=12)
        self.set_text_color(40, 80, 140)
        self.cell(0, 8, text, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def body_text(self, text):
        self.set_font("Songti", size=10)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, 6, text)
        self.ln(1)

    def bullet(self, text, indent=10):
        x = self.get_x()
        self.set_font("Songti", size=10)
        self.set_text_color(30, 30, 30)
        self.set_x(x + indent)
        self.cell(5, 6, "-")
        self.multi_cell(0, 6, text)
        self.ln(0.5)

    def numbered_item(self, num, text, indent=10):
        x = self.get_x()
        self.set_font("Songti", size=10)
        self.set_text_color(30, 30, 30)
        self.set_x(x + indent)
        self.cell(8, 6, f"{num}.")
        self.multi_cell(0, 6, text)
        self.ln(0.5)

    def table_row(self, cells, widths, header=False):
        if header:
            self.set_font("Heiti", size=9)
            self.set_fill_color(20, 60, 120)
            self.set_text_color(255, 255, 255)
        else:
            self.set_font("Songti", size=9)
            self.set_text_color(30, 30, 30)
            self.set_fill_color(245, 245, 250)

        row_h = 7
        fill = header
        x_start = self.get_x()
        # Calculate the max lines needed
        max_lines = 1
        for i, cell in enumerate(cells):
            lines = self.multi_cell(widths[i], row_h, cell, dry_run=True, output="LINES")
            max_lines = max(max_lines, len(lines))

        actual_h = row_h * max_lines

        # Check if we need a page break
        if self.get_y() + actual_h > self.h - self.b_margin:
            self.add_page()

        y_start = self.get_y()
        x = x_start
        for i, cell in enumerate(cells):
            self.set_xy(x, y_start)
            self.set_draw_color(200, 200, 200)
            self.rect(x, y_start, widths[i], actual_h, style="D" if not fill else "DF")
            self.set_xy(x + 1, y_start + 1)
            self.multi_cell(widths[i] - 2, row_h, cell)
            x += widths[i]

        self.set_xy(x_start, y_start + actual_h)

    def check_item(self, text, checked=False):
        """Render a checkbox item."""
        self.set_font("Songti", size=10)
        self.set_text_color(30, 30, 30)
        mark = "[x]" if checked else "[ ]"
        self.set_x(self.get_x() + 10)
        self.cell(7, 6, mark)
        self.multi_cell(0, 6, text)
        self.ln(0.5)

    def highlight_box(self, text, color=(255, 240, 240)):
        self.ln(2)
        self.set_fill_color(*color)
        self.set_font("Heiti", size=10)
        self.set_text_color(180, 0, 0)
        y = self.get_y()
        self.rect(10, y, 190, 12, style="DF")
        self.set_xy(14, y + 2)
        self.multi_cell(182, 6, text)
        self.ln(4)


def build_pdf():
    pdf = GuidePDF()
    pdf.alias_nb_pages()

    # ===== Cover Page =====
    pdf.title_page()

    # ===== Section 1: Interview Notice =====
    pdf.add_page()
    pdf.section_title("一、面试通知确认")
    pdf.body_text("收到 Interview Reschedule Notice 后，请立即确认以下事项：")
    pdf.bullet("面试日期、时间、地点")
    pdf.body_text("  Seattle Field Office: 12500 Tukwila International Blvd, Seattle, WA 98168")
    pdf.bullet("主申请人和配偶是否都需要到场（通常都需要）")
    pdf.bullet("通知上是否有特别要求携带的文件")

    # ===== Section 2: Document Checklist =====
    pdf.section_title("二、必备文件清单（主申请人 + 配偶）")

    # -- A: Identity --
    pdf.sub_title("A. 身份与移民状态文件")
    w = [80, 30, 30, 50]
    pdf.table_row(["文件", "主申请人", "配偶", "备注"], w, header=True)
    rows_a = [
        ["护照（有效期6个月以上）", "Y", "Y", "包括所有过期护照"],
        ["I-485 Receipt Notice (I-797C)", "Y", "Y", ""],
        ["Interview Notice", "Y", "Y", ""],
        ["I-94 入境记录（打印件）", "Y", "Y", "从 CBP 网站下载"],
        ["所有美国签证页复印件", "Y", "Y", "包括过期签证"],
        ["EAD 卡 (I-766)（如有）", "Y", "Y", ""],
        ["Advance Parole (I-131)（如有）", "Y", "Y", ""],
        ["当前签证状态证明", "Y", "Y", "I-797 Approval Notice"],
    ]
    for r in rows_a:
        pdf.table_row(r, w)

    # -- B: EB3 Core --
    pdf.sub_title("B. EB3 职业移民核心文件")
    w2 = [90, 100]
    pdf.table_row(["文件", "说明"], w2, header=True)
    rows_b = [
        ["PERM Labor Certification (ETA 9089)", "已批准的原件或 certified copy"],
        ["I-140 Approval Notice (I-797)", "Immigrant Petition 批准通知"],
        ["I-140 Petition 副本", "包括支持文件"],
        ["雇主支持信 (Employment Offer Letter)", "最新日期，确认职位、薪资、工作地点仍然有效"],
        ["当前工资单 (Pay Stubs)", "最近 3-6 个月"],
        ["W-2 表格", "最近 2-3 年"],
        ["联邦税表 (Tax Returns)", "最近 3 年，包括所有 schedules"],
        ["学历认证 / 学位证书", "学位证、毕业证、成绩单（外国学历需 credential evaluation）"],
        ["简历 / Resume", "最新版本"],
    ]
    for r in rows_b:
        pdf.table_row(r, w2)

    # -- C: Marriage & Family --
    pdf.sub_title("C. 婚姻与家庭关系文件")
    pdf.table_row(["文件", "说明"], w2, header=True)
    rows_c = [
        ["结婚证（原件 + 翻译件）", "如非英文需 certified translation"],
        ["结婚照片", "10-15张，涵盖不同时期"],
        ["共同生活证明", "见下方 D 部分详细清单"],
        ["出生证明（双方）", "原件 + 翻译件"],
        ["子女出生证明（如有）", ""],
        ["离婚证/判决书（如有前婚）", "证明前婚已合法终止"],
    ]
    for r in rows_c:
        pdf.table_row(r, w2)

    # -- D: Bona Fide Marriage --
    pdf.sub_title("D. 婚姻真实性证明（Bona Fide Marriage Evidence）")
    pdf.highlight_box("[!]这是面试重点之一，请充分准备！", (255, 245, 230))
    evidence = [
        "联名银行账户对账单（Joint Bank Statements）",
        "联名信用卡账单",
        "联名租房合同 / 房产证（Joint Lease / Mortgage）",
        "联名车辆登记或保险",
        "联名水电煤气账单（Utility Bills）",
        "共同报税记录（Joint Tax Returns）— Married Filing Jointly",
        "人寿保险 / 医疗保险受益人文件",
        "共同旅行记录（机票、酒店预订）",
        "来往通信记录（如适用）",
        "社交媒体合照、家庭活动照片",
    ]
    for e in evidence:
        pdf.check_item(e)

    # -- E: Medical --
    pdf.sub_title("E. 体检与医疗文件")
    pdf.table_row(["文件", "说明"], w2, header=True)
    pdf.table_row(["I-693 体检报告（密封信封）", "由 USCIS 指定的 civil surgeon 完成"], w2)
    pdf.table_row(["疫苗记录", "确保符合 USCIS 要求的所有疫苗"], w2)
    pdf.highlight_box("[!]重要：I-693 有效期为签字后 2 年。如果之前提交的已过期，需要重新体检。", (255, 240, 240))

    # -- F: Criminal --
    pdf.sub_title("F. 无犯罪与品行文件")
    pdf.table_row(["文件", "说明"], w2, header=True)
    pdf.table_row(["警察局无犯罪记录证明", "如在其他国家居住超过6个月"], w2)
    pdf.table_row(["法院文件（如有）", "任何逮捕、定罪、交通违章（DUI等）"], w2)
    pdf.table_row(["移民违规相关文件（如有）", "如 overstay 等"], w2)

    # -- G: Financial --
    pdf.sub_title("G. 财务能力证明")
    pdf.table_row(["文件", "说明"], w2, header=True)
    pdf.table_row(["I-864 经济担保书 (Affidavit of Support)", "雇主或个人提交（EB3通常由雇主）"], w2)
    pdf.table_row(["雇主最新税表或财务证明", "证明有能力支付承诺的薪资"], w2)
    pdf.table_row(["个人银行对账单", "最近 3-6 个月"], w2)

    # ===== Section 3: Interview Questions =====
    pdf.add_page()
    pdf.section_title("三、I-485 面试常见问题准备")

    pdf.sub_title("关于移民申请本身")
    q1 = [
        "When did you file your I-485?",
        "Who is your petitioning employer?",
        "What is your job title and what do you do?",
        "How long have you worked there?",
        "Are you still working for the sponsoring employer?",
        "What is your current salary?",
    ]
    for i, q in enumerate(q1, 1):
        pdf.numbered_item(i, q)

    pdf.sub_title("关于身份状态")
    q2 = [
        "When did you first enter the US? On what visa?",
        "Have you ever overstayed your visa?",
        "Have you ever been out of status?",
        "Have you traveled outside the US since filing I-485?",
    ]
    for i, q in enumerate(q2, 7):
        pdf.numbered_item(i, q)

    pdf.sub_title("关于婚姻（配偶作为 Dependent）")
    q3 = [
        "When and where did you get married?",
        "How did you meet your spouse?",
        "Do you live together? What is your address?",
        "Do you have children?",
    ]
    for i, q in enumerate(q3, 11):
        pdf.numbered_item(i, q)

    pdf.sub_title("关于品行")
    q4 = [
        "Have you ever been arrested, cited, or detained?",
        "Have you ever been convicted of a crime?",
        "Have you ever claimed to be a US citizen?",
        "Are you a member of any organizations?",
        "Have you ever been deported or removed?",
    ]
    for i, q in enumerate(q4, 15):
        pdf.numbered_item(i, q)

    pdf.sub_title("关于 I-485 表格内容")
    pdf.highlight_box("[!]面试官可能逐项核实 I-485 上填写的信息，务必重新审阅你提交的 I-485 表格副本！", (255, 245, 230))

    # ===== Section 4: Day-Of Tips =====
    pdf.add_page()
    pdf.section_title("四、面试当天注意事项")

    pdf.sub_title("时间安排")
    pdf.bullet("提前 30 分钟到达")
    pdf.bullet("预计整个过程 1-2 小时（含等待）")

    pdf.sub_title("着装")
    pdf.bullet("Business casual 或正装，整洁得体")

    pdf.sub_title("行为举止")
    pdf.bullet("诚实回答，不知道的说不知道")
    pdf.bullet("不要猜测或编造答案")
    pdf.bullet("回答简洁明了，不要过度解释")
    pdf.bullet("配偶和主申请人的回答要一致")

    pdf.sub_title("携带物品")
    pdf.bullet("所有文件按分类整理，用文件夹/标签分开")
    pdf.bullet("原件 + 复印件各一套")
    pdf.bullet("笔和纸")

    # ===== Section 5: Special Reminders =====
    pdf.section_title("五、特别提醒")

    reminders = [
        "雇主支持信必须是最新的 — 建议面试前 1-2 周让雇主出具新的 offer letter，确认职位和薪资不变",
        "I-693 体检报告 — 检查有效期，过期需重做",
        "重新审阅 I-485 表格 — 确保你记得自己填写的所有内容",
        "如有任何变化（地址、工作、婚姻状态等）— 提前准备相关文件",
        "配偶英语能力 — 如果配偶英语有限，面试官通常会放慢速度，也可以考虑带翻译（需提前确认是否允许）",
        "Seattle Field Office — 确认是否允许携带手机进入大楼，建议把手机留在车上",
    ]
    for i, r in enumerate(reminders, 1):
        pdf.numbered_item(i, r)

    # ===== Section 6: File Organization =====
    pdf.section_title("六、文件整理建议（按标签分类）")

    tabs = [
        ("Tab 1", "Interview Notice + I-485 Receipt + I-797s"),
        ("Tab 2", "Passports + I-94 + Visa pages"),
        ("Tab 3", "PERM + I-140 Approval"),
        ("Tab 4", "Employment Letter + Pay Stubs + W-2s"),
        ("Tab 5", "Tax Returns (3 years)"),
        ("Tab 6", "Marriage Certificate + Photos + Joint Evidence"),
        ("Tab 7", "Birth Certificates"),
        ("Tab 8", "I-693 Medical (sealed envelope)"),
        ("Tab 9", "I-864 Affidavit of Support"),
        ("Tab 10", "Education Documents"),
        ("Tab 11", "I-485 Filed Copy (for your reference)"),
    ]
    w3 = [30, 160]
    pdf.table_row(["标签", "内容"], w3, header=True)
    for tab, content in tabs:
        pdf.table_row([tab, content], w3)

    # ===== Final Note =====
    pdf.ln(10)
    pdf.set_font("Songti", size=10)
    pdf.set_text_color(80, 80, 80)
    pdf.multi_cell(
        0, 6,
        "以上内容基于一般性的 EB3 I-485 面试准备。每个案件的具体情况不同，"
        "强烈建议在面试前与您的移民律师进行一次详细的 prep session，"
        "逐项确认所有文件和可能的问题。\n\n祝面试顺利！",
        align="C",
    )

    pdf.output(OUTPUT_PATH)
    print(f"PDF generated: {OUTPUT_PATH}")


if __name__ == "__main__":
    build_pdf()
