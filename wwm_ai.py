
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
from twilio.rest import Client

# Voice assistant
import platform

def speak(text):
    if platform.system() == "Windows":
        try:
            import pyttsx3
            tts = pyttsx3.init()
            tts.say(text)
            tts.runAndWait()
        except Exception as e:
            st.warning("🗣️ Voice failed on desktop: " + str(e))
    else:
        st.info("🔇 Voice assistant not supported on Streamlit Cloud")


# Twilio setup
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

# Firebase skipped for now
def save_to_firebase(data): pass

# Load model
model = joblib.load("trained_model.pkl")

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

def generate_report(data_dict):
    with open("logs/treatment_report.txt", "w") as f:
        for k, v in data_dict.items():
            f.write(f"{k}: {v}\n")

# App layout
st.set_page_config(page_title="Smart STP", layout="wide")
st.title("💧 Smart STP | AI-Powered Dashboard & Log Analyzer")
tab1, tab2 = st.tabs(["📊 Dashboard", "📂 Upload & Analyze"])

# ---------------- Tab 1 --------------------
with tab1:
    ph = get_live_ph()
    if ph is not None:
        st.success(f"📡 Live pH: {ph:.2f}")
        speak(f"Live pH is {ph:.2f}")
    else:
        ph = st.number_input("Manual pH input (sensor offline)", 0.0, 14.0, 7.0)

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

        # Alerts
        if results['BOD_treated'] < 10 and results['COD_treated'] < 50:
            st.success("🟢 Excellent – Reusable water")
        elif results['BOD_treated'] < 30:
            st.warning("🟡 Moderate – Needs additional polishing")
        else:
            st.error("🔴 Poor quality – Unsafe for discharge")

        # SMS Alert
        if bod > 300 or cod > 500 or results['pH_treated'] < 6.5:
            send_alert_sms("🚨 STP Alert: Water quality out of range!")

        # Save logs
        full_record = {
            "timestamp": datetime.datetime.now().isoformat(),
            "BOD": bod, "COD": cod, "TSS": tss, "Oil": oil,
            "pH": ph, "Ammonical_N": ammonical, "Total_N": total_n,
            "Flow": flow_rate, **results
        }
        os.makedirs("logs", exist_ok=True)
        df = pd.DataFrame([full_record])
        log_file = "logs/full_logs.csv"
        if os.path.exists(log_file):
            df.to_csv(log_file, mode='a', header=False, index=False)
        else:
            df.to_csv(log_file, index=False)
        generate_report(full_record)
        st.success("📁 Logs saved and report generated ✅")

        # Insert expert motor & chlorine logic here
# ⚙️ Motor Automation Schedule (Smart Prediction)
st.subheader("⚙️ Motor Automation Schedule")

# Assumptions
total_volume = flow_rate * 60 * 24  # Convert L/min → L/day
motor_capacity = st.selectbox("Motor Speed (L/min)", [10, 20, 30], index=1)
high_load = bod > 300 or cod > 500

if high_load:
    batches_per_day = 2  # For high load, run twice a day
    runtime_per_batch = int((total_volume / batches_per_day) / motor_capacity)
    time_slots = ["7:00 AM – 8:00 AM", "5:00 PM – 6:00 PM"]
    st.error("🔁 High Load Detected – 2 Daily Motor Cycles Required")
else:
    batches_per_day = 1  # For moderate load
    runtime_per_batch = int(total_volume / motor_capacity)
    time_slots = ["8:00 AM – 9:00 AM"]
    st.warning("⚠️ Moderate Load – 1 Cycle Enough")

st.markdown(f"✅ **Runtime per Cycle:** {runtime_per_batch} minutes")
for i, slot in enumerate(time_slots[:batches_per_day]):
    st.markdown(f"🕒 **Cycle {i+1}:** {slot}")

# 🧪 Chlorination Calculation (Smart Dose)
st.subheader("🧴 Chlorination Dose Calculation")

