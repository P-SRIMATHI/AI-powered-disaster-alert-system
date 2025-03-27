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

# Geolocation setup
geolocator = Nominatim(user_agent="geoapi")

def extract_location(text):
    """Extracts location from disaster alert title (if possible)."""
    location = None
    words = text.split()
    for word in words:
        try:
            loc = geolocator.geocode(word)
            if loc:
                location = (loc.latitude, loc.longitude)
                break
        except:
            continue
    return location

# Function to clean text
def clean_text(text):
    text = re.sub(r'http\S+', '', text)  # Remove URLs
    text = re.sub(r'[^a-zA-Z\s]', '', text)  # Remove special characters
    text = text.lower()  # Convert to lowercase
    return text

# Fetch Disaster Alerts from GDACS (Global Disaster Alert System)
def fetch_gdacs_alerts():
    url = "https://www.gdacs.org/rss.aspx"
    feed = feedparser.parse(url)

    alerts = []
    for entry in feed.entries[:5]:  # Get latest 5 alerts
        alerts.append((clean_text(entry.title), extract_location(entry.title)))
    
    return alerts

# Fetch Earthquake Alerts from USGS (United States Geological Survey)
def fetch_usgs_earthquakes():
    url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_hour.atom"
    feed = feedparser.parse(url)

    earthquakes = []
    for entry in feed.entries[:5]:  # Get latest 5 earthquakes
        earthquakes.append((clean_text(entry.title), extract_location(entry.title)))
    
    return earthquakes

# Load training dataset (Replace with actual dataset)
data = pd.read_csv("disaster_tweets.csv")
data['cleaned_text'] = data['text'].apply(clean_text)

# Train a Naïve Bayes Classifier
pipeline = Pipeline([
    ('tfidf', TfidfVectorizer()),
    ('clf', MultinomialNB())
])
pipeline.fit(data['cleaned_text'], data['label'])  # Assuming 'label' column has 1 for disaster and 0 for non-disaster

# Save model
joblib.dump(pipeline, "disaster_model.pkl")

# Initialize database
conn = sqlite3.connect("disaster_alerts.db")
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        alert TEXT,
        latitude REAL,
        longitude REAL
    )
""")
conn.commit()

# Sentiment Analysis + ML Model Classification
def analyze_alerts(alerts):
    disaster_alerts = []
    model = joblib.load("disaster_model.pkl")
    
    for alert, location in alerts:
        prediction = model.predict([alert])[0]
        sentiment = TextBlob(alert).sentiment.polarity
        if prediction == 1 or sentiment < -0.2:  # If model or sentiment indicates disaster
            disaster_alerts.append((alert, location))
            cursor.execute("INSERT INTO alerts (alert, latitude, longitude) VALUES (?, ?, ?)", 
                           (alert, location[0] if location else None, location[1] if location else None))
            notification.notify(title="🚨 Disaster Alert!", message=alert, timeout=5)
    
    conn.commit()
    return disaster_alerts

# Streamlit UI
st.title("🚨 AI-Powered Disaster Alert System")

# Map Display
disaster_map = folium.Map(location=[20, 78], zoom_start=4)
cursor.execute("SELECT latitude, longitude FROM alerts")
locations = cursor.fetchall()
for lat, lon in locations:
    if lat and lon:
        folium.Marker([lat, lon], popup="Disaster Alert").add_to(disaster_map)
folium_static(disaster_map)

# Fetch and display GDACS alerts
if st.button("Fetch GDACS Alerts"):
    gdacs_alerts = fetch_gdacs_alerts()
    disaster_alerts = analyze_alerts(gdacs_alerts)
    
    if disaster_alerts:
        st.write("### 🚨 Emergency Alerts from GDACS:")
        for alert, location in disaster_alerts:
            loc_text = f" (Location: {location})" if location else " (Location: Unknown)"
            st.write(f"- {alert}{loc_text}")
    else:
        st.write("✅ No major disaster alerts from GDACS.")

# Fetch and display USGS earthquake alerts
if st.button("Fetch USGS Earthquake Data"):
    usgs_earthquakes = fetch_usgs_earthquakes()
    disaster_alerts = analyze_alerts(usgs_earthquakes)
    
    if disaster_alerts:
        st.write("### 🌍 Significant Earthquakes from USGS:")
        for alert, location in disaster_alerts:
            loc_text = f" (Location: {location})" if location else " (Location: Unknown)"
            st.write(f"- {alert}{loc_text}")
    else:
        st.write("✅ No significant earthquakes reported by USGS.")

# Display stored alerts
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
