import pytest
import fitz
from unittest.mock import MagicMock
from app.utils.extract_label import get_label_rect, extract_label_from_pdf, extract_product_details

def test_get_label_rect_fallback():
    mock_page = MagicMock()
    mock_page.rect = fitz.Rect(0, 0, 600, 800)
    mock_page.get_text.return_value = []
    mock_page.get_drawings.return_value = []
    mock_page.get_images.return_value = []
    
    rect = get_label_rect(mock_page)
    assert rect == fitz.Rect(0, 0, 300, 800)

def test_extract_label_missing_file():
    with pytest.raises(FileNotFoundError):
        extract_label_from_pdf("non_existent_file_path_xyz.pdf")

def test_extract_product_details_no_second_page():
    mock_doc = MagicMock()
    mock_doc.__len__.return_value = 1
    result = extract_product_details(mock_doc)
    assert result == "Sin detalles de producto"

def test_extract_product_details_success():
    mock_doc = MagicMock()
    mock_doc.__len__.return_value = 2
    
    mock_page_1 = MagicMock()
    mock_page_1.get_text.return_value = [
        (250, 150, 400, 170, "Product 1 Title", 0, 0),
        (250, 180, 400, 200, "Cantidad: 3", 1, 0),
        (250, 210, 400, 230, "Color: Azul", 2, 0),
        (250, 250, 400, 270, "Product 2 Title", 3, 0),
        (250, 280, 400, 300, "Cantidad: 1", 4, 0),
    ]
    mock_doc.__getitem__.return_value = mock_page_1
    
    result = extract_product_details(mock_doc)
    assert "1. Product 1 Title (Cantidad: 3)" in result
    assert "Color: Azul" in result
    assert "2. Product 2 Title (Cantidad: 1)" in result