# Chlorine dosing logic
if bod > 100 or cod > 300 or tss > 150:
    target_dose_mg_per_l = 5  # Heavy
    dose_level = "🔴 Heavy Chlorination"
elif bod > 30 or cod > 150:
    target_dose_mg_per_l = 2.5  # Light
    dose_level = "🟠 Light Chlorination"
else:
    target_dose_mg_per_l = 0
    dose_level = "🟢 No Chlorination Required"

st.markdown(f"**{dose_level}**")

if target_dose_mg_per_l > 0:
    batch_volume = 1000  # Default batch size
    total_chlorine_mg = target_dose_mg_per_l * batch_volume
    chlorine_strength_mg_per_l = 10000  # 1% solution (10000 mg/L)
    chlorine_volume_ml = round(total_chlorine_mg / chlorine_strength_mg_per_l * 1000, 2)

    st.info(f"✅ Target Dose: **{target_dose_mg_per_l} mg/L**")
    st.info(f"📦 For 1000L batch: **{chlorine_volume_ml} mL of 1% chlorine solution**")
    st.caption("ℹ️ Assumes 1% chlorine solution (10,000 mg/L strength)")
else:
    st.success("✅ No chlorine addition required for current input levels.")


    # Smart QR Code
    st.subheader("📱 Access Dashboard on Mobile")
    local_ip = get_local_ip()
    smart_url = f"http://{local_ip}:8501"
    qr = qrcode.make(smart_url)
    buf = BytesIO()
    qr.save(buf); buf.seek(0)
    st.image(Image.open(buf), caption=f"URL: {smart_url}", width=250)
    st.code(smart_url, language='text')
    st.button("📋 Copy Link", on_click=lambda: st.toast("Link copied!", icon="✅"))

# ---------------- Tab 2 --------------------
# 📂 Tab 2: Upload Company CSV, Analyze Logs & Visualize Trends
with tab2:
    st.header("📤 Upload Company CSV for Analysis")

    uploaded_file = st.file_uploader("📁 Upload CSV File (with timestamp, BOD, COD, pH, etc.)", type=["csv"])

    if uploaded_file is not None:
        try:
            import matplotlib.pyplot as plt

            df = pd.read_csv(uploaded_file, parse_dates=["timestamp"])

            st.success(f"✅ File loaded: {uploaded_file.name} — {len(df)} records")

            # 📅 Date filter
            st.subheader("📅 Filter by Date Range")
            col1, col2 = st.columns(2)
            with col1:
                start_date = st.date_input("From", value=df['timestamp'].min().date())
            with col2:
                end_date = st.date_input("To", value=df['timestamp'].max().date())

            filtered_df = df[(df['timestamp'].dt.date >= start_date) & (df['timestamp'].dt.date <= end_date)]

            st.dataframe(filtered_df, use_container_width=True)

            # ⬇️ Download filtered data
            csv = filtered_df.to_csv(index=False).encode('utf-8')
            st.download_button("⬇️ Download Filtered CSV", data=csv, file_name="filtered_uploaded_logs.csv", mime="text/csv")

            # 📊 Summary
            st.subheader("📈 Summary Stats")
            num_cols = ['BOD', 'COD', 'pH', 'TSS', 'Ammonical_N', 'Total_N']
            stats = filtered_df[num_cols].describe().T
            st.dataframe(stats)

            # 📉 Trend graph
            st.subheader("📊 Trend Graph")
            param = st.selectbox("Select Parameter to Visualize", options=num_cols)
            fig, ax = plt.subplots()
            ax.plot(filtered_df["timestamp"], filtered_df[param], marker='o')
            ax.set_xlabel("Date")
            ax.set_ylabel(param)
            ax.set_title(f"{param} Trend Over Time")
            st.pyplot(fig)

        except Exception as e:
            st.error(f"❌ Error processing CSV: {e}")
    else:
        st.info("👆 Upload a CSV file to begin.")

