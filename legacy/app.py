import streamlit as st
import pandas as pd
import numpy as np
import xgboost as xgb
from datetime import timedelta
import time
import plotly.express as px

st.set_page_config(page_title="E20 Phase Separation Predictor", layout="wide")
st.title("E20 Underground Tank: IoT Telemetry & ML Forecast")

@st.cache_resource
def load_model():
    model = xgb.XGBRegressor()
    model.load_model('models/xgb_model.json')
    return model

model = load_model()

# 1. Load Base Sensor Feed
try:
    sensor_df = pd.read_csv('data/sensor_log.csv', parse_dates=['timestamp'])
    sensor_df = sensor_df.sort_values('timestamp')
except FileNotFoundError:
    st.error("Sensor log not found. Run generate_sensor_log.py first.")
    st.stop()

# 2. Control Panel
st.sidebar.header("Data Source")
mode = st.sidebar.radio("Select Input Feed", ["Live Sensor Feed", "Manual Override"])
simulate_live = st.sidebar.checkbox("Simulate Real-Time Data Stream (IoT)")

# 3. UI Placeholders
kpi_placeholder = st.empty() 
st.subheader("Moisture Tracking: 14-Day History & 3-Day ML Forecast")
chart_placeholder = st.empty()
metrics_placeholder = st.empty()
alert_placeholder = st.empty()

def update_dashboard(current_sensor_df, is_manual=False, manual_inputs=None):
    if is_manual:
        temp, hum, vapor, current_water = manual_inputs
        last_timestamp = pd.Timestamp.now()
    else:
        latest_data = current_sensor_df.iloc[-1]
        temp = latest_data['temp_swing_c']
        hum = latest_data['humidity_pct']
        vapor = latest_data['vapor_space_vol']
        current_water = latest_data['water_ppm']
        last_timestamp = latest_data['timestamp']

    with kpi_placeholder.container():
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Current Water", f"{int(current_water)} ppm")
        col2.metric("Temp Swing", f"{temp:.1f} °C")
        col3.metric("Ambient Humidity", f"{hum:.1f} %")
        col4.metric("Tank Vapor Space", f"{vapor:.1f} %")

    # ML Inference
    input_df = pd.DataFrame({
        'temp_swing_c': [temp],
        'humidity_pct': [hum],
        'vapor_space_vol': [vapor],
        'current_water_ppm': [current_water]
    })
    daily_ingress = model.predict(input_df)[0]

    # Prepare Data for Charting
    history_plot = current_sensor_df[['timestamp', 'water_ppm']].copy()
    history_plot.rename(columns={'water_ppm': 'Historical (Actual)'}, inplace=True)

    # 3-Day Forecast (72 hours) with high-detail diurnal curves
    forecast_dates = [last_timestamp + timedelta(hours=i) for i in range(0, 73)]
    hourly_ingress = daily_ingress / 24.0
    
    forecast_water = [current_water]
    accumulated_water = current_water
    
    for i in range(1, 73):
        diurnal_cycle = np.cos(i * (2 * np.pi / 24)) * (hourly_ingress * 1.5)
        noise = np.random.normal(0, 0.3)
        hourly_step = max(0.1, hourly_ingress + diurnal_cycle + noise)
        accumulated_water += hourly_step
        forecast_water.append(accumulated_water)
    
    forecast_plot = pd.DataFrame({
        'timestamp': forecast_dates,
        'Forecast (Predicted)': forecast_water
    })

    # Combine data for Plotly
    chart_df = pd.concat([history_plot, forecast_plot], ignore_index=True)

    # Render Plotly Chart
    fig = px.line(
        chart_df, 
        x='timestamp', 
        y=['Historical (Actual)', 'Forecast (Predicted)'],
        color_discrete_sequence=['#1f77b4', '#00C4B4'] # Dark blue for history, bright teal for forecast
    )
    
    fig.update_layout(
        xaxis_title="",
        yaxis_title="Water Content (ppm)",
        legend_title="",
        hovermode="x unified", # Shows data for both lines simultaneously on hover
        margin=dict(l=0, r=0, t=10, b=0)
    )
    
    chart_placeholder.plotly_chart(fig, use_container_width=True)

    # Alerts
    threshold = 5000
    final_ppm = forecast_water[-1]
    
    with metrics_placeholder.container():
        st.metric(label="Predicted Ingress Velocity", value=f"+{int(daily_ingress)} ppm/day")
        
    with alert_placeholder.container():
        if final_ppm >= threshold:
            st.error("🚨 HIGH RISK: Phase separation imminent within 72 hours. Critical threshold (5000 ppm) breached.")
        elif final_ppm >= threshold * 0.8:
            st.warning("⚠️ WARNING: Water levels rapidly approaching critical limit.")
        else:
            st.success("✅ STABLE: Tank conditions within safe operational limits.")

# 4. Execution Flow
if mode == "Manual Override":
    temp = st.sidebar.slider("Temperature Swing (°C)", 2.0, 25.0, 15.0)
    hum = st.sidebar.slider("Ambient Humidity (%)", 30.0, 100.0, 75.0)
    vapor = st.sidebar.slider("Vapor Space (Tank % Empty)", 10.0, 95.0, 60.0)
    current_water = st.sidebar.slider("Current Water Content (ppm)", 500.0, 4800.0, 1200.0)
    update_dashboard(sensor_df, is_manual=True, manual_inputs=(temp, hum, vapor, current_water))

elif mode == "Live Sensor Feed":
    if simulate_live:
        st.sidebar.success("🔴 Live Stream Active...")
        live_df = sensor_df.copy()
        
        for _ in range(500):
            latest = live_df.iloc[-1]
            
            new_row = pd.DataFrame({
                'timestamp': [latest['timestamp'] + timedelta(hours=1)],
                'temp_swing_c': [latest['temp_swing_c'] + np.random.uniform(-1, 1)],
                'humidity_pct': [latest['humidity_pct'] + np.random.uniform(-2, 2)],
                'vapor_space_vol': [latest['vapor_space_vol']],
                'water_ppm': [latest['water_ppm'] + np.random.uniform(1.5, 5.5)]
            })
            
            live_df = pd.concat([live_df, new_row], ignore_index=True)
            
            if len(live_df) > 336: 
                live_df = live_df.iloc[1:]
                
            update_dashboard(live_df)
            time.sleep(1)
    else:
        update_dashboard(sensor_df)