import streamlit as st
from fpdf import FPDF
import os
import tempfile

# Page setup
st.set_page_config(page_title="Lyrics & Sheet Music PDF", page_icon="🎵")
st.title("🎵 Lyrics + Blank Staves PDF")
st.write("Type or paste your lyrics → Get a clean PDF with blank staves above each line!")

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

# ─────────── PDF DRAWING FUNCTIONS ───────────
def draw_staff(pdf, clef="treble"):
    """Draw one blank staff with clef label"""
    line_y = pdf.get_y()
    
    # Staff lines — 5 horizontal lines
    for i in range(5):
        y_line = line_y + (i * 2.5)
        pdf.line(25, y_line, 190, y_line)
    
    # Clef label (text instead of symbol)
    pdf.set_font("Arial", "B", 10)
    if clef == "treble":
        pdf.text(12, line_y + 8, "𝄞 TREBLE")
    elif clef == "bass":
        pdf.text(12, line_y + 8, "𝄢 BASS")
    
    # Bar lines
    pdf.line(25, line_y, 25, line_y + 10)
    pdf.line(190, line_y, 190, line_y + 10)
    
    # Move cursor down past the staff
    pdf.set_y(line_y + 14)

def draw_double_staff(pdf):
    """Draw grand staff: treble + bass"""
    line_y = pdf.get_y()
    
    # Treble staff — 5 lines
    for i in range(5):
        y_line = line_y + (i * 2.5)
        pdf.line(25, y_line, 190, y_line)
    pdf.set_font("Arial", "B", 9)
    pdf.text(10, line_y + 8, "TREBLE")
    
    # Space between staves
    mid_gap = line_y + 14
    
    # Bass staff — 5 lines
    for i in range(5):
        y_line = mid_gap + (i * 2.5)
        pdf.line(25, y_line, 190, y_line)
    pdf.text(14, mid_gap + 8, "BASS")
    
    # Bar lines
    pdf.line(25, line_y, 25, mid_gap + 10)
    pdf.line(190, line_y, 190, mid_gap + 10)
    
    pdf.set_y(mid_gap + 14)

# ─────────── MAIN APP ───────────
st.subheader("📝 Enter Your Lyrics")
st.info("💡 Each line below will get its own blank music staff in the PDF.")

c1, c2, c3, c4 = st.columns(4)
with c1: do_split = st.button("📏 Split Lines")
with c2: do_verse = st.button("📖 Add Verses")
with c3: do_chorus = st.button("🎤 Add Chorus")
with c4: do_clean = st.button("🧹 Clean")

if "lyrics" not in st.session_state:
    st.session_state.lyrics = ""

if do_split and st.session_state.lyrics:
    st.session_state.lyrics = split_lines(st.session_state.lyrics)
if do_verse and st.session_state.lyrics:
    st.session_state.lyrics = add_verses(st.session_state.lyrics)
if do_chorus and st.session_state.lyrics:
    st.session_state.lyrics = add_chorus(st.session_state.lyrics)
if do_clean:
    st.session_state.lyrics = "\n".join(
        [l.strip() for l in st.session_state.lyrics.splitlines() if l.strip()]
    )

lyrics_out = st.text_area(
    "✏️ Type or paste your lyrics here:",
    value=st.session_state.lyrics,
    height=250,
    key="lyrics"
)

st.subheader("📄 PDF Options")
title = st.text_input("Song Title", value="My Song")
clef_choice = st.radio("Clef to display:", ["Treble Clef", "Bass Clef", "Grand Staff"], horizontal=True)

# ─────────── GENERATE PDF ───────────
if st.button("✨ Generate PDF", type="primary") and lyrics_out.strip():
    with st.spinner("Creating your PDF..."):
        
        class SheetPDF(FPDF):
            def header(self):
                self.set_font("Arial", "B", 18)
                self.cell(0, 12, title, ln=True, align="C")
                self.ln(3)
                self.set_font("Arial", "I", 10)
                self.set_text_color(100, 100, 100)
                self.cell(0, 6, "Write your notes on the staves below", ln=True, align="C")
                self.set_text_color(0, 0, 0)
                self.ln(5)
        
        pdf = SheetPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        
        # Choose drawing function
        if clef_choice == "Treble Clef":
            draw = lambda pdf: draw_staff(pdf, "treble")
        elif clef_choice == "Bass Clef":
            draw = lambda pdf: draw_staff(pdf, "bass")
        else:  # Grand Staff
            draw = draw_double_staff
        
        # Process each line
        for line in lyrics_out.splitlines():
            line = line.strip()
            if not line:
                pdf.ln(4)
                continue
            
            # Section header (Verse/Chorus)
            if line.startswith("[") and line.endswith("]"):
                pdf.ln(4)
                pdf.set_font("Arial", "B", 11)
                pdf.cell(0, 8, line, ln=True)
                pdf.set_font("Arial", size=12)
                continue
            
            # Blank staff
            draw(pdf)
            
            # Lyrics centered below staff
            pdf.set_x(25)
            pdf.cell(0, 7, line, ln=True, align="C")
            pdf.ln(2)
        
        # Save and download
        output_path = os.path.join(tempfile.gettempdir(), "blank_staves.pdf")
        pdf.output(output_path)
        
        with open(output_path, "rb") as f:
            st.download_button(
                "📥 Download Your PDF",
                f,
                file_name=f"{title.replace(' ', '_')}_sheet.pdf",
                mime="application/pdf"
            )
        
        os.unlink(output_path)
        st.success("✅ Done! Your PDF is ready — enjoy writing your music! 🎵")

elif not lyrics_out.strip():
    st.info("👆 Type some lyrics above, then click Generate PDF!")

st.divider()
st.info("💡 Tip: One line of lyrics = one staff. Use the buttons to add [Verse] and [Chorus] headers!")



Sent from my iPad

On 25 Oct 2026, at 21:53, Richard Eunson <richard.eunson1@gmail.com> wrote:

FPDFUnicodeEncodingException: Character "𝄞" at index 0 in text is outside the 
range of characters supported by the font used: "helveticaB". Please consider 
using a Unicode font.
