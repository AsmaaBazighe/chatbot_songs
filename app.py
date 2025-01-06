import streamlit as st
import google.generativeai as genai
from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()

# Accéder aux variables
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
# Configure Gemini API
genai.configure(api_key=GOOGLE_API_KEY)

class Neo4jDatabase:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def get_songs_by_characteristics(self, artist=None, playlist_name=None):
        with self.driver.session() as session:
            query = """
            MATCH (t:Track)-[:PERFORMED_BY]->(a:Artist)
            MATCH (t)-[:PART_OF]->(al:Album)
            MATCH (t)-[:INCLUDED_IN]->(p:Playlist)
            WHERE 
                ($artist IS NULL OR a.name CONTAINS $artist)
                AND ($playlist_name IS NULL OR p.name CONTAINS $playlist_name)
            RETURN DISTINCT
                t.id as track_id,
                t.name as track_name,
                a.name as artist_name,
                t.popularity as popularity,
                t.tempo as tempo,
                t.energy as energy,
                t.danceability as danceability,
                t.duration_ms as duration,
                al.name as album_name,
                p.name as playlist_name,
                p.subgenre as subgenre
            ORDER BY t.popularity DESC
            LIMIT 15
            """
            result = session.run(query, artist=artist, playlist_name=playlist_name)
            return [dict(record) for record in result]

    def get_similar_songs(self, track_name):
        with self.driver.session() as session:
            query = """
            MATCH (t:Track {name: $track_name})-[:INCLUDED_IN]->(p:Playlist)
            MATCH (t)-[:PERFORMED_BY]->(artist:Artist)
            MATCH (p)<-[:INCLUDED_IN]-(similar:Track)-[:PERFORMED_BY]->(a:Artist)
            MATCH (similar)-[:PART_OF]->(al:Album)
            WHERE similar.name <> $track_name
            WITH similar, a, al, p,
                 abs(t.energy - similar.energy) + 
                 abs(t.danceability - similar.danceability) + 
                 abs(t.tempo - similar.tempo)/100 as similarity
            RETURN DISTINCT
                similar.id as track_id,
                similar.name as track_name,
                a.name as artist_name,
                similar.popularity as popularity,
                similar.energy as energy,
                similar.danceability as danceability,
                similar.tempo as tempo,
                al.name as album_name,
                p.subgenre as subgenre,
                similarity
            ORDER BY similarity ASC, similar.popularity DESC
            LIMIT 5
            """
            result = session.run(query, track_name=track_name)
            return [dict(record) for record in result]

class MusicRecommender:
    def __init__(self, neo4j_db):
        self.neo4j_db = neo4j_db
        self.model = genai.GenerativeModel('gemini-pro')

    def get_llm_recommendations(self, search_params):
        context = f"""
        As a music expert and DJ, I see you're looking for music with these search parameters:
        {search_params}

        Even though I don't have direct access to those specific songs in my database, I can suggest some recommendations based on these criteria.

        Please provide:
        1. 5 specific song recommendations that match these parameters
        2. Explanation of why these songs would be good matches
        3. The overall mood and style these recommendations follow
        4. When and how to best enjoy these songs
        5. Other artists or genres to explore based on these preferences

        Format your response in a conversational, engaging way, and be specific with song titles and artist names.
        """

        response = self.model.generate_content(context)
        return response.text

    def get_llm_similar_songs(self, track_name):
        context = f"""
        As a music expert, I see you're looking for songs similar to '{track_name}'.

        Even though I don't have this specific song in my database, I can recommend similar songs based on my musical knowledge.

        Please provide:
        1. 5 specific songs that would be similar to {track_name}
        2. Explanation of why these songs would be good matches
        3. The musical elements that connect these recommendations
        4. How these songs could create a cohesive playlist
        5. Other artists to explore based on this musical style

        Be specific about song titles and artists, and explain your recommendations in an engaging way.
        """

        response = self.model.generate_content(context)
        return response.text

    def analyze_music_characteristics(self, songs):
        # Existing method remains the same
        songs_info = []
        for song in songs:
            song_info = (
                f"Song: {song['track_name']}\n"
                f"Artist: {song['artist_name']}\n"
                f"Album: {song['album_name']}\n"
                f"Playlist: {song['playlist_name']}\n"
                f"Subgenre: {song['subgenre']}\n"
                f"Musical characteristics:\n"
                f"- Danceability: {song['danceability']}\n"
                f"- Energy: {song['energy']}\n"
                f"- Tempo: {song['tempo']}\n"
            )
            songs_info.append(song_info)

        context = f"""
        As a music expert and DJ, analyze these songs and their characteristics:

        {'\n\n'.join(songs_info)}

        Please provide:
        1. The main musical genres and styles represented in this selection
        2. The overall mood and energy level of these songs
        3. Recommendations for when and how to best enjoy these songs
        4. Any interesting patterns or commonalities in the musical characteristics
        5. Types of listeners who might especially enjoy this selection

        Format your response in a conversational, engaging way, like a knowledgeable friend sharing music insights.
        """

        response = self.model.generate_content(context)
        return response.text

    def analyze_similar_songs(self, original_track, similar_songs):
        # Existing method remains the same
        songs_info = []
        for song in similar_songs:
            song_info = (
                f"Song: {song['track_name']}\n"
                f"Artist: {song['artist_name']}\n"
                f"Subgenre: {song['subgenre']}\n"
                f"Characteristics:\n"
                f"- Danceability: {song['danceability']}\n"
                f"- Energy: {song['energy']}\n"
                f"- Tempo: {song['tempo']}\n"
            )
            songs_info.append(song_info)

        context = f"""
        As a music expert, analyze why these songs are similar to '{original_track}':

        {'\n\n'.join(songs_info)}

        Please explain:
        1. The musical elements that connect these songs
        2. How the energy and mood progress through these recommendations
        3. What makes each song unique while still being similar
        4. How these songs could create a cohesive playlist

        Be specific about the musical characteristics and provide insights in an engaging way.
        """

        response = self.model.generate_content(context)
        return response.text

