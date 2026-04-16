from __future__ import annotations

from pathlib import Path

from scripts import make_seed_csv


def test_build_rows_normalizes_usernames_and_links() -> None:
    rows = make_seed_csv.build_rows(
        group_name="  VUZ  ",
        seed_lines=["@synergyunivers", "https://t.me/SynergyUnivers", "t.me/s/another_seed"],
        notes="starter seed",
    )

    assert [row.channel for row in rows] == [
        "https://t.me/synergyunivers",
        "https://t.me/another_seed",
    ]
    assert rows[0].group_name == "VUZ"
    assert rows[0].title == "synergyunivers"
    assert rows[0].notes == "starter seed"


def test_render_csv_uses_bot_import_columns() -> None:
    rows = [
        make_seed_csv.SeedCsvRow(
            group_name="VUZ",
            channel="https://t.me/synergyunivers",
            title="synergyunivers",
            notes="",
        )
    ]

    assert make_seed_csv.render_csv(rows) == (
        "group_name,channel,title,notes\n"
        "VUZ,https://t.me/synergyunivers,synergyunivers,\n"
    )


def test_main_writes_output_file(tmp_path: Path) -> None:
    output_path = tmp_path / "seeds.csv"

    exit_code = make_seed_csv.main(
        ["--group", "VUZ", "--output", str(output_path), "@synergyunivers"]
    )

    assert exit_code == 0
    assert output_path.read_text(encoding="utf-8") == (
        "group_name,channel,title,notes\n"
        "VUZ,https://t.me/synergyunivers,synergyunivers,\n"
    )


def test_invalid_seed_returns_error_without_writing(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "seeds.csv"

    exit_code = make_seed_csv.main(
        ["--group", "VUZ", "--output", str(output_path), "https://t.me/+private"]
    )

    assert exit_code == 1
    assert not output_path.exists()
    assert "Private invite links are not supported" in capsys.readouterr().err
