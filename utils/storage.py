"""
NeuroLearn 2.0 — Cloud & Local Storage Helper
Supports Cloudinary uploads when configured, with seamless fallback to local disk storage.
"""

import os
import requests


def upload_image(file_storage, filename, folder="neurolearn"):
    """
    Upload an image file to Cloudinary if credentials are configured.
    Returns: URL of the uploaded image, or None if Cloudinary is not configured/fails.
    """
    cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME")
    upload_preset = os.getenv("CLOUDINARY_UPLOAD_PRESET")

    if not cloud_name or not upload_preset:
        return None

    try:
        file_storage.seek(0)
        files = {
            "file": (filename, file_storage.read(), file_storage.content_type)
        }
        data = {
            "upload_preset": upload_preset,
            "folder": folder
        }
        res = requests.post(
            f"https://api.cloudinary.com/v1_1/{cloud_name}/image/upload",
            data=data,
            files=files,
            timeout=15
        )
        if res.status_code == 200:
            result = res.json()
            url = result.get("secure_url") or result.get("url")
            print(f"☁️ [CLOUDINARY] Uploaded successfully: {url}")
            return url
        else:
            print(f"⚠️ [CLOUDINARY] Upload failed with status {res.status_code}: {res.text[:100]}")
    except Exception as e:
        print(f"⚠️ [CLOUDINARY] Error: {e}")
    finally:
        file_storage.seek(0)

    return None