def main():
    create_spotify_style_ui()
    
    st.title("🎵 AI-Powered Music Discovery")
    
    # Initialize connections
    neo4j_db = Neo4jDatabase(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    recommender = MusicRecommender(neo4j_db)
    
    # Sidebar inputs
    st.sidebar.header("Find Your Music")
    
    artist = st.sidebar.text_input("Search by Artist")
    playlist_search = st.sidebar.text_input("Search by Playlist Name")
    
    # Main content area
    tab1, tab2 = st.tabs(["🎵 Discover", "🔍 Similar Songs"])
    
    with tab1:
        if st.button("Get AI Music Analysis"):
            with st.spinner("Analyzing music..."):
                songs = neo4j_db.get_songs_by_characteristics(
                    artist=artist,
                    playlist_name=playlist_search
                )
                
                if songs:
                    analysis = recommender.analyze_music_characteristics(songs)
                    
                    st.markdown("### 🤖 AI Music Analysis")
                    st.markdown(analysis)
                    
                    st.markdown("### 📋 Discovered Songs")
                    for song in songs:
                        with st.container():
                            st.markdown(f"""
                            **{song['track_name']}**  
                            Artist: {song['artist_name']}  
                            Album: {song['album_name']}  
                            Playlist: {song['playlist_name']}  
                            Subgenre: {song['subgenre']}
                            """)
                            st.divider()
                else:
                    st.info("No exact matches found in the database, but here are some AI-powered recommendations!")
                    search_params = f"Artist: {artist if artist else 'Any'}, Playlist Style: {playlist_search if playlist_search else 'Any'}"
                    recommendations = recommender.get_llm_recommendations(search_params)
                    st.markdown("### 🤖 AI Music Recommendations")
                    st.markdown(recommendations)
    
    with tab2:
        track_name = st.text_input("Enter a song you love")
        if track_name and st.button("Find Similar Songs"):
            with st.spinner("Finding your next favorite songs..."):
                similar_songs = neo4j_db.get_similar_songs(track_name)
                if similar_songs:
                    analysis = recommender.analyze_similar_songs(track_name, similar_songs)
                    
                    st.markdown("### 🤖 Musical Connections Analysis")
                    st.markdown(analysis)
                    
                    st.markdown("### 📋 Similar Songs")
                    for song in similar_songs:
                        with st.container():
                            st.markdown(f"""
                            **{song['track_name']}**  
                            By {song['artist_name']}  
                            Subgenre: {song['subgenre']}
                            """)
                            st.divider()
                else:
                    st.info("Song not found in database, but here are some AI-powered recommendations!")
                    recommendations = recommender.get_llm_similar_songs(track_name)
                    st.markdown("### 🤖 AI Similar Song Recommendations")
                    st.markdown(recommendations)
# [Previous imports and class definitions remain the same until the UI part]

def create_spotify_style_ui():
    """Create a Spotify-like UI style for the Streamlit app"""
    st.set_page_config(
        page_title="Music Discovery AI",
        page_icon="🎵",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    st.markdown("""
        <style>
        .stApp {
            background-color: #121212;
            color: #ffffff;
        }
        .sidebar .sidebar-content {
            background-color: #000000;
        }
        .stButton>button {
            background-color: #1DB954;
            color: white;
            border-radius: 20px;
            padding: 10px 20px;
        }
        .stTextInput>div>div>input {
            background-color: #282828;
            color: white;
            border: none;
            border-radius: 4px;
        }
        .stSelectbox>div>div {
            background-color: #282828;
            color: white;
            border: none;
            border-radius: 4px;
        }
        .song-card {
            background-color: #282828;
            padding: 20px;
            border-radius: 8px;
            margin: 10px 0;
        }
        div[data-testid="stMarkdownContainer"] {
            color: #ffffff;
        }
        div[data-testid="stMarkdownContainer"] a {
            color: #1DB954;
        }
        .stTab {
            background-color: #282828;
            color: white !important;
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
            background-color: #121212;
        }
        .stTabs [data-baseweb="tab"] {
            background-color: #282828;
            border-radius: 4px;
            color: white;
            padding: 8px 16px;
        }
        .stTabs [data-baseweb="tab-highlight"] {
            background-color: #1DB954;
        }
        </style>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()