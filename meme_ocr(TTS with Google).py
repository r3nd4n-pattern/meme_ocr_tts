import os
import io
import uuid
import asyncio
import subprocess
from pathlib import Path

from tqdm import tqdm
from google.cloud import vision
from google.cloud import texttospeech
from PIL import Image
import click

# -------------------------------------------------------------------------
# 1. Load the same credential file you used for Vision (keys.json)
#    Make sure you also enabled the "Cloud Text-to-Speech" API in Google Cloud.
# -------------------------------------------------------------------------
credential_path = Path(__file__).parent / "keys.json"

# Initialize Google Vision client
vision_client = vision.ImageAnnotatorClient.from_service_account_json(str(credential_path))

# Initialize Google Cloud TTS client
tts_client = texttospeech.TextToSpeechClient.from_service_account_json(str(credential_path))


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

        # Vision can return multiline text; combine into one line by replacing newlines with spaces
        full_text = texts[0].description.strip().replace("\n", " ")
        return full_text
    except Exception as e:
        print(f"Error detecting text for {image_path}: {e}")
        return ""


def generate_audio_cloud(text: str, output_file: Path) -> None:
    """
    Converts text to audio using Google Cloud TTS and saves it as a WAV file.
    """
    try:
        # Configure the text input
        synthesis_input = texttospeech.SynthesisInput(text=text)

        # Choose a British English voice (Wavenet). You can change the name to any available en-GB voice.
        voice_params = texttospeech.VoiceSelectionParams(
            language_code="en-GB",
            name="en-GB-Wavenet-D",  # Try en-GB-Standard-A, en-GB-Wavenet-B, etc. if you like
        )

        # Configure the audio output (LINEAR16 = WAV)
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.LINEAR16
        )

        # Call the Text-to-Speech API
        response = tts_client.synthesize_speech(
            input=synthesis_input,
            voice=voice_params,
            audio_config=audio_config
        )

        # Write the binary audio content to file
        with open(output_file, "wb") as out:
            out.write(response.audio_content)

    except Exception as e:
        print(f"Error generating cloud-based audio for {output_file}: {e}")


async def process_images(folder_path: str) -> None:
    """
    Processes all images in the selected folder.
    Steps:
      1) Detect text from images (single-line).
      2) Write them to 'detected_texts.txt' with a blank line separating each image block:
         image_name:
         text here

      3) Let the user edit the file in a text editor.
      4) Parse it back and generate one .wav per image using Google Cloud TTS.
    """

    # Create an output directory with a unique name
    output_dir = Path(folder_path) / f"output-{uuid.uuid4().hex[:8]}"
    audio_dir = output_dir / "audio"
    os.makedirs(audio_dir, exist_ok=True)

    # Collect all image files from the folder (recursively)
    image_files = [
        Path(root) / file
        for root, _, files in os.walk(folder_path)
        for file in files
        if is_image(Path(root) / file)
    ]

    print(f"Total images found: {len(image_files)}\n")

    # Step 1: Detect text from each image and store results in a dict
    detected_texts = {}
    for idx, image_path in enumerate(image_files, start=1):
        print(f"Detecting text in image {idx}/{len(image_files)}: {image_path.name}")
        with tqdm(total=100, desc=f"Scanning {image_path.name}", leave=False) as pbar:
            text = detect_text(image_path)
            pbar.update(100)

        if text:
            detected_texts[image_path.stem] = text

    # Step 2: Save all detected texts to a single file for user review/correction
    txt_file = output_dir / "detected_texts.txt"

    with open(txt_file, "w", encoding="utf-8") as f:
        for image_name, text in detected_texts.items():
            # Format each entry like:
            # image_meme:
            # text text text
            #
            f.write(f"{image_name}:\n{text}\n\n")

    print(f"\nDetected texts saved to: {txt_file}")
    print("Please review and edit the text file before proceeding.\n")
    print("Format:\n"
          "filename:\n"
          "Corrected text in single line (or multiple lines if you prefer)\n\n"
          "Then a blank line.\n")

    # Step 3: Open the text file in the default editor (Windows: notepad)
    try:
        subprocess.call(["notepad", str(txt_file)])
    except FileNotFoundError:
        # Fallback if 'notepad' isn't available on the system
        print("Could not open notepad automatically. Please manually open and edit the file:")
        print(txt_file)

    # Wait for user to save/close the file
    input("Press Enter after you have finished editing and closed the text file... ")

    # Step 4: Read the corrected text file back
    corrected_texts = {}
    with open(txt_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if not line:
            i += 1
            continue

        # A line that ends with ":" indicates a new image block
        if line.endswith(":"):
            image_name = line[:-1].strip()  # remove the colon
            i += 1
            # Next line is the text (or empty if there's nothing)
            if i < len(lines):
                text_line = lines[i].rstrip()
                i += 1
            else:
                text_line = ""
            corrected_texts[image_name] = text_line

            # skip any blank lines
            while i < len(lines) and not lines[i].strip():
                i += 1
        else:
            i += 1

    # Step 5: Generate audio from the corrected texts (one .wav per image)
    print("\nGenerating audio for corrected texts...")
    total_items = len(corrected_texts)
    for idx, (image_name, text) in enumerate(corrected_texts.items(), start=1):
        print(f"Generating audio {idx}/{total_items}: {image_name}.wav")
        audio_file = audio_dir / f"{image_name}.wav"
        with tqdm(total=100, desc=f"Audio for {image_name}", leave=False) as pbar:
            generate_audio_cloud(text, audio_file)
            pbar.update(100)

    print(f"\nProcessing complete! Outputs saved to: {output_dir}")


@click.command()
@click.argument("folder_path", type=click.Path(exists=True, file_okay=False))
def main(folder_path):
    """Tool for extracting text from images, allowing corrections, and converting text to speech (Cloud-based)."""
    asyncio.run(process_images(folder_path))


if __name__ == "__main__":
    main()