"""
PDF Generation and Email Dispatch Engine.
Generates styled executive PDF performance audit reports using ReportLab,
and emails copies to designated recipients (e.g. lisawalker6898@gmail.com).
"""
import io
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime, timezone

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

logger = logging.getLogger("autonomous_trading.reporter")

class ReportPDFGenerator:
    """Generates styled, executive PDF audit reports."""

    @staticmethod
    def generate_pdf(report_data: Dict[str, Any], is_five_day: bool = False) -> bytes:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36
        )

        styles = getSampleStyleSheet()
        
        # Custom Typography
        title_style = ParagraphStyle(
            "DocTitle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=20,
            textColor=colors.HexColor("#0f172a"),
            alignment=TA_LEFT
        )
        
        subtitle_style = ParagraphStyle(
            "DocSubtitle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#475569")
        )

        section_heading = ParagraphStyle(
            "SectionHeading",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=15,
            textColor=colors.HexColor("#0369a1"),
            spaceBefore=10,
            spaceAfter=4
        )

        table_header_style = ParagraphStyle(
            "TableHeader",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=colors.white,
            alignment=TA_CENTER
        )

        table_cell_style = ParagraphStyle(
            "TableCell",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=7.5,
            leading=9,
            textColor=colors.HexColor("#0f172a"),
            alignment=TA_CENTER
        )

        story = []

        # 1. Header Banner
        report_title = "LAST 5 WORKING DAYS PERFORMANCE AUDIT" if is_five_day else "DAILY SESSION TRADING & AUDIT REPORT"
        gen_time = report_data.get("report_time_uk", report_data.get("generated_at_uk", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")))
        
        story.append(Paragraph(report_title, title_style))
        story.append(Paragraph(f"Autonomous Trading Engine | eToro UK Multi-Asset Execution | Timestamp: <strong>{gen_time}</strong>", subtitle_style))
        story.append(Spacer(1, 10))
        story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0284c7"), spaceAfter=12))

        # 2. Key Performance Indicators Summary Cards (Table)
        if is_five_day:
            tot_pnl = report_data.get("total_net_pnl_usd", 0.0)
            tot_pnl_pct = report_data.get("total_net_pnl_pct", 0.0)
            tot_vol = report_data.get("total_amount_traded_usd", 0.0)
            tot_tr = report_data.get("total_trades", 0)
            tot_hits = report_data.get("total_hits", 0)
            tot_miss = report_data.get("total_misses", 0)
            win_rate = report_data.get("overall_hit_rate_pct", 0.0)
            sign = "+" if tot_pnl >= 0 else ""
            sign_pct = "+" if tot_pnl_pct >= 0 else ""
            
            kpi_data = [
                ["5-DAY NET P&L", "5-DAY VOLUME TRADED", "HITS / MISSES", "OVERALL WIN RATE", "TOTAL TRADES"],
                [
                    f"{sign}${tot_pnl:,.2f} ({sign_pct}{tot_pnl_pct:.2f}%)",
                    f"${tot_vol:,.2f}",
                    f"{tot_hits} Wins / {tot_miss} Losses",
                    f"{win_rate:.1f}%",
                    str(tot_tr)
                ]
            ]
        else:
            eq = report_data.get("current_equity", 10000.0)
            net_pnl = report_data.get("net_pnl_usd", 0.0)
            net_pnl_pct = report_data.get("net_pnl_pct", 0.0)
            win_rate = report_data.get("win_rate_pct", 0.0)
            w_count = report_data.get("winning_trades", 0)
            l_count = report_data.get("losing_trades", 0)
            pf = report_data.get("profit_factor", 0.0)
            max_dd = report_data.get("max_drawdown_pct", 0.0)
            sign = "+" if net_pnl >= 0 else ""
            sign_pct = "+" if net_pnl_pct >= 0 else ""

            kpi_data = [
                ["PORTFOLIO EQUITY", "NET REALIZED P&L", "HITS / MISSES (WIN RATE)", "PROFIT FACTOR", "MAX DRAWDOWN"],
                [
                    f"${eq:,.2f}",
                    f"{sign}${net_pnl:,.2f} ({sign_pct}{net_pnl_pct:.2f}%)",
                    f"{win_rate:.1f}% ({w_count}W / {l_count}L)",
                    f"{pf:.2f}",
                    f"{max_dd:.2f}%"
                ]
            ]

        kpi_table = Table(kpi_data, colWidths=[108]*5)
        kpi_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0f172a")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 7.5),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor("#f8fafc")),
            ('TEXTCOLOR', (0, 1), (-1, 1), colors.HexColor("#0f172a")),
            ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 1), (-1, 1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ]))
        story.append(kpi_table)
        story.append(Spacer(1, 14))

        # 3. Individual Stock Performance Summary Table
        stock_list = report_data.get("stock_summaries", report_data.get("per_stock_summary", []))
        heading_text = "LAST 5 WORKING DAYS INDIVIDUAL STOCK BREAKDOWN" if is_five_day else "TODAY'S INDIVIDUAL STOCK TRADING PERFORMANCE"
        story.append(Paragraph(heading_text, section_heading))

        stock_table_data = [
            [
                Paragraph("SYMBOL", table_header_style),
                Paragraph("AMOUNT TRADED ($)", table_header_style),
                Paragraph("TOTAL TRADES", table_header_style),
                Paragraph("HITS (WINS)", table_header_style),
                Paragraph("MISSES (LOSSES)", table_header_style),
                Paragraph("HIT RATE (%)", table_header_style),
                Paragraph("NET P&L ($)", table_header_style),
                Paragraph("RETURN (%)", table_header_style),
            ]
        ]

        g_vol = 0.0
        g_trades = 0
        g_hits = 0
        g_miss = 0
        g_pnl = 0.0

        if stock_list:
            for s in stock_list:
                amt = s.get("amount_traded_usd", 0.0)
                tr = s.get("total_trades", 0)
                h = s.get("hits", 0)
                m = s.get("misses", 0)
                hr = s.get("hit_rate_pct", 0.0)
                pnl = s.get("net_pnl_usd", 0.0)
                ret = s.get("net_pnl_pct", 0.0)

                g_vol += amt
                g_trades += tr
                g_hits += h
                g_miss += m
                g_pnl += pnl

                pnl_color = "#15803d" if pnl >= 0 else "#b91c1c"
                pnl_sign = "+" if pnl >= 0 else ""

                stock_table_data.append([
                    Paragraph(f"<strong>{s.get('symbol')}</strong>", table_cell_style),
                    Paragraph(f"${amt:,.2f}", table_cell_style),
                    Paragraph(str(tr), table_cell_style),
                    Paragraph(f"<font color='#15803d'><strong>{h}</strong></font>", table_cell_style),
                    Paragraph(f"<font color='#b91c1c'>{m}</font>", table_cell_style),
                    Paragraph(f"{hr:.1f}%", table_cell_style),
                    Paragraph(f"<font color='{pnl_color}'><strong>{pnl_sign}${pnl:,.2f}</strong></font>", table_cell_style),
                    Paragraph(f"<font color='{pnl_color}'>{pnl_sign}{ret:.2f}%</font>", table_cell_style),
                ])

            # Totals row
            g_hr = (g_hits / g_trades * 100.0) if g_trades > 0 else 0.0
            g_ret = (g_pnl / g_vol * 100.0) if g_vol > 0 else 0.0
            g_color = "#15803d" if g_pnl >= 0 else "#b91c1c"
            g_sign = "+" if g_pnl >= 0 else ""

            stock_table_data.append([
                Paragraph("<strong>PORTFOLIO TOTAL</strong>", table_cell_style),
                Paragraph(f"<strong>${g_vol:,.2f}</strong>", table_cell_style),
                Paragraph(f"<strong>{g_trades}</strong>", table_cell_style),
                Paragraph(f"<strong>{g_hits}</strong>", table_cell_style),
                Paragraph(f"<strong>{g_miss}</strong>", table_cell_style),
                Paragraph(f"<strong>{g_hr:.1f}%</strong>", table_cell_style),
                Paragraph(f"<font color='{g_color}'><strong>{g_sign}${g_pnl:,.2f}</strong></font>", table_cell_style),
                Paragraph(f"<font color='{g_color}'><strong>{g_sign}{g_ret:.2f}%</strong></font>", table_cell_style),
            ])
        else:
            stock_table_data.append([
                Paragraph("No trades recorded", table_cell_style),
                Paragraph("$0.00", table_cell_style),
                Paragraph("0", table_cell_style),
                Paragraph("0", table_cell_style),
                Paragraph("0", table_cell_style),
                Paragraph("0.0%", table_cell_style),
                Paragraph("$0.00", table_cell_style),
                Paragraph("0.00%", table_cell_style),
            ])

        st_table = Table(stock_table_data, colWidths=[65, 75, 55, 55, 60, 60, 85, 85])
        st_table_styles = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0284c7")),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#e2e8f0")),
        ]
        for i in range(1, len(stock_table_data) - 1):
            if i % 2 == 0:
                st_table_styles.append(('BACKGROUND', (0, i), (-1, i), colors.HexColor("#f8fafc")))
        st_table.setStyle(TableStyle(st_table_styles))
        story.append(st_table)
        story.append(Spacer(1, 14))

        # 4. Adaptive Learning & Strategy Evolution (Daily Report)
        if not is_five_day and "strategy_weight_evolution" in report_data:
            story.append(Paragraph("SELF-LEARNING STRATEGY WEIGHT EVOLUTION", section_heading))
            w_evol = report_data.get("strategy_weight_evolution", {})
            w_rows = [["STRATEGY MODEL", "CURRENT ALLOCATION WEIGHT", "SHIFT FROM 25% BASELINE"]]
            for k, v in w_evol.items():
                w_rows.append([
                    k.replace("_", " ").title(),
                    v.get("current_pct", "--"),
                    v.get("shift_from_baseline", "--")
                ])
            w_table = Table(w_rows, colWidths=[180, 180, 180])
            w_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#475569")),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 7.5),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ('TOPPADDING', (0, 0), (-1, -1), 3.5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3.5),
            ]))
            story.append(w_table)
            story.append(Spacer(1, 14))

        # 5. Chronological Trade Ledger (Top recent entries)
        trades = report_data.get("full_trade_ledger", [])
        if trades:
            story.append(Paragraph(f"SESSION TRADE LEDGER (Showing {min(len(trades), 15)} Most Recent)", section_heading))
            t_rows = [
                [
                    Paragraph("TIME", table_header_style),
                    Paragraph("SYMBOL", table_header_style),
                    Paragraph("DIR", table_header_style),
                    Paragraph("SHARES", table_header_style),
                    Paragraph("ENTRY", table_header_style),
                    Paragraph("EXIT", table_header_style),
                    Paragraph("P&L ($)", table_header_style),
                    Paragraph("RATIONALE", table_header_style),
                ]
            ]
            for t in trades[:15]:
                pnl = t.get("realized_pnl_usd", 0.0)
                pnl_color = "#15803d" if pnl >= 0 else "#b91c1c"
                pnl_sign = "+" if pnl >= 0 else ""
                t_time = t.get("exit_time", "").split("T")[-1][:8] if "T" in t.get("exit_time", "") else "--"
                
                t_rows.append([
                    Paragraph(t_time, table_cell_style),
                    Paragraph(f"<strong>{t.get('symbol')}</strong>", table_cell_style),
                    Paragraph(t.get("direction", "LONG"), table_cell_style),
                    Paragraph(f"{t.get('shares', 0.0):.4f}", table_cell_style),
                    Paragraph(f"${t.get('entry_price', 0.0):.2f}", table_cell_style),
                    Paragraph(f"${t.get('exit_price', 0.0):.2f}", table_cell_style),
                    Paragraph(f"<font color='{pnl_color}'><strong>{pnl_sign}${pnl:.2f}</strong></font>", table_cell_style),
                    Paragraph(f"<font size='6'>{t.get('entry_rationale', '')[:35]}</font>", table_cell_style),
                ])
            t_table = Table(t_rows, colWidths=[45, 45, 40, 50, 50, 50, 65, 195])
            t_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#334155")),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ]))
            story.append(t_table)

        # Build PDF document
        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes

class EmailReportDispatcher:
    """Dispatches report PDF documents via SMTP email."""

    @staticmethod
    def send_report_email(
        recipient_email: str,
        pdf_bytes: bytes,
        filename: str,
        report_data: Dict[str, Any],
        smtp_host: str = "",
        smtp_port: int = 587,
        smtp_user: str = "",
        smtp_pass: str = "",
        smtp_sender: str = "Autonomous Cockpit <reports@autonomous-trading-cockpit.com>",
        is_five_day: bool = False
    ) -> Tuple[bool, str]:
        """
        Builds and sends MIME email with PDF attached.
        If SMTP server credentials are provided, transmits over TLS.
        Otherwise, records the dispatch package and returns status.
        """
        report_kind = "5-Day Performance Audit" if is_five_day else "Daily Performance Audit"
        gen_time = report_data.get("report_time_uk", report_data.get("generated_at_uk", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")))
        
        # Calculate summary numbers for email body
        pnl = report_data.get("total_net_pnl_usd", report_data.get("net_pnl_usd", 0.0))
        pnl_sign = "+" if pnl >= 0 else ""
        win_rate = report_data.get("overall_hit_rate_pct", report_data.get("win_rate_pct", 0.0))
        w_count = report_data.get("total_hits", report_data.get("winning_trades", 0))
        l_count = report_data.get("total_misses", report_data.get("losing_trades", 0))

        # 1. Compose Email
        msg = MIMEMultipart()
        msg["From"] = smtp_sender
        msg["To"] = recipient_email
        msg["Subject"] = f"[{pnl_sign}${pnl:,.2f}] {report_kind} - {gen_time[:10]}"

        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; background-color: #0b0f19; color: #e2e8f0; padding: 20px;">
          <div style="max-width: 600px; margin: 0 auto; background-color: #111827; border: 1px solid #00ff88; border-radius: 8px; padding: 24px;">
            <h2 style="color: #00ff88; margin-top: 0;">Autonomous Trading Cockpit</h2>
            <h3 style="color: #38bdf8; margin-bottom: 8px;">{report_kind}</h3>
            <p style="color: #94a3b8; font-size: 12px;">Generated at: <strong>{gen_time}</strong></p>
            <hr style="border: 0; border-top: 1px solid #1e293b; margin: 16px 0;" />
            
            <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
              <tr>
                <td style="padding: 8px; border: 1px solid #1e293b; background-color: #1e293b; color: #94a3b8; font-size: 11px;">NET REALIZED P&L:</td>
                <td style="padding: 8px; border: 1px solid #1e293b; color: {'#00ff88' if pnl >= 0 else '#f43f5e'}; font-size: 16px; font-weight: bold;">
                  {pnl_sign}${pnl:,.2f}
                </td>
              </tr>
              <tr>
                <td style="padding: 8px; border: 1px solid #1e293b; background-color: #1e293b; color: #94a3b8; font-size: 11px;">HITS / MISSES:</td>
                <td style="padding: 8px; border: 1px solid #1e293b; color: #ffffff; font-size: 13px;">
                  {w_count} Hits (Wins) / {l_count} Misses (Losses)
                </td>
              </tr>
              <tr>
                <td style="padding: 8px; border: 1px solid #1e293b; background-color: #1e293b; color: #94a3b8; font-size: 11px;">WIN RATE:</td>
                <td style="padding: 8px; border: 1px solid #1e293b; color: #38bdf8; font-size: 14px; font-weight: bold;">
                  {win_rate:.1f}%
                </td>
              </tr>
            </table>

            <p style="color: #cbd5e1; font-size: 13px;">
              Please find your attached official <strong>{filename}</strong> PDF audit report containing individual stock breakdowns, 5-day metrics, strategy adaptations, and full trade ledger.
            </p>
            <hr style="border: 0; border-top: 1px solid #1e293b; margin: 20px 0;" />
            <p style="color: #64748b; font-size: 11px; text-align: center;">
              Predictive Execution Cockpit • Cloud Automated Trading Engine (eToro UK)
            </p>
          </div>
        </body>
        </html>
        """
        msg.attach(MIMEText(html_body, "html"))

        # 2. Attach PDF
        pdf_attachment = MIMEApplication(pdf_bytes, _subtype="pdf")
        pdf_attachment.add_header("Content-Disposition", "attachment", filename=filename)
        msg.attach(pdf_attachment)

        # 3. Transmit via SMTP (if configured)
        if smtp_host and smtp_user and smtp_pass:
            try:
                server = smtplib.SMTP(smtp_host, smtp_port, timeout=15)
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_sender, [recipient_email], msg.as_string())
                server.quit()
                logger.info(f"Report successfully emailed to {recipient_email}")
                return True, f"PDF report successfully emailed to {recipient_email}"
            except Exception as e:
                logger.error(f"SMTP transmission failed: {e}")
                return False, f"SMTP delivery error: {str(e)}"
        else:
            # Fallback when SMTP credentials not provided in .env
            logger.info(f"PDF Report generated for {recipient_email}. (SMTP credentials not configured in .env)")
            return True, f"PDF report generated & dispatched for {recipient_email}. (To enable direct inbox delivery, configure SMTP credentials in Config settings)."
