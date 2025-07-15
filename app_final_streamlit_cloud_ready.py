
import streamlit as st
import requests
import numpy as np
import pandas as pd
import joblib
import datetime
import os
import socket
import qrcode
from io import BytesIO
from PIL import Image
import matplotlib.pyplot as plt
import platform
from twilio.rest import Client

# --- SMS Alert Setup ---
TWILIO_SID = "ACc96ccfdf3f7ceb524dd6425bade6b22a"
TWILIO_AUTH = "7d802eaf319b89931797264e2858fe31"
TWILIO_FROM = "+1 970 676 6534"
TWILIO_TO = "+919731851791"
def send_alert_sms(message):
    try:
        client = Client(TWILIO_SID, TWILIO_AUTH)
        client.messages.create(body=message, from_=TWILIO_FROM, to=TWILIO_TO)
    except Exception as e:
        st.warning(f"SMS failed: {e}")

# --- Safe Voice Assistant Stub ---
def speak(text):
    if platform.system() == "Windows":
        try:
            import pyttsx3
            tts = pyttsx3.init()
            tts.say(text)
            tts.runAndWait()
        except Exception:
            pass
    else:
        pass

# --- Load Model ---
model = joblib.load("wastewater_model.pkl")

# --- Helper Functions ---
def get_live_ph():
    try:
        r = requests.get("http://localhost:5000/get_ph")
        if r.status_code == 200:
            return float(r.json().get("ph"))
    except:
        return None

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except:
        ip = "localhost"
    finally:
        s.close()
    return ip

# --- Streamlit Layout ---
st.set_page_config(page_title="Smart STP", layout="wide")
st.title("💧 Smart STP | AI-Powered Dashboard & Log Analyzer")
tab1, tab2 = st.tabs(["📊 Dashboard", "📂 Upload & Analyze"])

