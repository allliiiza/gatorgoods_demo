import flask
import secrets
from pathlib import Path

# local imports
import crud


PROTECTED_IMAGE_DIR = Path(__file__).resolve().parent / "protected" / "listing-images"
PROFILE_IMAGE_DIR = Path(__file__).resolve().parent / "protected" / "profile-images"
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


def ensure_protected_image_dir():
    """Create the protected listing image directory if it does not already exist."""
    PROTECTED_IMAGE_DIR.mkdir(parents=True, exist_ok=True)


def ensure_profile_image_dir():
    """Create the protected profile image directory if it does not already exist."""
    PROFILE_IMAGE_DIR.mkdir(parents=True, exist_ok=True)


def get_upload_files() -> list:
    """Return all uploaded listing image files from supported request file field names."""
    files = []
    for field_name in ("image", "images", "listing_image"):
        files.extend(flask.request.files.getlist(field_name))
    return [uploaded_file for uploaded_file in files if uploaded_file and uploaded_file.filename]


def get_allowed_image_suffix(filename: str) -> str:
    """Return a valid lowercase image file suffix, or abort if the file type is unsupported."""
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_IMAGE_EXTENSIONS:
        flask.abort(415, "Only jpg, jpeg, png, gif, and webp image uploads are supported.")
    return suffix


def verify_image_upload(uploaded_file):
    """Abort if the uploaded file does not have an image MIME type."""
    mimetype = uploaded_file.mimetype or ""
    if not mimetype.startswith("image/"):
        flask.abort(415, "Only image uploads are supported.")


def generate_unique_image_name(suffix: str) -> str:
    """Generate a unique listing image filename with the given suffix."""
    ensure_protected_image_dir()
    while True:
        image_name = f"{secrets.token_hex(8)}{suffix}"
        if not (PROTECTED_IMAGE_DIR / image_name).exists():
            return image_name

def generate_unique_profile_image_name(suffix: str) -> str:
    """Generate a unique profile image filename with the given suffix."""
    ensure_profile_image_dir()
    while True:
        image_name = f"{secrets.token_hex(8)}{suffix}"
        if not (PROFILE_IMAGE_DIR / image_name).exists():
            return image_name


def upload_listing_images(db, current_user, listing_id):
    """Validate, save, register, and return uploaded images for a listing owned by the current user."""
    db_listing = crud.get_listing_by_id(db, listing_id)
    if db_listing is None:
        flask.abort(404, "Listing not found.")

    if db_listing.seller_id != current_user.id:
        flask.abort(403, "You do not have permission to upload images for this listing.")

    upload_files = get_upload_files()
    if len(upload_files) == 0:
        flask.abort(400, "Attach at least one image file using image, images, or listing_image.")

    saved_images = []
    for uploaded_file in upload_files:
        verify_image_upload(uploaded_file)
        suffix = get_allowed_image_suffix(uploaded_file.filename)
        image_name = generate_unique_image_name(suffix)
        output_path = PROTECTED_IMAGE_DIR / image_name
        uploaded_file.save(output_path)

        image_path = flask.url_for("serve_listing_image", image_name=image_name)
        try:
            db_image = crud.create_listing_image(db, image_path=image_path, listing_id=listing_id)
        except Exception:
            if output_path.exists():
                output_path.unlink()
            raise

        if db_image is None:
            if output_path.exists():
                output_path.unlink()
            flask.abort(404, "Listing not found.")

        saved_images.append({
            "id": db_image.id,
            "listing_id": db_image.listing_id,
            "image_path": db_image.image_path,
            "display_order": db_image.display_order,
        })

    return saved_images


def upload_profile_image(current_user):
    """Upload and return a new profile image path, or keep the current profile image if none was uploaded."""
    uploaded_file = flask.request.files.get("profile_image")
    if uploaded_file is None or not uploaded_file.filename:
        return current_user.profile_image_path

    verify_image_upload(uploaded_file)
    suffix = get_allowed_image_suffix(uploaded_file.filename)
    image_name = generate_unique_profile_image_name(suffix)
    output_path = PROFILE_IMAGE_DIR / image_name
    uploaded_file.save(output_path)

    return flask.url_for("serve_profile_image", image_name=image_name)
