import streamlit as st
from PIL import Image, ImageEnhance
import sqlite3
from io import BytesIO
import pandas as pd
import easyocr
import numpy as np
import re
from fuzzywuzzy import fuzz
import time
from streamlit_shadcn_ui import table


def preprocess_image(input_image):
    enhancer = ImageEnhance.Contrast(input_image)
    enhanced_image = enhancer.enhance(2.0)
    gray_image = enhanced_image.convert('L')
    image_np = np.array(gray_image)
    return image_np


def extract_text(image):
    width, height = image.size
    split_point_60_percent = int(width * 0.45)
    left_part = image.crop((0, 0, split_point_60_percent, height))
    right_part = image.crop((split_point_60_percent, 0, width, height))
    full_image = image

    preprocessed_left_part = preprocess_image(left_part)
    preprocessed_right_part = preprocess_image(right_part)
    preprocessed_full_image = preprocess_image(full_image)

    reader = easyocr.Reader(['en'])
    left_results = reader.readtext(preprocessed_left_part)
    right_results = reader.readtext(preprocessed_right_part)
    full_results = reader.readtext(preprocessed_full_image)

    return left_results, right_results, full_results

# Function to choose the side with valid data and extract text
def choose_and_extract(left_results, right_results, full_results):
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

    temp_name = []
    if len(left_results) > len(right_results):
        for bbox, text, prob in right_results:
            temp_name.append(text)
        extracted_info["company_name"] = ' '.join(temp_name)
        extracted_text = [text for _, text, _ in left_results]
    else:
        for bbox, text, prob in left_results:
            temp_name.append(text)
        extracted_info["company_name"] = ' '.join(temp_name)
        extracted_text = [text for _, text, _ in right_results]

    if len(full_results) >= 2:
      extracted_info["card_holder_name"] = full_results[0][1]
      extracted_info["designation"] = full_results[1][1]
    
    return extracted_info, extracted_text
#At first try to find by regular expression and if fails ,it will use partial ratio method
def approximate_match(pattern, text):
    return re.match(pattern, text) or fuzz.partial_ratio(pattern, text) >= 80


# Function to extract additional information from text
def extract_additional_info(extracted_info, extracted_text):
    # List of Indian states
    states = ['Andhra Pradesh', 'Arunachal Pradesh', 'Assam', 'Bihar', 'Chhattisgarh', 'Goa', 'Gujarat',
              'Haryana', 'Hyderabad', 'Himachal Pradesh', 'Jharkhand', 'Karnataka', 'Kerala', 'Madhya Pradesh',
              'Maharashtra', 'Manipur', 'Meghalaya', 'Mizoram', 'Nagaland', 'Odisha', 'Punjab',
              'Rajasthan', 'Sikkim', 'TamilNadu', 'Telangana', 'Tripura', 'Uttar Pradesh', 'Uttarakhand', 'West Bengal']

    # Keywords for area recognition
    area_keywords = ['road', 'floor', 'st ', 'st,', 'street', 'dt ', 'district', 'near', 'beside', 'opposite', 'at ', 'in ',
                     'center', 'main road', 'state', 'country', 'post', 'zip', 'city', 'zone', 'mandal', 'town', 'rural',
                     'circle', 'next to', 'across from', 'area', 'building', 'towers', 'village', 'st ', 'via ', 'via,', 'east ', 'west ', 'north ', 'south ']

    # Regular expressions patterns
    name_pattern = r'^([A-Z][a-z]+)\n'
    mobile_pattern = r"(\+?\d{3}-\d{3}-\d{4}|\+91?-?\d{3}-\d{4}|\+91?\d{3}-\d{3}-\d{4})"
    email_pattern = r'\b[\w\.-]+@[\w\.-]+\w+\b'
    website_pattern = r'(?!.*@)(www|.*com$)'
    pincode_pattern = r'\d{6,7}'

    # Extract information from extracted_text
    for text in extracted_text:

        if approximate_match(mobile_pattern, text.lower()):
            extracted_info["mobile_numbers"].append(text)

        if approximate_match(email_pattern, text.lower()):
            extracted_info["email"] = text

        if approximate_match(website_pattern, text.lower()):
            extracted_info["website"] = text

        for area in area_keywords:
            if approximate_match(area.lower(), text.lower()):
                address_area = text.replace(",", "").replace(".", "").replace(";", "").replace(":", "").replace(",", "")
                a = address_area.split()
                extracted_info["address"]["area"] = a[:-1]
                if a[-1] not in states:
                    extracted_info["address"]["city"] = a[-1]
                else:
                    extracted_info["address"]["city"] = a[-2]
                    extracted_info["address"]["area"] = a[:-2]
                    extracted_info["address"]["state"] = a[-1]

        if re.findall(pincode_pattern, text):
          data = text.split()
          for state_pincode in data:
            if state_pincode.isdigit():
              extracted_info["address"]["pin_code"] = state_pincode
            if state_pincode.isalpha():
              extracted_info["address"]["state"] = state_pincode
              
        else:
            if approximate_match(name_pattern, text.lower()):
                extracted_info["card_holder_name"] = text

    return extracted_info


