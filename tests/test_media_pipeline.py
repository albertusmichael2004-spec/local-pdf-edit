from pathlib import Path
import zipfile

from PIL import Image
from pypdf import PdfReader

from backend.services.media.capabilities import capability_payload, targets_for
from backend.services.media.engines.ffmpeg import build_ffmpeg_command
from backend.services.media.facade import MediaJobFacade
from backend.services.media.models import JobOptions, MediaProbeResult, MediaSource
from backend.services.media.probe import probe_media


def make_image(path: Path, color: str) -> Path:
    image = Image.new("RGBA", (80, 50), color)
    image.save(path, "PNG")
    image.close()
    return path


def test_probe_reads_content_instead_of_extension(tmp_path: Path):
    source = make_image(tmp_path / "misleading.data", "red")
    result = probe_media(source)
    assert result.kind == "image"
    assert result.format == "png"
    assert result.details["alpha"] is True
    assert any(item["format"] == "png" for item in targets_for(result))


def test_image_facade_direct_and_zip64_batch(tmp_path: Path):
    sources = [
        MediaSource(make_image(tmp_path / "one.png", "red"), "one.png"),
        MediaSource(make_image(tmp_path / "two.png", "blue"), "two.png"),
    ]
    facade = MediaJobFacade()
    single = facade.process(sources[:1], tmp_path / "single", JobOptions("converted", "jpg"), {"image"})
    assert single.media_type == "image/jpeg"
    assert single.path.suffix == ".jpg"
    with Image.open(single.path) as result:
        assert result.format == "JPEG"

    batch = facade.process(sources, tmp_path / "batch", JobOptions("compressed", "keep", "smallest"), {"image"})
    assert batch.media_type == "application/zip"
    with zipfile.ZipFile(batch.path) as archive:
        assert archive.namelist() == ["one_compressed.png", "two_compressed.png"]
        assert archive._allowZip64 is True


def test_pdf_and_image_capabilities_are_available_without_external_tools():
    payload = capability_payload()
    assert "docx" in payload["targets"]["pdf"]
    assert "png" in payload["targets"]["image"]
    assert "No app-imposed" in payload["constraints"]


def test_ffmpeg_command_builder_uses_argument_list(tmp_path: Path):
    source = tmp_path / "clip with spaces.mov"
    output = tmp_path / "clip.mp4"
    probe = MediaProbeResult("video", "mov", "video/quicktime", 123)
    command = build_ffmpeg_command("ffmpeg.exe", source, output, probe, JobOptions("converted", "mp4"))
    assert command[0] == "ffmpeg.exe"
    assert str(source) in command
    assert command[-1] == str(output)
    assert "shell=True" not in command


def test_animated_image_to_pdf_uses_one_page(tmp_path: Path):
    source = tmp_path / "animated.gif"
    first = Image.new("RGB", (80, 50), "red")
    second = Image.new("RGB", (80, 50), "blue")
    first.save(source, "GIF", save_all=True, append_images=[second], duration=50, loop=0)
    first.close()
    second.close()

    result = MediaJobFacade().process(
        [MediaSource(source, source.name)],
        tmp_path / "pdf-output",
        JobOptions("converted", "pdf"),
        {"image"},
    )
    assert len(PdfReader(str(result.path)).pages) == 1
    assert "first frame" in result.warnings[0]


def test_extreme_video_command_downscales_large_video(tmp_path: Path):
    source = tmp_path / "large.mov"
    output = tmp_path / "small.mp4"
    probe = MediaProbeResult(
        "video",
        "mov",
        "video/quicktime",
        123,
        {"width": 1920, "height": 1080},
    )
    command = build_ffmpeg_command(
        "ffmpeg.exe",
        source,
        output,
        probe,
        JobOptions("compressed", "mp4", "extreme"),
    )
    assert command[command.index("-crf") + 1] == "36"
    assert command[command.index("-vf") + 1] == "scale=-2:720"
