#!/usr/bin/env python3
"""
Download YouTube transcripts for the provided video URLs.
"""

from youtube_transcript_api import YouTubeTranscriptApi
import re
from pathlib import Path

# List of video URLs
VIDEOS = [
    "https://www.youtube.com/watch?v=n8D3vEx7NAE",
    "https://www.youtube.com/watch?v=tWLZNCJISYU",
    "https://www.youtube.com/watch?v=CI-cVKuSD1s&list=PLda3VoSoc_TTp8Ng3C57spnNkOw3Hm_35",
    "https://www.youtube.com/watch?v=qkAVTikDAss&list=PLWI8H56cvVoKfe6Rj3aVUGA2NPGkSOJZ_",
    "https://www.youtube.com/watch?v=hqhWR0CxZHA",
    "https://www.youtube.com/watch?v=JlgZtOFMdfc",
    "https://www.youtube.com/watch?v=n872lbC-_BU&list=PLV5T4EgpiiGPdtBDJO_K4bhab3_xKnNJ5&index=4",
    "https://www.youtube.com/watch?v=DKTpEVeyZ_Q&list=PLV5T4EgpiiGPdtBDJO_K4bhab3_xKnNJ5&index=5",
    "https://www.youtube.com/watch?v=oTsEaKpzseE",
    "https://www.youtube.com/watch?v=y1E_y9AIqow&list=PLhqJJNjsQ7KGXNbfsUHJbb5-s2Tujtjt4",
    "https://www.youtube.com/watch?v=Bp3z-DQHO3k",
    "https://www.youtube.com/watch?v=3EMG2jGKkdw",
]


GAME_DEV_BENCH_VIDEOS = [
    "https://www.youtube.com/watch?v=9tu-Q-T--mY",
    "https://www.youtube.com/watch?v=PjPDNLBdstw",
    "https://www.youtube.com/watch?v=m4Bq_xX4eMo",
    "https://www.youtube.com/watch?v=8MdvvNUrD3w",
    "https://www.youtube.com/watch?v=caADorHNFwI",
    "https://www.youtube.com/watch?v=z9d8BU1o3Zw",
    "https://www.youtube.com/watch?v=yW15z7xqMnw",
    "https://www.youtube.com/watch?v=EeQHw3rRJgc",
    "https://www.youtube.com/watch?v=fXHJLNAY0NU",
    "https://www.youtube.com/watch?v=obEgPSnPqUs",
    "https://www.youtube.com/watch?v=Oh70eo4pep8",
    "https://www.youtube.com/watch?v=unknown",
    "https://www.youtube.com/watch?v=uQl0HC-2FNk",
    "https://www.youtube.com/watch?v=XLjCmdy8jdw",
    "https://www.youtube.com/watch?v=JnubpEa-Inw",
    "https://www.youtube.com/watch?v=qW3B7-kBbno",
    "https://www.youtube.com/watch?v=rXVGwlA6yB0",
    "https://www.youtube.com/watch?v=aEDDkGIfwDY",
    "https://www.youtube.com/watch?v=BUa-mKHEPUM",
    "https://www.youtube.com/watch?v=0MfTANzADHw",
    "https://www.youtube.com/watch?v=2dIZu8jyHmg",
    "https://www.youtube.com/watch?v=yKoGuBGZatY",
    "https://www.youtube.com/watch?v=CWjTTOUPYDY",
    "https://www.youtube.com/watch?v=mV1EWF3MEWc",
    "https://www.youtube.com/watch?v=X0e-n7dbff8",
    "https://www.youtube.com/watch?v=rQkswXvVIGw",
    "https://www.youtube.com/watch?v=-rKzpl1dMWs",
    "https://www.youtube.com/watch?v=ke5KpqcoiIU",
    "https://www.youtube.com/watch?v=qmwxsL9P05E",
    "https://www.youtube.com/watch?v=iHkFPcYTdxg",
    "https://www.youtube.com/watch?v=zvoQqhLeans",
    "https://www.youtube.com/watch?v=n3mtPVuuyWk",
    "https://www.youtube.com/watch?v=kkyaevee7pc",
    "https://www.youtube.com/watch?v=GtH6_EctXh4",
    "https://www.youtube.com/watch?v=GrDIg96Ames",
    "https://www.youtube.com/watch?v=X9_eteLoZLA",
    "https://www.youtube.com/watch?v=E401x98N6iA",
    "https://www.youtube.com/watch?v=dHbqsr-KjOg",
    "https://www.youtube.com/watch?v=bJxh23oAMLU",
    "https://www.youtube.com/watch?v=PwYxXq9P7E8",
    "https://www.youtube.com/watch?v=zfA0jLDRCZ4",
    "https://www.youtube.com/watch?v=Gj2WpkAw6sw",
    "https://www.youtube.com/watch?v=ztX4OV6Syn8",
    "https://www.youtube.com/watch?v=AUVsX-mtuNs",
    "https://www.youtube.com/watch?v=5ZTUDwpzxH0",
    "https://www.youtube.com/watch?v=GRtnoZAubBA",
    "https://www.youtube.com/watch?v=PQHExF-sbB4",
    "https://www.youtube.com/watch?v=v6lKjUHjH4c",
    "https://www.youtube.com/watch?v=M1ri3Zli2g0",
    "https://www.youtube.com/watch?v=Lrs-TEucq3w",
    "https://www.youtube.com/watch?v=e3Luf7dXSEY",
    "https://www.youtube.com/watch?v=Z9FHL_GnYJo",
    "https://www.youtube.com/watch?v=4Vdfg9KI4Xw"
]


def extract_video_id(url):
    """Extract video ID from YouTube URL."""
    pattern = r'(?:v=|/)([0-9A-Za-z_-]{11}).*'
    match = re.search(pattern, url)
    return match.group(1) if match else None


def format_timestamp(seconds):
    """Format seconds into MM:SS or HH:MM:SS."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes}:{secs:02d}"


def download_transcript(video_id):
    """Download transcript for a video ID."""
    try:
        # Get transcript using youtube-transcript-api
        transcript = YouTubeTranscriptApi.get_transcript(video_id)

        # Format with timestamps
        lines = []
        for entry in transcript:
            timestamp = format_timestamp(entry['start'])
            text = entry['text'].strip()
            lines.append(f"[{timestamp}] {text}")

        return "\n".join(lines)
    except Exception as e:
        return f"Error: {e}"


def main():
    output_dir = Path("transcripts")
    output_dir.mkdir(exist_ok=True)

    print(f"Downloading transcripts for {len(VIDEOS)} videos...")
    print(f"Output directory: {output_dir}\n")

    for i, url in enumerate(VIDEOS, 1):
        video_id = extract_video_id(url)
        if not video_id:
            print(f"[{i}/{len(VIDEOS)}] ✗ Could not extract video ID from: {url}")
            continue

        print(f"[{i}/{len(VIDEOS)}] Downloading {video_id}...", end=" ")

        transcript = download_transcript(video_id)

        # Save to file
        output_file = output_dir / f"{video_id}.txt"
        output_file.write_text(transcript)

        if transcript.startswith("Error:"):
            print(f"✗ {transcript}")
        else:
            print(f"✓ Saved to {output_file}")

    print(f"\n✓ Done! Transcripts saved to {output_dir}/")


if __name__ == "__main__":
    main()
