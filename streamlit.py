import feedparser
import re
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import folium_static
from textblob import TextBlob
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
import joblib
import sqlite3
from geopy.geocoders import Nominatim
from plyer import notification

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
    words = alert.split()
    for word in words:
        try:
            loc = geolocator.geocode(word)
            if loc:
                location = (loc.latitude, loc.longitude)
                break
        except:
            continue
    return location

# 📡 **Function to Fetch Alerts from GDACS & USGS**
def fetch_alerts():
    alerts = []

    # Fetch GDACS alerts
    gdacs_feed = feedparser.parse(GDACS_FEED_URL)
    for entry in gdacs_feed.entries:
        alert_text = entry.title + " - " + entry.summary
        location = extract_location(alert_text)
        alerts.append((alert_text, location))

    # Fetch USGS Earthquake alerts
    usgs_feed = feedparser.parse(USGS_FEED_URL)
    for entry in usgs_feed.entries:
        alert_text = entry.title + " - " + entry.summary
        location = extract_location(alert_text)
        alerts.append((alert_text, location))

    return alerts

# 🧹 **Function to Clean Alert Text**
def clean_text(text):
    text = re.sub(r'http\S+', '', text)  # Remove URLs
    text = re.sub(r'[^a-zA-Z\s]', '', text)  # Remove special characters
    text = text.lower()  # Convert to lowercase
    return text

# 📌 **Load and Train Disaster Classification Model**
data = pd.read_csv("disaster_tweets.csv")  # Assuming you have a dataset
data['cleaned_text'] = data['text'].apply(clean_text)

pipeline = Pipeline([
    ('tfidf', TfidfVectorizer()),
    ('clf', MultinomialNB())
])
pipeline.fit(data['cleaned_text'], data['label'])

joblib.dump(pipeline, "disaster_model.pkl")

# 🔍 **Function to Analyze Alerts**
def analyze_alerts(alerts):
    disaster_alerts = []
    model = joblib.load("disaster_model.pkl")

    for alert, location in alerts:
        prediction = model.predict([alert])[0]
        sentiment = TextBlob(alert).sentiment.polarity

        if prediction == 1 or sentiment < -0.2:
            disaster_alerts.append((alert, location))
            try:
                cursor.execute("INSERT INTO alerts (alert, latitude, longitude) VALUES (?, ?, ?)", 
                               (alert, location[0] if location else None, location[1] if location else None))
                conn.commit()
                notification.notify(title="🚨 Disaster Alert!", message=alert, timeout=5)
            except sqlite3.OperationalError as e:
                st.error(f"Database error: {e}")

    return disaster_alerts

# 🎨 **Streamlit UI**
st.title("🚨 AI-Powered Disaster Alert System")

# 🌍 **Map Display**
disaster_map = folium.Map(location=[20, 78], zoom_start=4)
cursor.execute("SELECT latitude, longitude FROM alerts")
locations = cursor.fetchall()

for lat, lon in locations:
    if lat and lon:
        folium.Marker([lat, lon], popup="Disaster Alert").add_to(disaster_map)

folium_static(disaster_map)

# 📰 **Fetch & Analyze Alerts**
if st.button("Fetch Latest Disaster Alerts"):
    alerts = fetch_alerts()
    disaster_alerts = analyze_alerts(alerts)
    
    if disaster_alerts:
        st.write("### 🚨 Emergency Alerts from RSS Feeds:")
        for alert, location in disaster_alerts:
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
        for alert in past_alerts:
            loc_text = f" (Location: {alert[1]}, {alert[2]})" if alert[1] and alert[2] else " (Location: Unknown)"
            st.write(f"- {alert[0]}{loc_text}")
    else:
        st.write("📜 No past alerts recorded.")
