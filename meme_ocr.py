import os
import io
import uuid
import asyncio
import subprocess
from pathlib import Path
import sys

import click
from tqdm import tqdm
from google.cloud import vision
from PIL import Image

# -------------------------------------------------------------------------
# 1. Load the Google Cloud Vision credential file.
#    Make sure keys.json has Vision API access.
# -------------------------------------------------------------------------
credential_path = Path(__file__).parent / "keys.json"
vision_client = vision.ImageAnnotatorClient.from_service_account_json(str(credential_path))

# -------------------------------------------------------------------------
# 2. This function calls Balcon to generate a WAV file using Daniel voice.
# -------------------------------------------------------------------------
def generate_audio_balcon(text: str, output_file: Path):
    """
    Generates a WAV file from `text` by calling Balcon in the background.
    We assume you have Balcon at C:\balcon\balcon.exe
    and your Daniel voice is named "ScanSoft Daniel_Full_22kHz" in Balcon's list.
    """
    balcon_exe = r"C:\balcon\balcon.exe"  # adjust if Balcon is elsewhere
    voice_name = "ScanSoft Daniel_Full_22kHz"

    # For big / multiline text or special characters, consider writing to a temp file and using "-f".
    cmd = [
        balcon_exe,
        "-n", voice_name,      # which voice (Daniel) to use
        "-t", text,            # text to speak
        "-w", str(output_file) # output WAV path
    ]

    # Hide console window on Windows
    CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
    
    try:
        subprocess.run(cmd, check=True, creationflags=CREATE_NO_WINDOW)
    except Exception as e:
        print(f"Error generating audio via Balcon for {output_file}: {e}")


def is_image(file_path: Path) -> bool:
    """Check if the file is an image using Pillow."""
    try:
        with Image.open(file_path):
            return True
    except IOError:
        return False


def detect_text(image_path: Path) -> str:
    """Detect text in the file using Google Vision API."""
    try:
        with open(image_path, "rb") as image_file:
            content = image_file.read()
        image = vision.Image(content=content)
        response = vision_client.text_detection(image=image)

        if response.error.message:
            raise Exception(f"Error with Google Vision API: {response.error.message}")

        texts = response.text_annotations
        if not texts:
            return ""

        # Combine multiline text into one line
        full_text = texts[0].description.strip().replace("\n", " ")
        return full_text
    except Exception as e:
        print(f"Error detecting text for {image_path}: {e}")
        return ""


async def process_images(folder_path: str) -> None:
    """
    Processes all images in the selected folder:
      1) Detect text from each image (Google Vision)
      2) Write them to 'detected_texts.txt' with blank lines separating entries
         (image_name:\ntext)
      3) Let user edit the file in Notepad
      4) Parse corrected text and generate audio with Balcon (Daniel voice)
    """
    # Create a unique output directory
    output_dir = Path(folder_path) / f"output-{uuid.uuid4().hex[:8]}"
    audio_dir = output_dir / "audio"
    os.makedirs(audio_dir, exist_ok=True)

    # Collect image files
    image_files = [
        Path(root) / file
        for root, _, files in os.walk(folder_path)
        for file in files
        if is_image(Path(root) / file)
    ]

    print(f"Total images found: {len(image_files)}\n")

    # Step 1: OCR text detection
    detected_texts = {}
    for idx, image_path in enumerate(image_files, start=1):
        print(f"Detecting text in image {idx}/{len(image_files)}: {image_path.name}")
        with tqdm(total=100, desc=f"Scanning {image_path.name}", leave=False) as pbar:
            text = detect_text(image_path)
            pbar.update(100)
        if text:
            detected_texts[image_path.stem] = text

    # Step 2: Save to detected_texts.txt
    txt_file = output_dir / "detected_texts.txt"
    with open(txt_file, "w", encoding="utf-8") as f:
        for image_name, text in detected_texts.items():
            f.write(f"{image_name}:\n{text}\n\n")

    print(f"\nDetected texts saved to: {txt_file}")
    print("Please review and edit the text file before proceeding.\n")
    print("Format:\n"
          "filename:\n"
          "Corrected text on one (or more) line(s)\n\n"
          "Then a blank line.\n")

    # Step 3: Open in Notepad
    try:
        subprocess.call(["notepad", str(txt_file)])
    except FileNotFoundError:
        print("Could not open Notepad automatically. Please manually open and edit the file:")
        print(txt_file)

    input("Press Enter after editing and closing the text file... ")

    # Step 4: Read corrected text
    corrected_texts = {}
    with open(txt_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if not line:
            i += 1
            continue
        # If line ends with ':', it's an image name
        if line.endswith(":"):
            image_name = line[:-1].strip()
            i += 1
            text_line = ""
            if i < len(lines):
                text_line = lines[i].rstrip()
                i += 1
            corrected_texts[image_name] = text_line
            # skip blank lines
            while i < len(lines) and not lines[i].strip():
                i += 1
        else:
            i += 1

    # Step 5: Generate audio with Balcon
    print("\nGenerating audio...")
    total_items = len(corrected_texts)
    for idx, (image_name, text) in enumerate(corrected_texts.items(), start=1):
        print(f"Audio {idx}/{total_items}: {image_name}.wav")
        audio_file = audio_dir / f"{image_name}.wav"
        with tqdm(total=100, desc=f"Audio for {image_name}", leave=False) as pbar:
            generate_audio_balcon(text, audio_file)
            pbar.update(100)

    print(f"\nDone! Outputs in {output_dir}")


@click.command()
@click.argument("folder_path", type=click.Path(exists=True, file_okay=False))
def main(folder_path):
    asyncio.run(process_images(folder_path))

if __name__ == "__main__":
    main()
