#!/usr/bin/env python3
"""Generate sample PDF resume fixture using PyMuPDF."""

import os
import fitz

def create_sample_pdf(output_path: str):
    doc = fitz.open()
    page = doc.new_page()

    text = """Jane Doe
Email: jane.doe@example.com | Phone: 555-0199 | San Francisco, CA

Professional Summary
Senior Software Engineer with 6+ years of experience building scalable backend services.

Work Experience
Acme Corp — Senior Backend Engineer (2021 – Present)
• Architected high-throughput microservices in Python and FastAPI.
• Reduced database latency by 35% through PostgreSQL index optimization.

Technical Skills
Languages: Python, SQL, JavaScript
Frameworks: FastAPI, Docker, AWS, PostgreSQL

Education
B.S. in Computer Science — UC Berkeley
"""
    rect = fitz.Rect(50, 50, 550, 750)
    page.insert_textbox(rect, text, fontsize=11, fontname="helv")
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc.save(output_path)
    doc.close()
    print(f"Sample PDF created at: {output_path}")

if __name__ == "__main__":
    create_sample_pdf("tests/fixtures/resumes/sample.pdf")
