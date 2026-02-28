import sys
import pdfplumber


def extract_text(pdf_path: str) -> str:
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, 1):
            text = page.extract_text()
            if text and text.strip():
                pages.append(f"=== 第 {i} 页 ===\n{text.strip()}")
    return "\n\n".join(pages)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python extract_pdf.py <pdf文件路径>")
        sys.exit(1)
    result = extract_text(sys.argv[1])
    print(result)
