CREATE TABLE playlists (
    id          VARCHAR     PRIMARY KEY,        -- Spotify playlist ID
    name        VARCHAR     NOT NULL,
    owner_id    VARCHAR     NOT NULL,
    is_active   BOOLEAN     DEFAULT TRUE,
    added_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE tracked_tracks (
    track_id    VARCHAR     NOT NULL,
    playlist_id VARCHAR     NOT NULL REFERENCES playlists(id),
    track_name  VARCHAR     NOT NULL,
    artist_names TEXT[]     NOT NULL,
    album_name  VARCHAR,
    spotify_url VARCHAR,
    added_at    TIMESTAMPTZ,                    -- When the track was added to the playlist (Spotify data)
    detected_at TIMESTAMPTZ DEFAULT NOW(),      -- When we first detected this track
    analysis    TEXT,                            -- Groq emotional analysis (stored for weekly mood reports)
    PRIMARY KEY (track_id, playlist_id)
);
