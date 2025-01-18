# Image OCR and Text-to-Speech (Balcon + Google Vision)

This repository provides a Python script that:

1. Iterates through all images in a given folder (recursively).
2. Uses **Google Cloud Vision** to perform OCR (Optical Character Recognition) on each image.
3. Saves the detected text into a `detected_texts.txt` file for manual review and editing.
4. Generates **audio (WAV)** from the corrected text using **Balcon** (ScanSoft Daniel_Full_22kHz voice).

---

## Table of Contents
- [Overview](#overview)
- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
- [Notes](#notes)
- [License](#license)

---

## Overview

This script automates a workflow to:
1. **Detect text** in images with Google Vision.
2. **Edit and confirm** recognized text in a `.txt` file.
3. **Generate** corresponding **audio files** (WAV) using Balcon’s Daniel voice.

It’s especially useful for bulk processing a folder full of images where you need both text and TTS output.

---

## Requirements

1. **Operating System**:
   - Windows is recommended (due to Balcon). 
   - If you replace Balcon with another TTS engine, you could potentially run it on other platforms.

2. **Python**:
   - Python 3.7+ (tested with Python 3.9+ recommended).

3. **Balcon**:
   - [Balcon](https://www.cross-plus-a.com/bconsole.htm) or an equivalent TTS tool installed at:
     ```
     C:\balcon\balcon.exe
     ```
   - Default voice name is `ScanSoft Daniel_Full_22kHz`. You may change this in the script.
     _You need to have ScanSoft Daniel_Full_22kHz installed for this to be used_, you can download it [here](https://www.mediafire.com/file/jtamvdgo53gt2o6/Daniel+22Khz+MLG+voice.exe/file) 

4. **Google Cloud Vision Credentials**:
   - A `keys.json` file with Vision API access.
   - Place `keys.json` in the same folder as the script (or adjust the path).

5. **Python Libraries**:
   - `click`
   - `tqdm`
   - `google-cloud-vision`
   - `Pillow`

6. **Notepad** (or any text editor):
   - Script defaults to opening `detected_texts.txt` with `notepad`.

---

## Installation

1. **Clone** or **download** this repository:
   ```bash
   git clone https://github.com/your-username/your-repo-name.git
   cd your-repo-name
   
2. **Install the required libraries** (ideally in a virtual environment):
   ```bash
   pip install -r requirements.txt
   
   - Where requirements.txt contains:
      click
      tqdm
      google-cloud-vision
      Pillow

3. **Add keys.json** (service account credentials) to the same folder.
   Make sure your Google Cloud project has **Vision API enabled**.

4. **Install Balcon** (Windows).
   By default, the script expects C:\balcon\balcon.exe. Adjust if needed.

## Usage

1. Open a terminal where the script is located.

2. Run the script with a path to the folder containing images:
   python meme_ocr_tts.py "C:\path\to\images\folder"

3. Review text:
   The script will scan all images, run OCR, and create a file detected_texts.txt in an output folder (e.g., output-1234abcd).
   It will then open Notepad for you to edit the recognized text.
   
5. Generate audio:
   After editing and saving detected_texts.txt, return to the terminal and press Enter.
   The script will generate .wav files in the audio subfolder.

## Notes
- If your Balcon installation or voice differs, update the generate_audio_balcon() function accordingly.
- Make sure keys.json is valid for Google Vision; if you encounter errors, check your API credentials and project settings.
- If Notepad doesn’t open automatically (e.g., on non-Windows systems), just open detected_texts.txt manually, edit, and close.

## License
You’re free to use or modify this script. However, Google Cloud Vision and Balcon have their own licenses and terms of service. Make sure to comply with them while using this script.