# Preprocess extracted information before saving to database
def preprocess_extracted_info(extracted_info):

    extracted_info['company_name'] = re.sub(r'\d+', '', extracted_info['company_name']).strip().title()
    extracted_info['card_holder_name'] = extracted_info['card_holder_name'].strip().title()
    extracted_info['designation'] = extracted_info['designation'].strip().title()
    for i in range(len(extracted_info['mobile_numbers'])):
        number = extracted_info['mobile_numbers'][i].strip()
        if number and not number.startswith('+'):
            extracted_info['mobile_numbers'][i] = '+' + number
    
    extracted_info['email'] = extracted_info['email'].lower()
    email = extracted_info['email'].strip()
    if '@' in email and 'com' in email:
        if 'com' in email and '.' not in email.split('com')[-1]:
            # Replace 'com' with '.com' if the dot is missing
            extracted_info['email'] = email.replace('com', '.com')


    extracted_info['website'] = extracted_info['website'].lower()
    website = extracted_info['website'].lower()

    if 'www ' in website:
        # If "www" is missing, add it to the beginning of the website
        website_parts = website.split('www ')
        website_parts = [part.strip() for part in website_parts]
        website_parts.insert(1, 'www.')
        extracted_info['website'] = ''.join(website_parts)

    elif 'www.' not in website:
        # If "www" is missing, add it to the beginning of the website
        website_parts = website.split('.')
        website_parts[0] = 'www'
        extracted_info['website'] = '.'.join(website_parts)

    
    extracted_info['address']['city'] = extracted_info['address']['city'].title()

    return extracted_info



