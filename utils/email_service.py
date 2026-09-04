"""
NeuroLearn 2.0 — Email Service (Resend API)
Handles SOS alerts, daily reports, cognitive reports, and doctor notifications.
"""

import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
RESEND_FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL", "NeuroLearn <onboarding@resend.dev>")


def send_email(to_email, subject, html_body):
    """Send an email via Resend API."""
    if not RESEND_API_KEY:
        print(f"⚠️ [EMAIL] No RESEND_API_KEY set. Skipping email to {to_email}")
        return False

    try:
        url = "https://api.resend.com/emails"
        headers = {
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "from": RESEND_FROM_EMAIL,
            "to": [to_email],
            "subject": subject,
            "html": html_body
        }

        r = requests.post(url, headers=headers, json=payload, timeout=10)
        if r.status_code in [200, 201]:
            print(f"📧 [EMAIL] Sent to {to_email}: {subject}")
            return True
        else:
            print(f"⚠️ [EMAIL] Failed ({r.status_code}): {r.text}")
            return False
    except Exception as e:
        print(f"⚠️ [EMAIL] Error: {str(e)}")
        return False


def send_sos_alert(patient_name, caregiver_email, doctor_email=None, location_url=None):
    """Send emergency SOS alert to caregiver and doctor."""
    import time
    timestamp = time.strftime("%I:%M %p, %B %d, %Y")

    location_html = ""
    if location_url:
        location_html = f'''
        <div style="background: #FEF2F2; border: 2px solid #EF4444; border-radius: 12px; padding: 16px; margin: 16px 0;">
            <p style="margin: 0; font-size: 18px;">📍 <strong>Patient Location:</strong></p>
            <a href="{location_url}" style="color: #2563EB; font-size: 20px; font-weight: bold;">
                Open in Google Maps →
            </a>
        </div>
        '''

    html = f'''
    <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background: #EF4444; color: white; padding: 24px; border-radius: 16px; text-align: center;">
            <h1 style="margin: 0; font-size: 32px;">🆘 EMERGENCY ALERT</h1>
            <p style="margin: 8px 0 0; font-size: 18px;">NeuroLearn 2.0 — Patient SOS</p>
        </div>
        
        <div style="padding: 24px 0;">
            <h2 style="color: #1E293B; font-size: 24px;">
                {patient_name} has triggered an emergency alert.
            </h2>
            <p style="color: #475569; font-size: 16px;">
                ⏰ Time: <strong>{timestamp}</strong>
            </p>
            
            {location_html}
            
            <div style="background: #FFF7ED; border: 2px solid #F59E0B; border-radius: 12px; padding: 16px; margin: 16px 0;">
                <p style="margin: 0; font-size: 16px; color: #92400E;">
                    ⚠️ Please check on the patient immediately. If you cannot reach them, 
                    contact local emergency services.
                </p>
            </div>
        </div>
        
        <div style="background: #F1F5F9; padding: 16px; border-radius: 12px; text-align: center;">
            <p style="margin: 0; color: #64748B; font-size: 14px;">
                Sent by NeuroLearn 2.0 — Cognitive Care Platform
            </p>
        </div>
    </div>
    '''

    subject = f"🆘 EMERGENCY — {patient_name} needs help!"
    
    sent = send_email(caregiver_email, subject, html)
    
    if doctor_email:
        send_email(doctor_email, subject, html)
    
    return sent


def send_daily_report(patient_name, caregiver_email, stats):
    """Send daily progress report email."""
    games_played = stats.get("games_played", 0)
    avg_accuracy = stats.get("avg_accuracy", 0)
    streak = stats.get("streak", 0)
    memory_score = stats.get("memory_score", 0)
    attention_score = stats.get("attention_score", 0)

    html = f'''
    <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background: linear-gradient(135deg, #10B981, #059669); color: white; padding: 24px; border-radius: 16px; text-align: center;">
            <h1 style="margin: 0; font-size: 28px;">🧠 Daily Brain Report</h1>
            <p style="margin: 8px 0 0; font-size: 16px;">{patient_name}'s Progress Today</p>
        </div>
        
        <div style="padding: 24px 0;">
            <table style="width: 100%; border-collapse: collapse;">
                <tr>
                    <td style="padding: 12px; border-bottom: 1px solid #E2E8F0;">
                        <span style="font-size: 24px;">🎮</span> Games Played
                    </td>
                    <td style="padding: 12px; border-bottom: 1px solid #E2E8F0; text-align: right; font-weight: bold; font-size: 20px;">
                        {games_played}
                    </td>
                </tr>
                <tr>
                    <td style="padding: 12px; border-bottom: 1px solid #E2E8F0;">
                        <span style="font-size: 24px;">🎯</span> Average Accuracy
                    </td>
                    <td style="padding: 12px; border-bottom: 1px solid #E2E8F0; text-align: right; font-weight: bold; font-size: 20px;">
                        {avg_accuracy}%
                    </td>
                </tr>
                <tr>
                    <td style="padding: 12px; border-bottom: 1px solid #E2E8F0;">
                        <span style="font-size: 24px;">🔥</span> Streak
                    </td>
                    <td style="padding: 12px; border-bottom: 1px solid #E2E8F0; text-align: right; font-weight: bold; font-size: 20px;">
                        {streak} days
                    </td>
                </tr>
                <tr>
                    <td style="padding: 12px; border-bottom: 1px solid #E2E8F0;">
                        <span style="font-size: 24px;">🧠</span> Memory Score
                    </td>
                    <td style="padding: 12px; border-bottom: 1px solid #E2E8F0; text-align: right; font-weight: bold; font-size: 20px;">
                        {memory_score}%
                    </td>
                </tr>
                <tr>
                    <td style="padding: 12px;">
                        <span style="font-size: 24px;">👁️</span> Attention Score
                    </td>
                    <td style="padding: 12px; text-align: right; font-weight: bold; font-size: 20px;">
                        {attention_score}%
                    </td>
                </tr>
            </table>
        </div>
        
        <div style="background: #F1F5F9; padding: 16px; border-radius: 12px; text-align: center;">
            <p style="margin: 0; color: #64748B; font-size: 14px;">
                Sent by NeuroLearn 2.0 — Cognitive Care Platform
            </p>
        </div>
    </div>
    '''

    subject = f"🧠 {patient_name}'s Daily Brain Report — {games_played} games, {avg_accuracy}% accuracy"
    return send_email(caregiver_email, subject, html)


