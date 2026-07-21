import tempfile
import unittest
from pathlib import Path

from scripts.pack_version import (
    PackChangelogError,
    PackVersionError,
    classify_pack_version_transition,
    compare_pack_versions,
    parse_pack_version,
    read_pack_changelog,
    read_pack_version,
)


class PackVersionTest(unittest.TestCase):
    @staticmethod
    def _changelog(*, current: str = "0.2.0", previous: str = "0.1.0") -> str:
        return (
            "# Changelog\n\n"
            "All notable changes to this project are documented in this file.\n\n"
            "The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), "
            "and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).\n\n"
            "## [Unreleased]\n\n"
            f"## [{current}] - 2026-07-21\n\n"
            "### Added\n\n"
            "- Added a governed workflow-pack release contract.\n\n"
            f"## [{previous}] - 2026-07-20\n\n"
            "### Added\n\n"
            "- Added the initial workflow pack.\n"
        )

    def test_parse_accepts_semver_release_and_prerelease(self) -> None:
        self.assertEqual("0.1.0", parse_pack_version("0.1.0"))
        self.assertEqual("1.2.3-rc.1+build.7", parse_pack_version("1.2.3-rc.1+build.7"))

    def test_parse_rejects_non_semver_and_surrounding_whitespace(self) -> None:
        for value in ("", "1", "1.2", "01.2.3", "1.2.3 ", "v1.2.3"):
            with self.subTest(value=value), self.assertRaises(PackVersionError):
                parse_pack_version(value)

    def test_compare_follows_semver_prerelease_precedence(self) -> None:
        ordered = (
            "1.0.0-alpha",
            "1.0.0-alpha.1",
            "1.0.0-alpha.beta",
            "1.0.0-beta",
            "1.0.0-beta.2",
            "1.0.0-beta.11",
            "1.0.0-rc.1",
            "1.0.0",
        )
        for lower, higher in zip(ordered, ordered[1:]):
            with self.subTest(lower=lower, higher=higher):
                self.assertEqual(-1, compare_pack_versions(lower, higher))
                self.assertEqual(1, compare_pack_versions(higher, lower))
        self.assertEqual(0, compare_pack_versions("1.0.0+build.1", "1.0.0+build.2"))

    def test_classify_pack_version_transition(self) -> None:
        cases = (
            (None, "0.1.0", "legacy_install"),
            ("0.1.0", "0.1.0", "same"),
            ("0.1.0", "0.2.0", "compatible_upgrade"),
            ("0.1.0", "1.0.0", "breaking_upgrade"),
            ("1.0.0", "0.1.0", "rollback"),
            ("1.0.0+one", "1.0.0+two", "version_replacement"),
        )
        for current, target, expected in cases:
            with self.subTest(current=current, target=target):
                self.assertEqual(expected, classify_pack_version_transition(current, target))

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

    def test_read_changelog_requires_current_release_and_returns_release_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "VERSION").write_text("0.2.0\n", encoding="utf-8")
            (root / "CHANGELOG.md").write_text(self._changelog(), encoding="utf-8")

            changelog = read_pack_changelog(root)

            self.assertEqual("0.2.0", changelog.current_version)
            self.assertEqual(("0.2.0", "0.1.0"), changelog.release_versions)
            self.assertEqual("2026-07-21", changelog.current_release_date)
            self.assertEqual(("Added",), changelog.current_sections)

    def test_read_changelog_rejects_missing_or_mismatched_current_release(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "VERSION").write_text("0.2.0\n", encoding="utf-8")

            with self.assertRaises(PackChangelogError):
                read_pack_changelog(root)

            (root / "CHANGELOG.md").write_text(
                self._changelog(current="0.1.0", previous="0.0.1"),
                encoding="utf-8",
            )
            with self.assertRaises(PackChangelogError):
                read_pack_changelog(root)

    def test_read_changelog_rejects_invalid_date_order_and_empty_release(self) -> None:
        cases = {
            "invalid-date": self._changelog().replace("2026-07-21", "2026-02-30", 1),
            "wrong-order": self._changelog(current="0.2.0", previous="0.3.0"),
            "empty-release": self._changelog().replace(
                "### Added\n\n- Added a governed workflow-pack release contract.\n\n",
                "",
                1,
            ),
        }
        for name, text in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / "VERSION").write_text("0.2.0\n", encoding="utf-8")
                (root / "CHANGELOG.md").write_text(text, encoding="utf-8")

                with self.assertRaises(PackChangelogError):
                    read_pack_changelog(root)


if __name__ == "__main__":
    unittest.main()
