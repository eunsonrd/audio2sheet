
import streamlit as st
import whisper
from basic_pitch.inference import predict
from basic_pitch import ICASSP_2022_MODEL_PATH
from fpdf import FPDF
import os
import tempfile
import subprocess

# Page setup
st.set_page_config(page_title="Audio2Sheet", page_icon="🎵")
st.title("🎵 Audio2Sheet: Lyrics & Sheet Music PDF")
st.write("Upload an MP3 → Edit lyrics → Get sheet music + lyrics together!")

# Load AI model
@st.cache_resource
def load_whisper():
    return whisper.load_model("base")

model = load_whisper()

# ─────────── HELPER FUNCTIONS ───────────
def split_lines(text):
    import re
    lines = re.split(r'([.,;:!?])', text)
    result, current = [], ""
    for part in lines:
        if part in ".!,;:?":
            if current.strip():
                result.append((current + part).strip())
            current = ""
        else:
            current = part
    if current.strip():
        result.append(current.strip())
    return "\n".join(result)

def add_verses(text):
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    out = []
    for i, line in enumerate(lines, 1):
        out.append(f"[Verse {i}]")
        out.append(line)
    return "\n".join(out)

def add_chorus(text):
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    out = []
    for line in lines:
        out.append("[Chorus]")
        out.append(line)
    return "\n".join(out)