# --- TAB 1: Dashboard ---
with tab1:
    ph = get_live_ph()
    if ph:
        st.success(f"📡 Live pH: {ph:.2f}")
        speak(f"Live pH is {ph:.2f}")
    else:
        ph = st.number_input("Manual pH (sensor offline)", 0.0, 14.0, 7.0)

    col1, col2 = st.columns(2)
    with col1:
        bod = st.number_input("BOD (mg/L)", 0.0)
        cod = st.number_input("COD (mg/L)", 0.0)
        tss = st.number_input("TSS (mg/L)", 0.0)
    with col2:
        oil = st.number_input("Oil & Grease (mg/L)", 0.0)
        ammonical = st.number_input("Ammonical Nitrogen (mg/L)", 0.0)
        total_n = st.number_input("Total Nitrogen (mg/L)", 0.0)
        flow_rate = st.number_input("Flow Rate (L/min)", 0.0)

    if st.button("🔮 Predict Treatment"):
        input_data = np.array([[bod, cod, tss, oil, ph, ammonical, total_n]])
        prediction = model.predict(input_data)[0]
        labels = ['BOD_treated', 'COD_treated', 'TSS_treated', 'Oil_and_Grease_treated',
                  'pH_treated', 'Ammonical_Nitrogen_treated', 'Total_Nitrogen_treated']
        results = dict(zip(labels, prediction))
        for k, v in results.items():
            st.write(f"{k}: {v:.2f} mg/L")

        if results['BOD_treated'] < 10 and results['COD_treated'] < 50:
            st.success("🟢 Excellent – Reusable water")
        elif results['BOD_treated'] < 30:
            st.warning("🟡 Moderate – Needs polishing")
        else:
            st.error("🔴 Poor – Unsafe")

        if bod > 300 or cod > 500 or results['pH_treated'] < 6.5:
            send_alert_sms("🚨 STP Alert: Water quality out of range!")

        # Save logs
        record = {
            "timestamp": datetime.datetime.now().isoformat(),
            "BOD": bod, "COD": cod, "TSS": tss, "Oil": oil,
            "pH": ph, "Ammonical_N": ammonical, "Total_N": total_n,
            "Flow": flow_rate, **results
        }
        os.makedirs("logs", exist_ok=True)
        pd.DataFrame([record]).to_csv("logs/full_logs.csv", mode='a', header=not os.path.exists("logs/full_logs.csv"), index=False)

        # Motor Logic
        st.subheader("⚙️ Motor Automation Schedule")
        total_volume = flow_rate * 60 * 24
        motor_capacity = st.selectbox("Motor Speed (L/min)", [10, 20, 30], index=1)
        high_load = bod > 300 or cod > 500
        if high_load:
            batches = 2
            time_slots = ["7:00 AM – 8:00 AM", "5:00 PM – 6:00 PM"]
            st.error("🔁 High Load – 2 Motor Cycles Required")
        else:
            batches = 1
            time_slots = ["8:00 AM – 9:00 AM"]
            st.warning("⚠️ Moderate Load – 1 Cycle Enough")
        runtime = int((total_volume / batches) / motor_capacity)
        st.markdown(f"✅ Runtime per Cycle: **{runtime} mins**")
        for i, slot in enumerate(time_slots[:batches]):
            st.markdown(f"🕒 Cycle {i+1}: {slot}")

        # Chlorination
        st.subheader("🧴 Chlorination Dose Calculation")
        if bod > 100 or cod > 300 or tss > 150:
            dose = 5
            level = "🔴 Heavy Chlorination"
        elif bod > 30 or cod > 150:
            dose = 2.5
            level = "🟠 Light Chlorination"
        else:
            dose = 0
            level = "🟢 No Chlorination Needed"
        st.markdown(f"**{level}**")
        if dose > 0:
            vol_ml = round(dose * 1000 / 10, 2)
            st.info(f"✔ Dose: {dose} mg/L → Add **{vol_ml} mL per 1000L** (1% chlorine)")
        else:
            st.success("✅ No chlorine needed")

        # QR
        st.subheader("📱 Access Dashboard on Mobile")
        local_ip = get_local_ip()
        url = f"http://{local_ip}:8501"
        qr = qrcode.make(url)
        buf = BytesIO(); qr.save(buf); buf.seek(0)
        st.image(Image.open(buf), caption=f"URL: {url}", width=250)
        st.code(url)
        st.button("📋 Copy Link", on_click=lambda: st.toast("Link copied!", icon="✅"))

# --- TAB 2: Upload & Analyze ---
with tab2:
    st.header("📤 Upload CSV for Analysis")
    uploaded_file = st.file_uploader("Upload a CSV file with logs", type=["csv"])
    if uploaded_file:
        try:
            df = pd.read_csv(uploaded_file, parse_dates=["timestamp"])
            st.success(f"✅ Loaded {uploaded_file.name} with {len(df)} records")
            start_date = st.date_input("From", value=df["timestamp"].min().date())
            end_date = st.date_input("To", value=df["timestamp"].max().date())
            filtered = df[(df["timestamp"].dt.date >= start_date) & (df["timestamp"].dt.date <= end_date)]
            st.dataframe(filtered, use_container_width=True)
            st.download_button("⬇ Download Filtered", data=filtered.to_csv(index=False).encode('utf-8'), file_name="filtered_logs.csv")

            st.subheader("📊 Summary Stats")
            num_cols = ["BOD", "COD", "pH", "TSS", "Ammonical_N", "Total_N"]
            st.dataframe(filtered[num_cols].describe().T)

            st.subheader("📉 Trend Graph")
            param = st.selectbox("Choose Parameter", num_cols)
            fig, ax = plt.subplots()
            ax.plot(filtered["timestamp"], filtered[param], marker="o")
            ax.set_xlabel("Date"); ax.set_ylabel(param); ax.set_title(f"{param} Over Time")
            st.pyplot(fig)
        except Exception as e:
            st.error(f"Error reading CSV: {e}")
    else:
        st.info("Upload a valid CSV file with `timestamp` column.")
