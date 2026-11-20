import csv
import json
import os
import urllib.request
from datetime import datetime
import pandas as pd
import streamlit as st
from google import genai
from google.genai import types

# Reads your API key securely from Streamlit Cloud Secrets (or local environment)
API_KEY = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", ""))
client = genai.Client(api_key=API_KEY)

OWNER_PIN = "1501"  # Change this to your mom's secret 4-digit PIN!
LEADS_FILE = "tattvamasi_leads.csv"

FALLBACK_RATES = {
    "USD": 0.0118, "GBP": 0.0092, "EUR": 0.0109, "AED": 0.0433,
    "SGD": 0.0158, "CAD": 0.0163, "AUD": 0.0181, "JPY": 1.81, "INR": 1.0
}

def calculate_yoga_quote(country: str, currency_code: str, classes_per_month: int) -> str:
    """Calculates exact monthly Group and Personal 1-on-1 prices based on country and classes/month, converting to local currency if outside India."""
    is_india = country.strip().lower() in ["india", "in", "bharat"]
    currency = currency_code.strip().upper()
    
    if is_india:
        group_inr = 150 * classes_per_month
        personal_inr = 500 * classes_per_month
        return (
            f"India Pricing for {classes_per_month} classes/month:\n"
            f"- Standard Group Class (₹150/class): ₹{group_inr:,}/month\n"
            f"- Personal 1-on-1 Class (₹500/class): ₹{personal_inr:,}/month"
        )
    else:
        group_inr = 500 * classes_per_month
        personal_inr = 750 * classes_per_month
        rate = FALLBACK_RATES.get(currency, 0.0118)
        try:
            url = "https://er-api.com"
            with urllib.request.urlopen(url, timeout=4) as response:
                data = json.loads(response.read().decode())
                if currency in data.get("rates", {}):
                    rate = data["rates"][currency]
        except Exception:
            pass
            
        group_local = round(group_inr * rate, 2)
        personal_local = round(personal_inr * rate, 2)
        return (
            f"International Pricing for {classes_per_month} classes/month (converted to {currency}):\n"
            f"- Standard Group Class: {currency} {group_local:,.2f}/month\n"
            f"- Personal 1-on-1 Class: {currency} {personal_local:,.2f}/month"
        )

def save_lead(
    name: str,
    country: str,
    city: str,
    mode: str,
    program: str,
    classes_per_month: int,
    plan_type: str,
    quoted_price: str,
    phone: str
) -> str:
    """Saves a student's complete inquiry and trial booking details into tattvamasi_leads.csv."""
    file_exists = os.path.isfile(LEADS_FILE)
    with open(LEADS_FILE, mode="a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow([
                "Date & Time", "Student Name", "Country", "City/Area",
                "Mode", "Program", "Classes/Month", "Plan Type", "Quoted Price", "Phone/WhatsApp"
            ])
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M"), name, country, city,
            mode, program, classes_per_month, plan_type, quoted_price, phone
        ])
    return "Student booking successfully saved in Tattvamasi's database."

TATTVAMASI_PROMPT = """You are the warm, attentive virtual receptionist for Tattvamasi Yoga Studio, led by an experienced certified instructor (MSc in Yoga, RYT-200, 8+ years experience).
Follow this exact step-by-step conversation flow naturally (ask 1-2 short questions at a time so the visitor never feels overwhelmed):

Step 1 (Join Intent): Confirm whether they are looking to join yoga classes (and which style interests them: Therapeutic Yoga, Prenatal Yoga, Kids Yoga, General Wellness Yoga, Meditation, or Tabata).
Step 2 (Location Check): Ask which **Country** and **City/Area** they live in.
Step 3 (Online vs. Offline Routing):
- If they live **near Whitefield, Bengaluru** (e.g., Whitefield, ITPL, Brookefield, Varthur, Marathahalli, Hoodi, Kadugodi), let them choose whether they prefer **In-Studio (Offline) near Whitefield** or **Online Live Classes**.
- If they live **elsewhere in India** or **outside India**, let them know they can join via **Online Live Classes** from home (and ask their preferred time zone/slot).
Step 4 (Classes per Month & Dynamic Pricing): Ask **how many classes per month** they are looking to take (for example: 8 classes/month for twice a week, or 12 classes/month for thrice a week).
- As soon as they give the number of classes per month AND you know their country, IMMEDIATELY call the `calculate_yoga_quote` tool (pass their country, their 3-letter local currency code like USD, GBP, AED, EUR, SGD, CAD, AUD, or INR, and the integer number of classes) and present both the **Standard Group** and **Personal 1-on-1** monthly totals clearly!
Step 5 (Booking & Lead Capture): Ask which plan they prefer (Group or Personal 1-on-1), plus their **Name** and **Phone / WhatsApp Number** to schedule their session or trial.
- Once you have their Name, Country, City, Mode (Online/Offline), Program, Classes/Month, Plan Type, Quoted Price, and Phone/WhatsApp Number, IMMEDIATELY call `save_lead` and warmly confirm that Tattvamasi will reach out shortly!

Keep all replies concise, warm, and well-formatted (under 4 sentences per turn).
"""

st.set_page_config(page_title="Tattvamasi Yoga Studio", page_icon="🪷", layout="wide")

# Sidebar: PIN-Protected Owner Dashboard
with st.sidebar:
    st.title("🪷 Tattvamasi")
    st.caption("Studio Owner Access")
    st.divider()
    
    entered_pin = st.text_input("🔒 Enter Owner PIN to view leads:", type="password")
    if entered_pin == OWNER_PIN:
        st.success("Owner Unlocked")
        st.subheader("📋 Student Inquiries")
        if os.path.isfile(LEADS_FILE):
            df = pd.read_csv(LEADS_FILE)
            st.dataframe(df, use_container_width=True, hide_index=True)
            with open(LEADS_FILE, "r", encoding="utf-8") as f:
                st.download_button("⬇️ Download Leads (CSV)", f, file_name=LEADS_FILE, mime="text/csv")
        else:
            st.info("No student inquiries saved yet.")
    elif entered_pin:
        st.error("Incorrect PIN")

# Initialize Session State
if "chat" not in st.session_state:
    st.session_state.chat = client.chats.create(
        model="gemini-3.5-flash-lite",
        config=types.GenerateContentConfig(
            system_instruction=TATTVAMASI_PROMPT,
            tools=[calculate_yoga_quote, save_lead],
            temperature=0.4,
        )
    )
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "Namaste! Welcome to **Tattvamasi** 🪷\n\nAre you looking to join yoga classes?"
        }
    ]

def handle_user_input(user_text: str):
    st.session_state.messages.append({"role": "user", "content": user_text})
    response = st.session_state.chat.send_message(user_text)
    st.session_state.messages.append({"role": "assistant", "content": response.text})
    st.rerun()

st.header("🪷 Tattvamasi — Personal Yoga & Wellness Assistant")
st.caption("Therapeutic Yoga • Prenatal Yoga • Kids Yoga • Meditation • Tabata")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if len(st.session_state.messages) == 1:
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("✅ Yes, I want to join!", use_container_width=True):
            handle_user_input("Yes, I'm looking to join yoga classes!")
    with col2:
        if st.button("🧘 Explore Programs", use_container_width=True):
            handle_user_input("Yes, I'm interested! What yoga programs do you offer?")
    with col3:
        if st.button("💰 Check Class Pricing", use_container_width=True):
            handle_user_input("I'd like to join and check your class pricing.")

if prompt := st.chat_input("Type your reply here..."):
    handle_user_input(prompt)
