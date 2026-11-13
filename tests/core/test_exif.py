import pytest
from PIL import Image

from perspective_projector.core import exif, solve


def _jpeg(path, exif_ifd=None, size=(600, 400)):
    img = Image.new("RGB", size, (120, 120, 120))
    if exif_ifd is None:
        img.save(path, "JPEG")
        return path
    ex = Image.Exif()
    ex[0x010F] = "TestCam"
    ifd = ex.get_ifd(0x8769)
    ifd.update(exif_ifd)
    img.save(path, "JPEG", exif=ex.tobytes())
    return path


def test_35mm_equivalent(tmp_path):
    p = _jpeg(tmp_path / "a.jpg", {exif.TAG_FOCAL_35MM: 28, exif.TAG_FOCAL_LENGTH: 4.3})
    f, desc = exif.focal_px_from_exif(p, 600, 400)
    assert f == pytest.approx(solve.focal_from_35mm(28, 600, 400))
    assert "28" in desc


def test_physical_focal_without_35mm_is_not_used(tmp_path):
    # FocalPlaneXResolution is unreliable (Fujifilm X100T writes one that does not match the sensor)
    p = _jpeg(tmp_path / "b.jpg", {exif.TAG_FOCAL_LENGTH: 23.0, exif.TAG_FOCAL_PLANE_XRES: 820.0,
                                    exif.TAG_FOCAL_PLANE_UNIT: 3})
    assert exif.focal_px_from_exif(p, 600, 400) is None


def test_no_exif(tmp_path):
    p = _jpeg(tmp_path / "c.jpg")
    assert exif.focal_px_from_exif(p, 600, 400) is None


def test_tiff(tmp_path):
    img = Image.new("RGB", (300, 200))
    ex = Image.Exif()
    ex.get_ifd(0x8769)[exif.TAG_FOCAL_35MM] = 50
    p = tmp_path / "d.tif"
    img.save(p, "TIFF", exif=ex.tobytes())
    f, _ = exif.focal_px_from_exif(p, 300, 200)
    assert f == pytest.approx(solve.focal_from_35mm(50, 300, 200))


def test_not_an_image(tmp_path):
    p = tmp_path / "e.jpg"
    p.write_bytes(b"hello")
    assert exif.focal_px_from_exif(p, 10, 10) is None
