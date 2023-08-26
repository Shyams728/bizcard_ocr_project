# BizCardX: Business Card OCR

This repository contains a _Python script_ that utilizes `Optical Character Recognition (OCR)` to extract information from images of business cards. The script employs the `easyocr` library for text extraction and incorporates various techniques, `including regular expressions`, for approximate string matching. This ensures the accurate extraction of relevant data. The extracted information is then `stored in MySQL`, `retrieved`, and displayed in `Streamlit GUI`.

## Optimized Image Processing

The script applies a series of preprocessing steps to enhance the images before performing OCR. These steps include:

1. **Resizing**: Images are resized to ensure consistent dimensions, optimizing OCR accuracy.
2. **Cropping**: Cropping focuses on the relevant text, eliminating unnecessary elements for better extraction.
3. **Filtering**: The `Python Imaging Library (PIL)` is used for filtering to enhance clarity by removing noise and improving edge detection.

_These optimized images are then input into the OCR algorithm, resulting in improved character recognition accuracy. Additionally, regular expressions are extensively used to clean the extracted text and obtain the required results._

---

## Getting Started

### Prerequisites

Ensure you have the following dependencies installed:

- `Python 3.11.x`
- `streamlit`
- `easyocr`
- `Python Imaging Library (PIL)`
- `mysql-connector-python` (for MySQL integration)
- `pandas`
- `numpy`

### Installation

1. Clone this repository to your local machine:

   ```bash
   git clone https://github.com/Shyams728/https---github.com-Shyams728-bizcard_ocr_project/edit/main.git
   ```

2. Install the required Python packages:

   ```bash
   pip install -r requirements.txt
   ```
5. Running the Application:

   ```bash
   streamlit run ocr_card_reader.py
   ```


1. Upload an image of a business card (formats: jpg, jpeg, png).
2. The script will process the uploaded image, extract information, and use regular expressions to refine the text.
3. Extracted information, including the company name, cardholder's name, designation, mobile numbers, email, website, and address, will be displayed.

## Extracted Information
```python
Extracted Information: 
{
 'card_holder_name': 'Amit kumar',
 'company_name': 'GLOBAL INSURANCE',
 'designation': 'CEO & FOUNDER',
 'email': 'hello@globalcom',
 'mobile_numbers': ['123-456-7569'],
 'website': '.global.com'
 'address': {'area': ['123', 'global', 'St'],
             'city': 'Erode',
             'pin_code': '600115',
             'state': 'TamilNadu'}
 }
```

### MySQL Integration

To integrate with MySQL, follow these steps:

1. Enter the MySQL host, username, password, and database name in the sidebar.
2. Click the "Connect" button to establish a connection.
3. Use the "Save to Database" button to save the extracted information to the MySQL database.
4. Click the "Retrieve from Database" button to retrieve and display data from the MySQL database.

---

## Contact

For questions or issues, please contact [Shyamsundar Dharwad](mailto:shyamsundardharwad@gmail.com).

#### Please note that the script utilizes various approximate matching techniques to ensure accurate extraction of information.
---
## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

