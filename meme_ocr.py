import os
import io
import uuid
import asyncio
import subprocess
from pathlib import Path
import sys
import re

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
#    It returns None if successful, or an error message if something fails.
# -------------------------------------------------------------------------
def generate_audio_balcon(text: str, output_file: Path):
    """
    Generates a WAV file from `text` by calling Balcon in the background.
    We assume you have Balcon at C:\balcon\balcon.exe
    and your Daniel voice is named "ScanSoft Daniel_Full_22kHz" in Balcon's list.
    Returns:
      None if successful, otherwise an error message.
    """
    balcon_exe = r"C:\balcon\balcon.exe"  # adjust if Balcon is elsewhere
    voice_name = "ScanSoft Daniel_Full_22kHz"

    cmd = [
        balcon_exe,
        "-n", voice_name,
        "-t", text,
        "-w", str(output_file)
    ]

    CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

    try:
        result = subprocess.run(cmd, check=True, creationflags=CREATE_NO_WINDOW,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return None  # success
    except subprocess.CalledProcessError as e:
        return e.stderr.decode() if e.stderr else str(e)
    except Exception as e:
        return str(e)


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

        full_text = texts[0].description.strip().replace("\n", " ")
        return full_text
    except Exception as e:
        print(f"Error detecting text for {image_path}: {e}")
        return ""


def quality_control(corrected_texts: dict, audio_dir: Path, max_attempts: int = 3):
    """
    Performs quality control by scanning the audio directory to confirm that
    all expected audio files (one per corrected_text entry) exist.
    A progress bar is shown during the scanning. If files are missing,
    the function attempts to regenerate them up to max_attempts.
    If after max_attempts some files are still missing, it prints the reason
    why each could not be generated.
    """
    expected_names = set(corrected_texts.keys())
    reasons = {}  # to record error messages for each image

    for attempt in range(1, max_attempts + 1):
        print(f"\nQuality Control: Scanning audio files (Attempt {attempt}/{max_attempts})...")
        # Check progress: iterate through expected image names with a progress bar.
        missing = set()
        for image_name in tqdm(expected_names, desc="Scanning", unit="file"):
            audio_file = audio_dir / f"{image_name}.wav"
            if not audio_file.exists():
                missing.add(image_name)

        if not missing:
            print("Quality Control: All expected audio files have been generated.")
            return

        print(f"\n{len(missing)} audio file(s) missing. Attempting to regenerate missing files...")
        # Attempt to re-generate missing audio files.
        for image_name in missing:
            text = corrected_texts.get(image_name)
            audio_file = audio_dir / f"{image_name}.wav"
            err = generate_audio_balcon(text, audio_file)
            if err:
                reasons[image_name] = err
        # After regeneration, the loop will scan again.
    
    # After max_attempts, final scan
    final_missing = expected_names - {f.stem for f in audio_dir.glob("*.wav")}
    if final_missing:
        print("\nFinal Report: The following audio files could not be generated after"
              f" {max_attempts} attempts:")
        for image_name in final_missing:
            reason = reasons.get(image_name, "No error message available.")
            print(f"  {image_name}.wav  -->  Reason: {reason}")


async def process_images(folder_path: str) -> None:
    """
    Processes images:
      1) Detect text (using Google Vision).
      2) Save them in 'detected_texts.txt' (one block per image).
      3) Let the user edit the file in Notepad.
      4) Parse the corrected text (supporting multiline blocks).
      5) Generate audio with Balcon.
      6) Run quality control to verify and re-generate any missing audio.
    """
    output_dir = Path(folder_path) / f"output-{uuid.uuid4().hex[:8]}"
    audio_dir = output_dir / "audio"
    os.makedirs(audio_dir, exist_ok=True)

    # Collect image files.
    image_files = [
        Path(root) / file
        for root, _, files in os.walk(folder_path)
        for file in files
        if is_image(Path(root) / file)
    ]

    print(f"Total images found: {len(image_files)}\n")

    # Step 1: OCR text detection.
    detected_texts = {}
    for idx, image_path in enumerate(image_files, start=1):
        print(f"Detecting text in image {idx}/{len(image_files)}: {image_path.name}")
        with tqdm(total=100, desc=f"Scanning {image_path.name}", leave=False) as pbar:
            text = detect_text(image_path)
            pbar.update(100)
        if text:
            detected_texts[image_path.stem] = text

    # Step 2: Save detected texts.
    txt_file = output_dir / "detected_texts.txt"
    with open(txt_file, "w", encoding="utf-8") as f:
        for image_name, text in detected_texts.items():
            f.write(f"{image_name}:\n{text}\n\n")

    print(f"\nDetected texts saved to: {txt_file}")
    print("Please review and edit the text file before proceeding.\n")
    print("Format each block as follows (with a blank line between blocks):\n")
    print("  image_name:\n  Text line 1\n  Text line 2 (optional)\n  ...\n")

    # Step 3: Open in Notepad.
    try:
        subprocess.call(["notepad", str(txt_file)])
    except FileNotFoundError:
        print("Could not open Notepad automatically. Please manually open and edit the file:")
        print(txt_file)

    input("Press Enter after editing and closing the text file... ")

    # Step 4: Parse the corrected text.
    corrected_texts = {}
    with open(txt_file, "r", encoding="utf-8") as f:
        content = f.read()

    blocks = re.split(r"\n\s*\n", content)
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        lines = block.splitlines()
        header = lines[0].strip()
        if not header.endswith(":"):
            print(f"Warning: block header does not end with ':' -> {header}")
            continue
        image_name = header[:-1].strip()
        text = "\n".join(line.strip() for line in lines[1:] if line.strip())
        if not text:
            print(f"Warning: No text found for image {image_name}.")
        corrected_texts[image_name] = text

    # Step 5: Generate audio with Balcon.
    print("\nGenerating audio...")
    total_items = len(corrected_texts)
    for idx, (image_name, text) in enumerate(corrected_texts.items(), start=1):
        print(f"Audio {idx}/{total_items}: {image_name}.wav")
        audio_file = audio_dir / f"{image_name}.wav"
        with tqdm(total=100, desc=f"Audio for {image_name}", leave=False) as pbar:
            err = generate_audio_balcon(text, audio_file)
            pbar.update(100)
            if err:
                print(f"Warning: Error generating audio for {image_name}: {err}")

    # Step 6: Quality control.
    quality_control(corrected_texts, audio_dir, max_attempts=3)

    print(f"\nDone! Outputs in {output_dir}")


@click.command()
@click.argument("folder_path", type=click.Path(exists=True, file_okay=False))
def main(folder_path):
    asyncio.run(process_images(folder_path))


if __name__ == "__main__":
    main()
