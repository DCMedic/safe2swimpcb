import io

from PIL import Image, ImageDraw

from scripts.flag_image_verification import classify_flag_image_bytes


def png_bytes(draw_fn):
    image = Image.new("RGB", (200, 120), "white")
    draw = ImageDraw.Draw(image)
    draw_fn(draw)
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def test_yellow_flag_image_can_be_publishable():
    data = png_bytes(lambda d: d.rectangle((20, 20, 180, 100), fill=(245, 205, 20)))
    result = classify_flag_image_bytes(data)
    assert result.primary == "Yellow"
    assert result.publishable is True
    assert result.confidence >= 0.82


def test_green_flag_image_can_be_publishable():
    data = png_bytes(lambda d: d.rectangle((20, 20, 180, 100), fill=(20, 150, 70)))
    result = classify_flag_image_bytes(data)
    assert result.primary == "Green"
    assert result.publishable is True


def test_red_image_is_never_published_without_single_double_evidence():
    data = png_bytes(lambda d: d.rectangle((20, 20, 180, 100), fill=(220, 35, 35)))
    result = classify_flag_image_bytes(data)
    assert result.primary is None
    assert result.publishable is False
    assert "Single Red" in result.reason
    assert "Double Red" in result.reason


def test_multicolor_legend_like_image_is_rejected():
    def draw(d):
        d.rectangle((10, 15, 190, 40), fill=(20, 150, 70))
        d.rectangle((10, 48, 190, 73), fill=(245, 205, 20))
        d.rectangle((10, 81, 190, 106), fill=(220, 35, 35))
    result = classify_flag_image_bytes(png_bytes(draw))
    assert result.publishable is False
    assert result.primary is None


def test_small_colored_logo_patch_is_rejected():
    data = png_bytes(lambda d: d.rectangle((5, 5, 25, 25), fill=(245, 205, 20)))
    result = classify_flag_image_bytes(data)
    assert result.publishable is False
    assert result.primary is None


def test_purple_is_overlay_not_primary():
    def draw(d):
        d.rectangle((10, 10, 190, 80), fill=(245, 205, 20))
        d.rectangle((30, 86, 170, 112), fill=(125, 45, 165))
    result = classify_flag_image_bytes(png_bytes(draw))
    assert result.primary == "Yellow"
    assert result.purple is True
