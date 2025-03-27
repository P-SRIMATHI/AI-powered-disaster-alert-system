import feedparser
import re
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import folium_static
from textblob import TextBlob
import sqlite3
from geopy.geocoders import Nominatim

# 🌍 Geolocation setup
geolocator = Nominatim(user_agent="geoapi")

# 📊 Database Setup (using /tmp/ for Streamlit Cloud)
DB_PATH = "/tmp/disaster_alerts.db"
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()

# 🏗️ Ensure the database table exists
cursor.execute("""
    CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        alert TEXT,
        latitude REAL,
        longitude REAL
    )
""")
conn.commit()

# 📰 **RSS Feed URLs**
GDACS_FEED_URL = "https://www.gdacs.org/xml/rss.xml"
USGS_FEED_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_week.atom"

# 🔍 **Function to Extract Location**
def extract_location(alert):
    location = None
    try:
        loc = geolocator.geocode(alert)
        if loc:
            location = (loc.latitude, loc.longitude)
    except:
        pass
    return location

# 📡 **Function to Fetch Alerts from GDACS & USGS**
def fetch_alerts():
    alerts = []

    # 🛑 Debug log: Check if feeds are accessible
    st.write("📡 Fetching alerts from GDACS & USGS...")

    # Fetch GDACS alerts
    gdacs_feed = feedparser.parse(GDACS_FEED_URL)
    if not gdacs_feed.entries:
        st.error("⚠️ No alerts found in GDACS feed!")

    for entry in gdacs_feed.entries:
        alert_text = f"🌍 {entry.title} - {entry.summary}"
        location = extract_location(entry.title)
        alerts.append((alert_text, location))

    # Fetch USGS Earthquake alerts
    usgs_feed = feedparser.parse(USGS_FEED_URL)
    if not usgs_feed.entries:
        st.error("⚠️ No alerts found in USGS feed!")

    for entry in usgs_feed.entries:
        alert_text = f"🌍 {entry.title} - {entry.summary}"
        location = extract_location(entry.title)
        alerts.append((alert_text, location))

    return alerts

# 🔍 **Function to Analyze and Store Alerts**
def analyze_and_store_alerts(alerts):
    new_alerts = []
    for alert, location in alerts:
        try:
            cursor.execute("INSERT INTO alerts (alert, latitude, longitude) VALUES (?, ?, ?)", 
                           (alert, location[0] if location else None, location[1] if location else None))
            conn.commit()
            new_alerts.append((alert, location))
        except sqlite3.OperationalError as e:
            st.error(f"Database error: {e}")

    return new_alerts

# 🎨 **Streamlit UI**
st.title("🚨 AI-Powered Disaster Alert System")

# 🌍 **Map Display**
disaster_map = folium.Map(location=[20, 78], zoom_start=3)
cursor.execute("SELECT alert, latitude, longitude FROM alerts")
locations = cursor.fetchall()

for alert, lat, lon in locations:
    if lat and lon:
        folium.Marker([lat, lon], popup=alert).add_to(disaster_map)

folium_static(disaster_map)

# 📰 **Fetch & Display Alerts**
if st.button("Fetch Latest Disaster Alerts"):
    alerts = fetch_alerts()
    new_alerts = analyze_and_store_alerts(alerts)

    if new_alerts:
        st.write("### 🚨 Emergency Alerts from GDACS & USGS:")
        for alert, location in new_alerts:
            loc_text = f" (Location: {location})" if location else " (Location: Unknown)"
            st.write(f"- {alert}{loc_text}")
    else:
        st.write("✅ No major disaster-related alerts detected.")

# 🏛️ **View Past Alerts**
if st.button("View Past Alerts"):
    cursor.execute("SELECT alert, latitude, longitude FROM alerts")
    past_alerts = cursor.fetchall()

    if past_alerts:
        st.write("### 🕒 Historical Disaster Alerts:")
        for alert, lat, lon in past_alerts:
            loc_text = f" (Location: {lat}, {lon})" if lat and lon else " (Location: Unknown)"
            st.write(f"- {alert}{loc_text}")
    else:
        st.write("📜 No past alerts recorded.")
