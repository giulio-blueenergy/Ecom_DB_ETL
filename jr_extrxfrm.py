# this module connects to the supplier server, retrieves
# the updated product list and transforms it according to
# the master stock list format
import requests
import os
import pandas as pd
from sqlalchemy import delete
import re
from my_data import suppliers_path, suppliers_list

# EXTRACT: connect to server via HTTPS and import updated product table into a local file and a dataframe
def jr_extr(url):
    product_list = pd.read_csv(url, sep=';')
    os.makedirs(suppliers_path, exist_ok=True)
    with open(os.path.join(suppliers_path,'{}_raw_file.csv'.format(suppliers_list['JR'])),'w',newline='', encoding="utf-8") as csv_file:
        url_file = requests.get(url).content.decode('utf-8')
        csv_file.write(url_file)
    return product_list

# TRANSFORM: rename/transform/add/drop columns as per database table
def jr_xfrm(df):
    col_names = {
        'part_number': 'SKU CODE (UNIQUE)',
        'brand': 'BRAND',
        'model': 'WHEEL MODEL',
        'size': 'SIZE',
        'width': 'J WIDTH',
        'pcd': 'PCD',
        'et': 'ET',
        'colour': 'COLOUR',
        'center_bore': 'CB',
        'stock': 'QUANTITY (SETS AVAILABLE)',
        'photo': 'IMAGE 1 URL',
        'suggested_retail_price': 'MSRP',
    }
    # rename columns
    df.rename(columns=col_names, inplace=True)
    # drop non-relevant columns
    df = df[list(col_names.values())]
    # add and transform some columns
    df['ITEM CODE'] = 'JR-' + df['SKU CODE (UNIQUE)']
    df['IMAGE SKU 1'] = df['ITEM CODE']
    df['WHEEL OWNER'] = suppliers_list['JR']
    df['SIZE'] = df['SIZE'].apply(lambda x: re.sub("[^0-9.]", "", x))
    df['J WIDTH'] = df['J WIDTH'].str.replace(',', '.')
    df['J WIDTH'] = df['J WIDTH'].apply(lambda x: re.sub("[^0-9.]", "", x))
    df['PCD'] = df['PCD'].str.replace('x', '/')
    df['PCD'] = df['PCD'].str.replace(', ', '|')
    df['GROUP IDENTIFIER'] = df['BRAND'] + ' ' + df['WHEEL MODEL'] + ' ' + df['COLOUR']
    df['SHIPPING (DOMESTIC)'] = 30
    df['PRICE MARK UP'] = 0
    df['TOTAL UNIQUE PRICE (MSRP + MARGIN)'] = df['MSRP'] + df['PRICE MARK UP']
    df['IMPORT / DISPLAY FILTER'] = 'TRUE'
    df['ET'] = df['ET'].str.replace(', ', '|')
    df['IMAGE SOURCE'] = 'EXTERNAL_1'
    df['STOCK STATUS'] = 'PRE-ORDER'
    df['SIZE DESC'] = df['SIZE'] + 'x' + df['J WIDTH']
    df['CB'] = df['CB'].str.replace(', ', '|')
    return df

# Update the database
def jr_update(url,db_engine,db_table,fn_extr, fn_xfrm):
    # Extract latest product list from suppliers
    df_extr = fn_extr(url)
    # Transform imported supplier product list to fit master stock list
    df_extrxfrm = fn_xfrm(df_extr)
    # Delete values from old supplier list from table
    stmt = delete(db_table).where(db_table.c['WHEEL OWNER'] == suppliers_list['JR'])
    with db_engine.begin() as conn:
        conn.execute(stmt)
    # Load the updated supplier list into the database
    df_extrxfrm.to_sql(db_table.name, con=db_engine, if_exists='append', index=False, chunksize=1024)
    print("Database updated with latest JR products")