def create_table_in_sqlite(sqlite_conn):
    cursor = sqlite_conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS business_cards (
        id INTEGER PRIMARY KEY,
        company_name VARCHAR(60),
        card_holder_name VARCHAR(60),
        designation VARCHAR(60),
        mobile_numbers VARCHAR(100),
        email VARCHAR(60),
        website VARCHAR(60),
        address_area TEXT,
        address_city VARCHAR(30),
        address_state VARCHAR(30),
        address_pin_code VARCHAR(30),
        image BLOB
        )
    """)
    sqlite_conn.commit()

def save_to_database(sqlite_conn, extracted_info, image):
    cursor = sqlite_conn.cursor()
    insert_query = """
    INSERT INTO business_cards (
        company_name, card_holder_name, designation, mobile_numbers, email, website,
        address_area, address_city, address_state, address_pin_code, image
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    
    # Convert the image to a byte stream
    img_byte_arr = BytesIO()
    image.save(img_byte_arr, format='PNG')  # Save the image as PNG
    img_bytes = img_byte_arr.getvalue() 

    values = (
        extracted_info['company_name'],
        extracted_info['card_holder_name'],
        extracted_info['designation'],
        ', '.join(extracted_info['mobile_numbers']),
        extracted_info['email'],
        extracted_info['website'],
        ', '.join(extracted_info['address']['area']),
        extracted_info['address']['city'],
        extracted_info['address']['state'],
        extracted_info['address']['pin_code'],
        img_bytes 
    )
    cursor.execute(insert_query, values)
    sqlite_conn.commit()

def retrieve_from_database(sqlite_conn):
    cursor = sqlite_conn.cursor()
    query = "SELECT * FROM business_cards"
    retrieved_data = pd.read_sql(query, con=sqlite_conn)
    return retrieved_data

def extract_data_from_bizcard(image):
    # Preprocess and extract text
    left_results, right_results, full_results = extract_text(image)
    extracted_info = choose_and_extract(left_results, right_results, full_results)
    
    # Extract additional information
    extracted_data, extracted_text = choose_and_extract(left_results, right_results, full_results)
    extracted_info = extract_additional_info(extracted_data, extracted_text)
    return extracted_info

def display_information(extracted_info):
    display_box = st.container()
    col1,col2 = display_box.columns([3,2])
    with col1:
        st.write("**Company Name:**", extracted_info["company_name"])
        st.write("**Designation:**", extracted_info["designation"])
        st.write("**Card Holder Name:**", extracted_info["card_holder_name"])
        phone_numbers = ','.join(extracted_info["mobile_numbers"])
        st.write("**Mobile Numbers:**",phone_numbers )
        st.write("**Email:**", extracted_info["email"])
    with col2:
        # Display extracted information 
        st.write("**Website:**", extracted_info["website"])
        area = '  '.join(extracted_info["address"]['area'])
        st.write("**Area:**", area)
        st.write("**City:**", extracted_info["address"]['city'])
        st.write("**State:**", extracted_info["address"]['state'])
        st.write("**Pin Code:**", extracted_info["address"]['pin_code'])


# Function to retrieve data from the database
def retrieve_from_database(sqlite_conn):
    try:
        query = "SELECT * FROM business_cards"
        retrieved_data = pd.read_sql(query, con=sqlite_conn)
        return retrieved_data
    except Exception as e:
        st.error(f"Error retrieving data from the database: {str(e)}")
        return pd.DataFrame()

# Function to delete the current business card from the database
def delete_current_card(sqlite_conn, current_row):
    try:
        cursor = sqlite_conn.cursor()
        delete_query = f"DELETE FROM business_cards WHERE id = '{current_row['id']}'"
        cursor.execute(delete_query)
        sqlite_conn.commit()
        st.session_state['current_index'] = max(0, st.session_state['current_index'] - 1)
        st.success('Business card deleted successfully.')
    except Exception as e:
        st.error(f"Error deleting business card: {str(e)}")

# Function to display the business card image
def display_bizcard_image(current_row):
    try:
        display_image = st.container(border=True)
        st.write("#### Business Card Image")
        bizcard_image_data = current_row['image']
        # Convert image data to PIL image
        bizcard_image = Image.open(BytesIO(bizcard_image_data))
        st.image(bizcard_image, caption='Business Card', width=500)
        # display_image.image(bizcard_image, caption='Business Card', use_column_width=True)
    except Exception as e:
        st.error(f"Error displaying business card image: {str(e)}")

# Function to display a card with business card information
def display_business_card(row):
    try:
        display_box = st.container(border=True)
        col1,col2 = display_box.columns([3,2])
        with col1:
            st.write("**Company Name:**", row["company_name"])
            st.write("**Designation:**", row["designation"])
            st.write("**Card Holder Name:**", row["card_holder_name"])
            st.write("**Mobile Numbers:**", row["mobile_numbers"])
            st.write("**Email:**", row["email"])
        with col2:
            st.write("**Website:**", row["website"])
            st.write("**Area:**", row["address_area"])
            st.write("**City:**", row["address_city"])
            st.write("**State:**", row["address_state"])
            st.write("**Pin Code:**", row["address_pin_code"])
    except Exception as e:
        st.error(f"An error occurred while displaying the business card: {e}")

def data_card():
    st.subheader('Business Card Information Viewer')

    # Connect to the database
    try:
        sqlite_conn = sqlite3.connect('business_cards.db')
        data = retrieve_from_database(sqlite_conn)

        # Check if there is data to display
        if not data.empty:
            if 'current_index' not in st.session_state:
                st.session_state['current_index'] = 0

            # Ensure current_index is within bounds
            st.session_state['current_index'] = max(0, min(st.session_state['current_index'], len(data) - 1))

            current_row = data.iloc[st.session_state['current_index']]
            display_business_card(current_row)

        # Navigation buttons
        col1,col5, col2, col3, col4= st.columns(5)
        
        col5.write(f'**ID : {current_row[0]}**')
        if col1.button('< Previous') and st.session_state['current_index'] > 0:
            st.session_state['current_index'] -= 1
        if col2.button('Next >') and st.session_state['current_index'] < len(data) - 1:
            st.session_state['current_index'] += 1

        # Display the button to show the business card image
        if col4.toggle("Show BizCard Image"):
            display_bizcard_image(current_row)

        # Delete button
        if col3.button('Delete this BizCard '):
            delete_current_card(sqlite_conn, current_row)
            # Refresh the data after deletion
            data = retrieve_from_database(sqlite_conn)



    except Exception as e:
        st.error(f"Error: {str(e)}")

    finally:
        # Close the database connection
        if 'sqlite_conn' in locals():
            sqlite_conn.close()

# 6. Main Streamlit app
def main():
    st.set_page_config(
        page_title="Business Card OCR",
        page_icon="📇",  # Business card icon
        layout="wide",
        initial_sidebar_state="expanded"
    )

    st.markdown("""
    <style>
    .big-font {
        font-size:30px !important;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<p class="big-font" style="color:blue;">BizCardX: Business Card Information Extractor with OCR</p>', unsafe_allow_html=True)

    
    st.markdown("""
    <div style="background-color: #d8e2dc; padding: 20px; border-radius: 10px;">
        <p style="font-size: 18px; color: #005b96;">
            <strong>This BizCardX project</strong> contains a Python code that uses OCR (Optical Character Recognition) to extract information from business card images. 
            The script utilizes the <strong>PIL(Python Imaging Library)</strong> and <strong>easyocr</strong>
            library for preprocessing and text extraction and employs various techniques for approximate string matching to accurately extract relevant data. 
            The extracted information is then stored, retrieved, and displayed here.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

 
    # Radio buttons for selecting query type
    selcted_option = st.radio(
        "Select the option",
        ["***Upload a File***", "***View & Modify the Data***"],
        captions = ["To Exctract data from the given business card.", "To check the data in the database and, if necessary, remove the business card from the database",],
        horizontal= True ,
        index=1  # Default selection index 
        )
    choice_box = st.container(border=True)

    if selcted_option == "***Upload a File***" :
        with choice_box:
            # Upload image
            uploaded_file = st.file_uploader("Choose a business card image...", type=["jpg", "jpeg", "png"])
            
        if uploaded_file is not None:
            display_main = st.container(border=True)
            image_display,data_display = display_main.columns([3,4])
            with image_display:
            
                image = Image.open(uploaded_file)
                # st.subheader("Uploaded Business Card")
                st.image(image, caption='Uploaded Business Card', use_column_width=True)

                with data_display:
                    with st.spinner("Executing data extraction please wait......."):
                        time.sleep(2)
                        extracted_info = extract_data_from_bizcard(image)
                        st.success('Extracted successfully!', icon="✅")
                        # Display extracted information   
                        st.subheader("Extracted Information")
                        display_information(extracted_info)
                        final_info = preprocess_extracted_info(extracted_info)
                        display_main.success('standardising the data before saving')
                        #save the data to data base
                        conn = sqlite3.connect('business_cards.db') 
                        create_table_in_sqlite(conn) 
                        save_to_database(conn, final_info, image) 
                        display_main.success('Saved to database!')

    if selcted_option == "***View & Modify the Data***":

        with choice_box:
            data_card()
            # Upload image

        display_main = st.container(border=True)
        
        # Retrieve from database
        conn = sqlite3.connect('business_cards.db')
        bizcard_data = retrieve_from_database(conn)
        bizcard_data.drop(columns=['image'], inplace=True)
        
        with display_main:
            with st.expander(f"Show table data"):
                table(data=bizcard_data, maxHeight=500, key="bizcard_data")


if __name__ == '__main__':
    main()
