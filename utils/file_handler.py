 
import os
import json
import pandas as pd
from utils.logger import get_logger
from config.settings import MASTERDATA_DIR,OUTPUT_FOLDER
import zipfile
from datetime import datetime
import shutil
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

logger = get_logger(__name__)

# adjust path as per project


# ============================================================
# 📂 File Loader
# ============================================================
def load_symbols_from_csv(folder_path: str):
    """
    Read ALL CSV files from given folder and return UNIQUE list of trading symbols (-EQ suffix).
    
    Rules:
      - For MyScreen_ files:
          * Resolve 'Name' column → map via symbolnamemaster.json → TradingSymbol-EQ
      - For ChartInk_ files:
          * Take 'Symbol' column directly → append -EQ
      - Skip unsupported files

    Args:
        folder_path (str): Directory path containing input CSVs.

    Returns:
        list[str]: Unique trading symbols with -EQ suffix.
    """
    if not os.path.exists(folder_path):
        raise FileNotFoundError(f"Input folder not found: {folder_path}")

    files = [f for f in os.listdir(folder_path) if f.endswith(".csv")]
    if not files:
        raise FileNotFoundError(f"No CSV files found in {folder_path}")

    logger.info(f"Found {len(files)} CSV file(s) to process in {folder_path}")

    # --- Load masterdata once for MyScreen files ---
    master_file = os.path.join(MASTERDATA_DIR, "symbolnamemaster.json")
    if not os.path.exists(master_file):
        raise FileNotFoundError("symbolnamemaster.json missing in masterdata folder")

    with open(master_file, "r") as f:
        master_data = json.load(f)

    all_symbols = set()  # ✅ ensures uniqueness

    for file in files:
        file_path = os.path.join(folder_path, file)

        logger.info(f"Processing file: {file_path}")
            
        if not os.path.exists(file_path):
            logger.error(f"Invalid file path: {file_path}")
        try:
            

            df = pd.read_csv(file_path)

            # --- MyScreen_ files ---
            if file.lower().startswith("myscreen_"):
                if "Name" not in df.columns:
                    raise ValueError(f"MyScreen file {file} missing 'Name' column")
                raw_names = df["Name"].dropna().unique().tolist()
                logger.info(f"Extracted {len(raw_names)} raw names from MyScreen file {file}")

                for name in raw_names:
                    match = next(
                        (item for item in master_data if item["SEM_CUSTOM_SYMBOL"] == name),
                        None
                    )
                    if match:
                        all_symbols.add(f"{match['SEM_TRADING_SYMBOL']}-EQ")

            # --- ChartInk_ files ---
            elif file.lower().startswith("chartink_"):
                if "Symbol" not in df.columns:
                    raise ValueError(f"ChartINK file {file} missing 'Symbol' column")
                raw_symbols = df["Symbol"].dropna().unique().tolist()
                logger.info(f"Extracted {len(raw_symbols)} symbols from ChartINK file {file}")
                for sym in raw_symbols:
                    all_symbols.add(f"{sym}-EQ")

            # --- Unsupported files ---
            else:
                logger.warning(f"Skipping unsupported file: {file}")
                continue

        except Exception as e:
            logger.error(f"Error processing file {file}: {e}")

    logger.info(f" Total unique symbols collected: {len(all_symbols)}")
    return list(all_symbols)


# ============================================================
# 📂 Generic File Helpers
# ============================================================
def save_text(file_path: str, content):
    """
    Save text (string or list of strings) into a file.
    Creates directories if missing.
    """
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        if isinstance(content, (list, tuple)):
            f.write("\n".join(str(line) for line in content))
        else:
            f.write(str(content))
    logger.info(f"Saved text to {file_path}")


def save_csv(df: pd.DataFrame, file_path: str):
    """
    Save DataFrame to CSV.
    Creates directories if missing.
    """
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    df.to_csv(file_path, index=False)
    logger.info(f"Saved CSV to {file_path} (rows={len(df)})")


def create_output_zip():
    """Create a zip file from all files in OUTPUT_DIR."""
    zip_filename = f"tradefinder_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    zip_path = os.path.join(OUTPUT_FOLDER, zip_filename)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(OUTPUT_FOLDER):
            for file in files:
                if file.endswith(".zip"):  # avoid zipping old zips
                    continue
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, OUTPUT_FOLDER)
                zipf.write(file_path, arcname)
    return zip_path

def cleanup_old_outputs(days_to_keep=1):
    """
    Remove dated folders in OUTPUT_DIR older than `days_to_keep`.
    """
    now = datetime.now()
    for folder in os.listdir(OUTPUT_FOLDER):
        folder_path = os.path.join(OUTPUT_FOLDER, folder)
        if os.path.isdir(folder_path):
            try:
                # assume folder name like 20250920 or similar
                folder_date = datetime.strptime(folder, "%Y%m%d")
                age = (now - folder_date).days
                if age > days_to_keep:
                    shutil.rmtree(folder_path)
                    print(f" Deleted old folder: {folder_path}")
            except ValueError:
                # skip folders not matching date format
                continue

# ============================================================
# 📄 PDF File Saver
# ============================================================

def save_pdf(file_path: str, content, title="Report"):
    """
    Save formatted text content to a PDF file using ReportLab.
    Preserves structure for better mobile readability.

    Args:
        file_path (str): Full output PDF path.
        content (str | list): Report text or list of lines.
        title (str): Optional title for the PDF.
    """
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    styles = getSampleStyleSheet()
    normal = styles["Normal"]
    heading = styles["Heading1"]

    doc = SimpleDocTemplate(file_path, pagesize=A4)
    story = []

    # Title
    story.append(Paragraph(title, heading))
    story.append(Spacer(1, 12))

    # Convert to lines
    if isinstance(content, (list, tuple)):
        lines = [str(line) for line in content]
    else:
        lines = str(content).split("\n")

    # Add each line
    for line in lines:
        story.append(Paragraph(line.strip(), normal))
        story.append(Spacer(1, 4))

    doc.build(story)
    logger.info(f"Saved PDF to {file_path}")