# Convert MIDI note number to LilyPond note name
def midi_to_lilypond(midi_num):
    note_names = ['c', 'cis', 'd', 'dis', 'e', 'f', 'fis', 'g', 'gis', 'a', 'ais', 'b']
    note_idx = midi_num % 12
    octave = (midi_num // 12) - 3
    lily_note = note_names[note_idx]
    if octave > 0:
        lily_note += "'" * octave
    elif octave < 0:
        lily_note += "," * abs(octave)
    return lily_note

# Generate LilyPond file with lyrics aligned under music
def create_lilypond_with_lyrics(note_events, lyrics_lines, output_path):
    # Filter valid notes
    valid_notes = []
    for start_time, end_time, pitch, conf, _ in note_events:
        if conf > 0.5 and 48 <= pitch <= 84:
            valid_notes.append((start_time, end_time, pitch))
   
    if not valid_notes:
        return None
   
    # Build note list with durations
    note_objs = []
    for start_time, end_time, pitch in valid_notes:
        duration = end_time - start_time
        if duration >= 0.9:
            dur = "1"
        elif duration >= 0.45:
            dur = "2"
        elif duration >= 0.22:
            dur = "4"
        elif duration >= 0.11:
            dur = "8"
        else:
            dur = "16"
        note_objs.append({
            'lily': midi_to_lilypond(pitch),
            'dur': dur,
            'time': start_time
        })
   
    # Prepare lyrics — one syllable/word per note position
    clean_lyrics = [l.strip() for l in lyrics_lines if l.strip() and not l.startswith("[")]
    words = []
    for line in clean_lyrics:
        words.extend(line.split())
   
    # Distribute words under notes
    lyrics_syllables = []
    for i, note in enumerate(note_objs):
        if i < len(words):
            lyrics_syllables.append(words[i].replace(' ', '~'))
        else:
            lyrics_syllables.append("")
   
    # Build LilyPond code with \lyricmode
    music_str = " ".join(f"{n['lily']}{n['dur']}" for n in note_objs)
    lyrics_str = " ".join(f'"{w}"' if w else "" for w in lyrics_syllables)
   
    lilypond_code = f"""\\version "2.22.0"
\\header {{
  title = ""
  composer = ""
}}
\\layout {{
  indent = 0\\mm
  line-width = 180\\mm
}}
\\relative c' {{
  \\clef treble
  \\key c \\major
  \\time 4/4
  {music_str}
  \\bar "|."
}}
\\addlyrics {{
  {lyrics_str}
}}
"""
    with open(output_path, 'w') as f:
        f.write(lilypond_code)
    return output_path

# Compile LilyPond to PDF
def lilypond_to_pdf(ly_path):
    pdf_path = ly_path.replace('.ly', '.pdf')
    try:
        result = subprocess.run(
            ['lilypond', '-o', os.path.dirname(ly_path), ly_path],
            capture_output=True,
            text=True,
            timeout=120
        )
        if os.path.exists(pdf_path):
            return pdf_path
        return None
    except Exception as e:
        st.error(f"LilyPond error: {e}")
        return None

# ─────────── MAIN APP ───────────
audio_file = st.file_uploader("Upload your MP3", type=["mp3"])

if audio_file:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
        tmp.write(audio_file.read())
        tmp_path = tmp.name

    st.audio(tmp_path)

    # Step 1: Transcribe lyrics
    with st.spinner("🔄 Transcribing lyrics..."):
        result = model.transcribe(tmp_path)
        raw_lyrics = result["text"].strip()

    # Step 2: Lyrics editor
    st.subheader("📝 Edit Your Lyrics")
    c1, c2, c3, c4 = st.columns(4)
    with c1: do_split = st.button("📏 Split Lines")
    with c2: do_verse = st.button("📖 Add Verses")
    with c3: do_chorus = st.button("🎤 Add Chorus")
    with c4: do_clean = st.button("🧹 Clean")

    if "lyrics" not in st.session_state:
        st.session_state.lyrics = raw_lyrics

    if do_split:
        st.session_state.lyrics = split_lines(st.session_state.lyrics)
    if do_verse:
        st.session_state.lyrics = add_verses(st.session_state.lyrics)
    if do_chorus:
        st.session_state.lyrics = add_chorus(st.session_state.lyrics)
    if do_clean:
        st.session_state.lyrics = "\n".join(
            [l.strip() for l in st.session_state.lyrics.splitlines() if l.strip()]
        )

    lyrics_out = st.text_area(
        "✏️ Edit your lyrics — words will appear under the notes:",
        value=st.session_state.lyrics,
        height=200,
        key="lyrics"
    )

    # Step 3: Extract melody
    st.subheader("🎼 Preparing Sheet Music")
    with st.spinner("🎵 Analyzing melody..."):
        _, _, note_events = predict(tmp_path)
       
        ly_path = os.path.join(tempfile.gettempdir(), "song.ly")
        lyrics_lines = lyrics_out.splitlines()
        ly_file = create_lilypond_with_lyrics(note_events, lyrics_lines, ly_path)
       
        sheet_pdf = None
        if ly_file:
            with st.spinner("🎼 Generating sheet music with lyrics..."):
                sheet_pdf = lilypond_to_pdf(ly_file)
                if sheet_pdf:
                    st.success("✅ Sheet music with lyrics ready!")
                else:
                    st.warning("⚠️ Could not generate music — check logs.")

    # Step 4: Download
    st.subheader("📄 Download Your PDF")
    title = st.text_input("Song Title", value="My Song")

    if st.button("✨ Generate PDF", type="primary"):
        if sheet_pdf and os.path.exists(sheet_pdf):
            with open(sheet_pdf, "rb") as f:
                st.download_button(
                    "📥 Download PDF — Music + Lyrics",
                    f,
                    file_name=f"{title.replace(' ', '_')}.pdf",
                    mime="application/pdf"
                )
            st.success("✅ Done! Your lyrics are under the notes in the sheet music 🎉")
        else:
            st.error("❌ Sheet music not available. Try a clearer recording or check logs.")

    # Cleanup
    os.unlink(tmp_path)
    if 'ly_path' in locals() and os.path.exists(ly_path):
        os.unlink(ly_path)
    if 'sheet_pdf' in locals() and sheet_pdf and os.path.exists(sheet_pdf):
        os.unlink(sheet_pdf)

st.divider()
st.info("💡 Words from your lyrics are placed under the notes. For best alignment, keep lyrics simple — one word per melody note!")

