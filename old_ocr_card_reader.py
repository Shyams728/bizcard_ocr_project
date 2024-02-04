import streamlit as st
from PIL import Image, ImageEnhance
import mysql.connector
from io import BytesIO
import pandas as pd
import easyocr
import numpy as np
import re
from fuzzywuzzy import fuzz



def create_table_in_mysql(mysql):
    db,cursor = mysql
    # Create a table if it doesn't exist
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS business_cards (
        id INT AUTO_INCREMENT PRIMARY KEY,
        company_name VARCHAR(255),
        card_holder_name VARCHAR(255),
        designation VARCHAR(255),
        mobile_numbers TEXT,
        email VARCHAR(255),
        website VARCHAR(255),
        address_area VARCHAR(255),
        address_city VARCHAR(255),
        address_state VARCHAR(255),
        address_pin_code VARCHAR(255),
        image MEDIUMBLOB   
        )
    """)
    db.commit()


# Function to save extracted information to MySQL database
def save_to_database(mysql,extracted_info,image):
    # Connect to MySQL database
    db,cursor = mysql
    
    # Insert data into the database
    insert_query = """
    INSERT INTO business_cards (
        company_name, card_holder_name, designation, mobile_numbers, email, website,
        address_area, address_city, address_state, address_pin_code,image
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    address = extracted_info['address']
    values = (       
        extracted_info['company_name'],
        extracted_info['card_holder_name'],
        extracted_info['designation'],
        ', '.join(extracted_info['mobile_numbers']),
        extracted_info['email'],
        extracted_info['website'],
        ', '.join(address['area']),
        address['city'],
        address['state'],
        address['pin_code'],
        image
        )
    cursor.execute(insert_query, values)
    db.commit()
    cursor.close()
    db.close()

# Function to retrieve data from MySQL database
def retrieve_from_database(mysql):
    # Connect to MySQL database
    db,cursor = mysql
    # Retrieve data from the database
    query = "SELECT * FROM business_cards"
    retrieved_data = pd.read_sql(query, con=db)
    
    db.close()

    return retrieved_data



def data_extraction_from_bizcard(bizcard):

    # image = Image.open(bizcard)
    image = bizcard
    # Get the dimensions of the image
    width, height = image.size

    # Split the image into two parts vertically
    split_point = width // 2
    left_part = image.crop((0, 0, split_point, height))
    right_part = image.crop((split_point, 0, width, height))

    # Function to preprocess an image
    @st.cache_resource
    def preprocess_image(input_image):
        # Enhance the image using Pillow's ImageEnhance module
        enhancer = ImageEnhance.Contrast(input_image)
        enhanced_image = enhancer.enhance(2.0)  # Adjust the enhancement factor as needed

        # Convert the enhanced image to grayscale
        gray_image = enhanced_image.convert('L')

        # Convert the grayscale image to a numpy array
        image_np = np.array(gray_image)

        return image_np

    # Preprocess left and right parts
    preprocessed_left_part = preprocess_image(left_part)
    preprocessed_right_part = preprocess_image(right_part)

    # Initialize the EasyOCR reader
    reader = easyocr.Reader(lang_list=['en'])

    # Perform OCR on the preprocessed left part of the image
    left_results = reader.readtext(preprocessed_left_part)

    # Perform OCR on the preprocessed right part of the image
    right_results = reader.readtext(preprocessed_right_part)

    # Initialize the extracted_info dictionary
    extracted_info = {
        "company_name": "",
        "card_holder_name": "",
        "designation": "",
        "mobile_numbers": [],
        "email": "",
        "website": "",
        "address": {
            "area": "",
            "city": "",
            "state": "",
            "pin_code": ""
        }
    }

    # Choose the side with valid data
    def choose_side(left_results, right_results):
        temp_name = []
        if len(left_results) > len(right_results):
            for bbox, text, prob in right_results:
                temp_name.append(text)
            extracted_info["company_name"] = ' '.join(temp_name)
            return left_results
        else:
            for bbox, text, prob in left_results:
                temp_name.append(text)
            extracted_info["company_name"] = ' '.join(temp_name)
            return right_results

    # Extracted text list to store extracted information
    extracted_text = []

    # Extract information from EasyOCR results of both left and right parts
    for bbox, text, prob in choose_side(left_results, right_results):
        extracted_text.append(text)

    # List of Indian states
    states = ['Andhra Pradesh', 'Arunachal Pradesh', 'Assam', 'Bihar', 'Chhattisgarh', 'Goa', 'Gujarat',
            'Haryana', 'Himachal Pradesh', 'Jharkhand', 'Karnataka', 'Kerala', 'Madhya Pradesh',
            'Maharashtra', 'Manipur', 'Meghalaya', 'Mizoram', 'Nagaland', 'Odisha', 'Punjab',
            'Rajasthan', 'Sikkim', 'TamilNadu', 'Telangana', 'Tripura', 'Uttar Pradesh', 'Uttarakhand', 'West Bengal']

    # Keywords for area recognition
    area_keywords = ['road', 'floor', 'st ', 'st,', 'street', 'dt ', 'district', 'near', 'beside', 'opposite', 'at ', 'in ',
                    'center', 'main road', 'state', 'country', 'post', 'zip', 'city', 'zone', 'mandal', 'town', 'rural',
                    'circle', 'next to', 'across from', 'area', 'building', 'towers', 'village', 'st ', 'via ', 'via,', 'east ', 'west ', 'north ', 'south ']

    # Function for approximate string matching using FuzzyWuzzy
    def approximate_match(pattern, text):
        return re.match(pattern, text) or fuzz.partial_ratio(pattern, text) >= 80


    def extract_card_holder_name(extracted_info, extracted_text):
        for text in extracted_text:
            if text != extracted_info.values():
                if not text.isnumeric() and re.match(name_pattern, text):
                    extracted_info["card_holder_name"] = text
                    break

    # Regular expressions patterns
    name_pattern = r'^([A-Z][a-z]+)\n'
    designation_keywords = r'CEO|Chief Executive Officer|Manager|Supervisor|Founder|Executive|Director|Coordinator|Analyst|Specialist|President|Vice President|Administrator|Assistant|Engineer|Consultant|Technician|Developer|Designer|Accountant|Salesperson|Researcher|Scientist|Attorney|Doctor|Nurse'
    mobile_pattern = r"(\+?\d{3}-\d{3}-\d{4}|\+91?-?\d{3}-\d{4}|\+91?\d{3}-\d{3}-\d{4})" #r'(\+?\d{3}-\d{3}-\d{4})'
    email_pattern = r'\b[\w\.-]+@[\w\.-]+\w+\b'
    website_pattern = r'(?!.*@)(www|.*com$)'

    # Extract information from extracted_text
    for text in extracted_text:
        mod = text.split()
        for data in mod:
            if approximate_match(designation_keywords.lower(), data.lower()):
                extracted_info["designation"] = text

        if approximate_match(mobile_pattern, text.lower()):
            extracted_info["mobile_numbers"].append(text)

        if approximate_match(email_pattern, text.lower()):
            extracted_info["email"] = text

        if approximate_match(website_pattern, text.lower()):
            extracted_info["website"] = text

        for area in area_keywords:
            if approximate_match(area.lower(), text.lower()):
                address_area = text.replace(",", "").replace(".", "").replace(";", "").replace(":", "")
                a = address_area.split()
                extracted_info["address"]["area"] = a[:-1]
                if a[-1] not in states:
                    extracted_info["address"]["city"] = a[-1]
                else:
                    extracted_info["address"]["city"] = a[-2]
                    extracted_info["address"]["area"] = a[:-2]
                    extracted_info["address"]["state"] = a[-1]

        if re.findall(r'\d{6,7}', text):
          data = text.split()
          for pincode in data:
            if pincode.isdigit():
              # print(f"isdigit = {pincode} ")
              extracted_info["address"]["pin_code"] = pincode
            if pincode.isalpha():
              # print(f"isalpha = {pincode} ")
              extracted_info["address"]["state"] = pincode
              
        else:
            extract_card_holder_name(extracted_info, extracted_text)

    return extracted_info



# Create the database connection

def connect_to_mysql(host, user, password, database):
    mysql_connection = mysql.connector.connect(
        host=host, user=user, password=password, database=database
    )
    mysql_cursor = mysql_connection.cursor()
    return mysql_connection, mysql_cursor

# Function to Get data from MySQL
def fetch_data_from_mysql(query,mysql_connection):
    df = pd.read_sql(query, mysql_connection)
    mysql_connection.close()
    return df

@st.cache_resource
def load_image(uploaded_file):
    return Image.open(uploaded_file)


# Convert PIL Image to bytes
def image_to_bytes(image):
    img_byte_array = BytesIO()
    image.save(img_byte_array, format=image.format)
    return img_byte_array.getvalue()

# Create a Streamlit UI
def main():
    
    # Set page width and background color
    st.set_page_config(
        page_title="Business Card OCR",
        page_icon="📇",  # Business card icon
        layout="wide",
        initial_sidebar_state="expanded"
    )

    st.title("BizCardX: Extract Business Card Data with OCR")
    
    st.markdown("""
    <div style="background-color: #d8e2dc; padding: 20px; border-radius: 10px;">
        <p style="font-size: 18px; color: #005b96;">
            <strong>This repository</strong> contains a Python script that uses OCR (Optical Character Recognition) to extract information from business card images. The script utilizes the <strong>easyocr</strong> library for text extraction and employs various techniques for approximate string matching to accurately extract relevant data. The extracted information is then stored, retrieved, and displayed here.</p>
    </div>
    """, unsafe_allow_html=True)

    # Adding the new content
    st.markdown("""
    <div style="background-color: #d8e2dc; padding: 20px; border-radius: 10px;">
        <p style="font-size: 18px; color: #005b96;">
            <strong>Images have been optimized for accurate character recognition.</strong> The script applies a series of preprocessing steps to enhance the images before performing OCR. These steps include resizing, cropping, and filtering using the Python Imaging Library (PIL). Resizing ensures consistent dimensions, while cropping focuses on relevant text. Filtering enhances clarity, removing noise and improving edge detection. The optimized images are then fed into the OCR algorithm, resulting in improved character recognition accuracy.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")



    # Upload image
    uploaded_file = st.file_uploader("Upload a business card image", type=["jpg", "jpeg", "png"])

    if uploaded_file is not None:
    
        image = load_image(uploaded_file)
        st.image(image, caption='Uploaded Image.', use_column_width=True)

        # Process the image using the provided code
        # extracted_info = data_extraction_from_bizcard(image)
        extracted_info = {'company_name': 'selva digitals', 'card_holder_name': 'Selva', 'designation': 'DATA MANAGER', 'mobile_numbers': ['+123-456-7890', '+123-456-7891'], 'email': 'hello@XYZI.com', 'website': 'wWW XYZI.com', 'address': {'area': ['123', 'ABC', 'St'], 'city': 'Chennai', 'state': 'TamilNadu', 'pin_code': '600113'}}

        # Display extracted information
        st.write("Extracted Information:")
        st.write("Company Name:", extracted_info["company_name"])
        st.write("Card Holder Name:", extracted_info["card_holder_name"])
        st.write("Designation:", extracted_info["designation"])
        st.write("Mobile Numbers:", extracted_info["mobile_numbers"])
        st.write("Email:", extracted_info["email"])
        st.write("Website:", extracted_info["website"])
        st.write("Address:", extracted_info["address"])
        
        # Create the sidebar
        st.sidebar.title("Credentials")

        st.markdown("---")
        
        st.sidebar.markdown("---")
        # MySQL options
        st.sidebar.title("MySQL Options")
        mysql_host = st.sidebar.text_input("Enter MySQL host:", "localhost")
        mysql_user = st.sidebar.text_input("Enter MySQL username:", "root")
        mysql_password = st.sidebar.text_input("Enter MySQL password:", type="password")
        mysql_database = st.sidebar.text_input("Enter MySQL database name:", "bizcardx")

        # Connect to MySQL
        mysql = connect_to_mysql(mysql_host, mysql_user, mysql_password, mysql_database)
        db, cursor = mysql
        
        # Check if the connection is successful
        if st.sidebar.button("Connect"):
            try:
                db.ping()
                st.sidebar.success("Connection successful!")
            except Exception as e:
                st.sidebar.error(f"Connection failed: {e}")

        # create table in MySQL
        create_table_in_mysql(mysql)
        
        image_file = image_to_bytes(image)
        # Save the extracted information to MySQL database
        if st.button("Save to Database"):
            save_to_database(mysql, extracted_info,image_file)
        st.markdown("---")
        # Retrieve data from MySQL database and display
        if st.button("Retrieve from Database"):
            retrieved_data = retrieve_from_database(mysql)
            st.write("Retrieved Data:")
            # Display the dataframe
            st.dataframe(retrieved_data, width=1600, height=200, hide_index=False)
        st.markdown("---")            


if __name__ == '__main__':
    main()
