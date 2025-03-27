import tweepy
import re
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium
from textblob import TextBlob
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
import joblib
import sqlite3
import geopy
from geopy.geocoders import Nominatim
from plyer import notification

# Twitter API credentials (Replace with your credentials)
consumer_key = "YOUR_CONSUMER_KEY"
consumer_secret = "YOUR_CONSUMER_SECRET"
access_token = "YOUR_ACCESS_TOKEN"
access_token_secret = "YOUR_ACCESS_SECRET"

# Authenticate with Twitter API
auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
auth.set_access_token(access_token, access_token_secret)
api = tweepy.API(auth)

# Geolocation setup
geolocator = Nominatim(user_agent="geoapi")

def extract_location(tweet):
    location = None
    words = tweet.split()
    for word in words:
        try:
            loc = geolocator.geocode(word)
            if loc:
                location = (loc.latitude, loc.longitude)
                break
        except:
            continue
    return location

# Function to clean tweets
def clean_text(text):
    text = re.sub(r'http\S+', '', text)  # Remove URLs
    text = re.sub(r'[^a-zA-Z\s]', '', text)  # Remove special characters
    text = text.lower()  # Convert to lowercase
    return text

# Fetch real-time disaster-related tweets
def fetch_tweets(keyword="earthquake OR flood OR wildfire", count=100):
    tweets = api.search_tweets(q=keyword, lang="en", count=count)
    tweet_list = [(clean_text(tweet.text), extract_location(tweet.text)) for tweet in tweets]
    return tweet_list

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
        tweet TEXT,
        latitude REAL,
        longitude REAL
    )
""")
conn.commit()

# Sentiment Analysis + ML Model Classification
def analyze_tweets(tweets):
    disaster_alerts = []
    model = joblib.load("disaster_model.pkl")
    
    for tweet, location in tweets:
        prediction = model.predict([tweet])[0]
        sentiment = TextBlob(tweet).sentiment.polarity
        if prediction == 1 or sentiment < -0.2:  # If model or sentiment indicates disaster
            disaster_alerts.append((tweet, location))
            cursor.execute("INSERT INTO alerts (tweet, latitude, longitude) VALUES (?, ?, ?)", (tweet, location[0] if location else None, location[1] if location else None))
            notification.notify(title="🚨 Disaster Alert!", message=tweet, timeout=5)
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
st_folium(disaster_map)


if st.button("Fetch Latest Disaster Tweets"):
    tweets = fetch_tweets()
    disaster_tweets = analyze_tweets(tweets)
    if disaster_tweets:
        st.write("### 🚨 Emergency Alerts from Social Media:")
        for tweet, location in disaster_tweets:
            loc_text = f" (Location: {location})" if location else " (Location: Unknown)"
            st.write(f"- {tweet}{loc_text}")
    else:
        st.write("✅ No major disaster-related alerts detected.")

# Display stored alerts
if st.button("View Past Alerts"):
    cursor.execute("SELECT tweet, latitude, longitude FROM alerts")
    past_alerts = cursor.fetchall()
    if past_alerts:
        st.write("### 🕒 Historical Disaster Alerts:")
        for alert in past_alerts:
            loc_text = f" (Location: {alert[1]}, {alert[2]})" if alert[1] and alert[2] else " (Location: Unknown)"
            st.write(f"- {alert[0]}{loc_text}")
    else:
        st.write("📜 No past alerts recorded.")
