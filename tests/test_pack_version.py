import tempfile
import unittest
from pathlib import Path

from scripts.pack_version import PackVersionError, parse_pack_version, read_pack_version


class PackVersionTest(unittest.TestCase):
    def test_parse_accepts_semver_release_and_prerelease(self) -> None:
        self.assertEqual("0.1.0", parse_pack_version("0.1.0"))
        self.assertEqual("1.2.3-rc.1+build.7", parse_pack_version("1.2.3-rc.1+build.7"))

    def test_parse_rejects_non_semver_and_surrounding_whitespace(self) -> None:
        for value in ("", "1", "1.2", "01.2.3", "1.2.3 ", "v1.2.3"):
            with self.subTest(value=value), self.assertRaises(PackVersionError):
                parse_pack_version(value)

    def test_read_requires_regular_utf8_single_line_version_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            version = root / "VERSION"
            version.write_text("0.1.0\n", encoding="utf-8")
            self.assertEqual("0.1.0", read_pack_version(root))

            version.write_text("0.1.0\nextra\n", encoding="utf-8")
            with self.assertRaises(PackVersionError):
                read_pack_version(root)

            version.unlink()
            version.mkdir()
            with self.assertRaises(PackVersionError):
                read_pack_version(root)

    def test_read_rejects_invalid_encoding_symlink_and_oversized_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            version = root / "VERSION"
            version.write_bytes(b"\xff\n")
            with self.assertRaises(PackVersionError):
                read_pack_version(root)

            version.unlink()
            source = root / "source-version"
            source.write_text("0.1.0\n", encoding="utf-8")
            version.symlink_to(source.name)
            with self.assertRaises(PackVersionError):
                read_pack_version(root)

            version.unlink()
            version.write_text("1.2.3+" + "a" * 300, encoding="utf-8")
            with self.assertRaises(PackVersionError):
                read_pack_version(root)


if __name__ == "__main__":
    unittest.main()