def send_smart_alert(patient_name, caregiver_email, alert_type, message):
    """Send a smart alert when unusual changes are detected."""
    color = "#F59E0B" if alert_type == "warning" else "#EF4444"
    icon = "⚠️" if alert_type == "warning" else "🚨"
    
    html = f'''
    <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background: {color}; color: white; padding: 24px; border-radius: 16px; text-align: center;">
            <h1 style="margin: 0; font-size: 28px;">{icon} Smart Alert</h1>
            <p style="margin: 8px 0 0; font-size: 16px;">{patient_name} — Attention Needed</p>
        </div>
        
        <div style="padding: 24px 0;">
            <p style="font-size: 18px; color: #1E293B; line-height: 1.6;">{message}</p>
        </div>
        
        <div style="background: #F1F5F9; padding: 16px; border-radius: 12px; text-align: center;">
            <p style="margin: 0; color: #64748B; font-size: 14px;">
                Sent by NeuroLearn 2.0 — Cognitive Care Platform
            </p>
        </div>
    </div>
    '''

    subject = f"{icon} Alert: {patient_name} — {message[:60]}"
    return send_email(caregiver_email, subject, html)


def send_doctor_report(patient_name, doctor_email, report_data):
    """Send cognitive report to doctor with location."""
    scores = report_data.get("domain_scores", {})
    location = report_data.get("location", "Not shared")
    period = report_data.get("period", "This Month")
    overall = report_data.get("overall_score", 0)
    
    rows = ""
    for domain, info in scores.items():
        trend_icon = "↑" if info.get("trend", 0) > 0 else ("↓" if info.get("trend", 0) < 0 else "→")
        rows += f'''
        <tr>
            <td style="padding: 10px; border-bottom: 1px solid #E2E8F0; font-size: 16px;">{domain}</td>
            <td style="padding: 10px; border-bottom: 1px solid #E2E8F0; font-weight: bold; font-size: 18px;">{info.get("score", 0)}%</td>
            <td style="padding: 10px; border-bottom: 1px solid #E2E8F0; font-size: 18px;">{trend_icon} {info.get("trend", 0):+d}%</td>
        </tr>
        '''

    html = f'''
    <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background: linear-gradient(135deg, #6366F1, #4F46E5); color: white; padding: 24px; border-radius: 16px; text-align: center;">
            <h1 style="margin: 0; font-size: 28px;">📊 Cognitive Health Report</h1>
            <p style="margin: 8px 0 0; font-size: 16px;">Patient: {patient_name} | Period: {period}</p>
        </div>
        
        <div style="padding: 24px 0;">
            <div style="background: #F0FDF4; border: 2px solid #10B981; border-radius: 12px; padding: 16px; text-align: center; margin-bottom: 20px;">
                <p style="margin: 0; font-size: 16px; color: #475569;">Overall Cognitive Score</p>
                <p style="margin: 8px 0 0; font-size: 36px; font-weight: bold; color: #10B981;">{overall}/100</p>
            </div>
            
            <table style="width: 100%; border-collapse: collapse;">
                <thead>
                    <tr style="background: #F8FAFC;">
                        <th style="padding: 10px; text-align: left;">Domain</th>
                        <th style="padding: 10px; text-align: left;">Score</th>
                        <th style="padding: 10px; text-align: left;">Trend</th>
                    </tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>
            
            <div style="background: #EFF6FF; border-radius: 12px; padding: 16px; margin-top: 20px;">
                <p style="margin: 0; font-size: 14px; color: #1E40AF;">
                    📍 Patient Location: <strong>{location}</strong>
                </p>
            </div>
        </div>
        
        <div style="background: #F1F5F9; padding: 16px; border-radius: 12px; text-align: center;">
            <p style="margin: 0; color: #64748B; font-size: 14px;">
                Sent by NeuroLearn 2.0 — Cognitive Care Platform
            </p>
        </div>
    </div>
    '''

    subject = f"📊 Cognitive Report: {patient_name} — Score {overall}/100"
    return send_email(doctor_email, subject, html)
