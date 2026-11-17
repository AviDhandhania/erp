import unittest
from unittest.mock import Mock, patch

import frappe

from sales_erp import gallery


class TestGalleryFileLifecycle(unittest.TestCase):
    def test_packaged_asset_is_never_deleted(self):
        with patch.object(frappe, "delete_doc") as delete_doc:
            self.assertEqual(gallery._delete_orphan("/assets/sales_erp/test.jpg"), 0)
        delete_doc.assert_not_called()

    def test_referenced_upload_is_never_deleted(self):
        with patch.object(frappe.db, "exists", return_value=True), patch.object(
            frappe, "delete_doc"
        ) as delete_doc:
            self.assertEqual(gallery._delete_orphan("/files/shared.jpg"), 0)
        delete_doc.assert_not_called()

    def test_unreferenced_local_gallery_upload_is_deleted(self):
        with patch.object(frappe.db, "exists", return_value=False), patch.object(
            frappe, "get_all", return_value=["FILE-1"]
        ), patch.object(frappe, "delete_doc") as delete_doc:
            self.assertEqual(gallery._delete_orphan("/files/orphan.jpg", "ITEM-1"), 1)
        delete_doc.assert_called_once_with("File", "FILE-1", ignore_permissions=True)

    def test_removing_a_gallery_row_checks_only_removed_urls(self):
        old = frappe._dict(
            custom_clothing_product_images=[
                frappe._dict(image="/files/keep.jpg"),
                frappe._dict(image="/files/remove.jpg"),
            ]
        )
        current = frappe._dict(
            name="ITEM-1",
            custom_clothing_product_images=[frappe._dict(image="/files/keep.jpg")],
        )
        current.get_doc_before_save = Mock(return_value=old)
        with patch.object(gallery, "_delete_orphan") as delete_orphan:
            gallery.cleanup_removed_gallery_files(current)
        delete_orphan.assert_called_once_with("/files/remove.jpg", item_name="ITEM-1")
