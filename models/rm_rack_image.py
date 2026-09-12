# -*- coding: utf-8 -*-
import base64
import logging
from io import BytesIO

from odoo import models

_logger = logging.getLogger(__name__)

try:
    from PIL import Image
except ImportError:  # pragma: no cover - Pillow ships with Odoo itself
    Image = None


class RmRackImageMixin(models.AbstractModel):
    """Shared image-compositing helpers for generating a real, stored
    product image that visually matches the Ribbon Rack / Medal Rack
    OWL widgets (see static/src/js/ribbon_rack.js, medal_rack.js and
    their .scss files - this is kept in sync with those BY HAND; if
    their layout changes, this should too).

    Used by rm.rack.product (grid layout) and rm.medal.rack (single,
    overlapping-when-crowded row layout) - the two "finished" rack
    models. The result is always set on the specific VARIANT's own
    image_variant_1920, never the shared template's image_1920 - many
    different combinations are variants of the same shared template
    (see rm_product_sync_mixin._ensure_rm_variant), so writing at the
    template level would incorrectly give every combination the same
    picture.
    """
    _name = 'rm.rack.image.mixin'
    _description = 'Rack Image Generation Mixin'

    def _rm_pil_available(self):
        if Image is None:
            _logger.warning(
                "Pillow isn't available - skipping rack image generation "
                "for %s. Install it (pip install Pillow) to enable this.",
                self._name)
            return False
        return True

    def _rm_new_canvas(self, width, height, background=(0, 0, 0, 0)):
        if not self._rm_pil_available():
            return None
        return Image.new('RGBA', (width, height), background)

    def _rm_paste_cell(self, canvas, decoration_image_b64, attachment_image_b64, box):
        """Paste one cell's decoration image (ribbon or medal), fit to
        `box` (left, top, width, height) with a cover-style crop
        (matching the widgets' `object-fit: cover`), then the
        attachment/device badge on top at the same box - matching the
        widgets' two-stacked-<img> pattern."""
        if canvas is None:
            return
        left, top, width, height = box
        for image_b64 in (decoration_image_b64, attachment_image_b64):
            if not image_b64:
                continue
            try:
                cell_img = Image.open(BytesIO(base64.b64decode(image_b64))).convert('RGBA')
            except Exception:
                _logger.warning(
                    "Could not decode an image while generating a rack "
                    "image for %s - skipping that cell's image.", self._name, exc_info=True)
                continue
            src_w, src_h = cell_img.size
            if not src_w or not src_h:
                continue
            scale = max(width / src_w, height / src_h)
            resized = cell_img.resize((max(1, round(src_w * scale)), max(1, round(src_h * scale))))
            crop_left = (resized.width - width) // 2
            crop_top = (resized.height - height) // 2
            cropped = resized.crop((crop_left, crop_top, crop_left + width, crop_top + height))
            canvas.paste(cropped, (left, top), cropped)

    def _rm_finalize_image(self, canvas, flatten=False):
        if canvas is None:
            return False
        buf = BytesIO()
        (canvas.convert('RGB') if flatten else canvas).save(buf, format='PNG')
        return base64.b64encode(buf.getvalue())
