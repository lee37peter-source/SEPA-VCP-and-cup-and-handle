"""Breakout email via SMTP (Gmail app password by default).

Environment variables (set as GitHub repository secrets):
  SMTP_USER       your Gmail address
  SMTP_PASSWORD   a Gmail *app password* (not your normal password)
  ALERT_TO        where to send (defaults to SMTP_USER); comma-separate several addresses
  SMTP_HOST / SMTP_PORT  optional, default smtp.gmail.com / 465"""
from __future__ import annotations

import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape


def build_email(signals: list[dict], market: dict, site_url: str, data_date: str) -> tuple[str, str, str]:
    tickers = list(dict.fromkeys(s["ticker"] for s in signals))
    n = len(tickers)
    tick = ", ".join(tickers[:6]) + (" ..." if n > 6 else "")
    subject = f"{n} breakout{'s' if n != 1 else ''} {data_date}: {tick}"
    color = {"green": "#1a7f37", "amber": "#9a6700", "red": "#cf222e"}.get(market.get("color"), "#555")
    rows = "".join(
        f"<tr><td style='padding:6px 10px'><b>{escape(s['ticker'])}</b><br>"
        f"<span style='color:#666;font-size:12px'>{escape(s.get('name', ''))}</span></td>"
        f"<td style='padding:6px 10px'>{escape(s['pattern_name'])}</td>"
        f"<td style='padding:6px 10px'>{s['status']}</td>"
        f"<td style='padding:6px 10px;text-align:right'>{s['close']:.2f}</td>"
        f"<td style='padding:6px 10px;text-align:right'>{s['pivot']:.2f}</td>"
        f"<td style='padding:6px 10px;text-align:right'>{s['stop']:.2f} ({s['risk_pct']:.1f}%)</td>"
        f"<td style='padding:6px 10px;text-align:right'>{s.get('vol_x') or 0:.1f}x</td>"
        f"<td style='padding:6px 10px;text-align:right'>{s['score']:.0f}</td></tr>"
        for s in signals)
    html = f"""<div style="font-family:-apple-system,Segoe UI,Arial,sans-serif;font-size:14px;color:#111">
<p style="margin:0 0 8px">Market: <b style="color:{color}">{escape(market.get('regime', '?'))}</b>
 &mdash; {escape(market.get('advice', ''))}</p>
<table style="border-collapse:collapse;border:1px solid #ddd">
<tr style="background:#f4f4f4;text-align:left"><th style="padding:6px 10px">Ticker</th>
<th style="padding:6px 10px">Pattern</th><th style="padding:6px 10px">Signal</th>
<th style="padding:6px 10px">Close</th><th style="padding:6px 10px">Pivot</th>
<th style="padding:6px 10px">Stop</th><th style="padding:6px 10px">Vol</th>
<th style="padding:6px 10px">Score</th></tr>{rows}</table>
<p><a href="{escape(site_url)}">Open the screener</a> for charts and today's setups.</p>
<p style="color:#888;font-size:12px">Automated screen, not investment advice. Check every chart yourself.</p>
</div>"""
    text = "\n".join(f"{s['ticker']:6} {s['pattern_name']:16} {s['status']:9} close {s['close']:.2f} "
                     f"pivot {s['pivot']:.2f} stop {s['stop']:.2f}" for s in signals)
    text = f"Market: {market.get('regime')}\n\n{text}\n\n{site_url}"
    return subject, html, text


def send(signals: list[dict], market: dict, site_url: str, data_date: str, log=print) -> bool:
    user, pw = os.environ.get("SMTP_USER"), os.environ.get("SMTP_PASSWORD")
    if not (user and pw):
        log("Email skipped: SMTP_USER / SMTP_PASSWORD not set")
        return False
    if not signals:
        log("Email skipped: no new breakouts today")
        return False
    to = [a.strip() for a in os.environ.get("ALERT_TO", user).split(",") if a.strip()]
    subject, html, text = build_email(signals, market, site_url, data_date)
    msg = MIMEMultipart("alternative")
    msg["Subject"], msg["From"], msg["To"] = subject, user, ", ".join(to)
    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", "465"))
    try:
        with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=30) as s:
            s.login(user, pw)
            s.sendmail(user, to, msg.as_string())
        log(f"Email sent to {', '.join(to)}")
        return True
    except Exception as e:
        log(f"Email failed: {e}")
        return False
