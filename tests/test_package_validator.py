import hashlib

from sincro.package_validator import check_attachments, check_csv_layout


def test_check_csv_layout_detects_wrong_header(tmp_path):
    path = tmp_path / "records.csv"
    path.write_text("name,id\nAna,1\n", encoding="utf-8")

    results = check_csv_layout(
        {"path": str(path), "expected_columns": ["id", "name"]}
    )

    assert results[0].passed
    assert results[1].issue_count == 1


def test_check_attachments_validates_size_and_hash(tmp_path):
    attachment = tmp_path / "document.pdf"
    attachment.write_bytes(b"example")
    digest = hashlib.sha256(b"example").hexdigest()
    manifest = tmp_path / "attachments.csv"
    manifest.write_text(
        f"path,size,hash\ndocument.pdf,7,{digest}\n",
        encoding="utf-8",
    )

    result = check_attachments(
        {
            "manifest": str(manifest), "root": str(tmp_path),
            "path_column": "path", "size_column": "size",
            "hash_column": "hash",
        }
    )

    assert result.passed


def test_check_attachments_rejects_path_traversal(tmp_path):
    manifest = tmp_path / "attachments.csv"
    manifest.write_text("path\n../secret.txt\n", encoding="utf-8")

    result = check_attachments(
        {"manifest": str(manifest), "root": str(tmp_path), "path_column": "path"}
    )

    assert result.sample[0]["problem"] == "path_outside_root"


# @hugaojanuario
