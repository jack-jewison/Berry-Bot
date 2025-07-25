import os
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
from exif import Image as ExifImage
from geopy.distance import geodesic
import piexif
import piexif.helper

def dms_to_decimal(dms, ref):
    degrees, minutes, seconds = dms
    decimal = degrees + minutes / 60 + seconds / 3600
    if ref in ['S', 'W']:
        decimal = -decimal
    return decimal

def get_image_gps(image_path):
    try:
        with open(image_path, 'rb') as img_file:
            img = ExifImage(img_file)
            if not img.has_exif:
                return None
            if not hasattr(img, 'gps_latitude') or not hasattr(img, 'gps_longitude'):
                return None
            lat = dms_to_decimal(img.gps_latitude, img.gps_latitude_ref)
            lon = dms_to_decimal(img.gps_longitude, img.gps_longitude_ref)
            return (lat, lon)
    except Exception as e:
        print(f"Error reading EXIF from {image_path}: {e}")
        return None

def find_closest_label(lat, lon, label_df, threshold_meters=10):
    point = (lat, lon)
    label_df['distance'] = label_df.apply(
        lambda row: geodesic(point, (row['latitude'], row['longitude'])).meters, axis=1)
    closest = label_df.loc[label_df['distance'].idxmin()]
    if closest['distance'] <= threshold_meters:
        return closest['label']
    return None

def label_image(image_path, label, output_folder):
    try:
        img = Image.open(image_path).convert("RGB")
        draw = ImageDraw.Draw(img)
        width, height = img.size

        # Font size = 5% of height
        font_size = int(height * 0.05)

        # Load TrueType font
        try:
            font_path = "arial.ttf"
            if not os.path.exists(font_path):
                font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            font = ImageFont.truetype(font_path, font_size)
        except Exception as e:
            print(f"Falling back to default font. Text may be small. Error: {e}")
            font = ImageFont.load_default()

        # Draw label
        text = str(label)
        bbox = font.getbbox(text)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        padding = 6
        draw.rectangle(
            [10 - padding, 10 - padding, 10 + text_width + padding, 10 + text_height + padding],
            fill="black"
        )
        draw.text((10, 10), text, fill="white", font=font)

        # Save image with visual label
        output_path = os.path.join(output_folder, os.path.basename(image_path))
        img.save(output_path, "JPEG", quality=95)

        # Write label into EXIF metadata
        exif_dict = piexif.load(output_path)
        user_comment = f"{label}"
        exif_dict["0th"][piexif.ImageIFD.ImageDescription] = user_comment.encode("utf-8")
        exif_dict["Exif"][piexif.ExifIFD.UserComment] = piexif.helper.UserComment.dump(user_comment, encoding="unicode")
        exif_bytes = piexif.dump(exif_dict)
        piexif.insert(exif_bytes, output_path)

    except Exception as e:
        print(f"Error labeling image {image_path}: {e}")

def process_images(image_folder, label_csv, output_folder):
    os.makedirs(output_folder, exist_ok=True)
    label_df = pd.read_csv(label_csv, dtype={"label": str})
    for filename in os.listdir(image_folder):
        if filename.lower().endswith(('.jpg', '.jpeg')):
            image_path = os.path.join(image_folder, filename)
            gps = get_image_gps(image_path)
            if gps:
                label = find_closest_label(gps[0], gps[1], label_df)
                if isinstance(label, str):
                    label_image(image_path, label, output_folder)
                    print(f"Labeled {filename} with '{label}'")
                else:
                    print(f"No valid string label found for {filename} (got: {label})")
            else:
                print(f"No GPS data found for {filename}")

# 🚀 Run this script directly
if __name__ == "__main__":
    process_images(
        image_folder="RGBMay15",        # Folder with input .jpg images
        label_csv="gps_labels.csv",     # CSV with 'latitude', 'longitude', 'label'
        output_folder="labeled_images"  # Output destination
    )
