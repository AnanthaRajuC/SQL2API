import mysql.connector
import json
import os
import uuid
import xml.etree.ElementTree as ET
import yaml
import csv
from datetime import datetime
from flask import Flask, request, jsonify, Response
from datetime import datetime
from io import BytesIO, StringIO
from openpyxl import Workbook

app = Flask(__name__)

class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.strftime('%Y-%m-%d %H:%M:%S')
        return json.JSONEncoder.default(self, obj)

class ResultSetDTO:
    def __init__(self, result_set):
        self.result_set = result_set

    def to_csv(self):
        csv_data = StringIO()
        csv_writer = csv.DictWriter(csv_data, fieldnames=self.result_set[0].keys(), delimiter=',')
        csv_writer.writeheader()
        csv_writer.writerows(self.result_set)
        return Response(csv_data.getvalue(), mimetype='text/csv')

    def to_tsv(self):
        tsv_data = StringIO()
        tsv_writer = csv.DictWriter(tsv_data, fieldnames=self.result_set[0].keys(), delimiter='\t')
        tsv_writer.writeheader()
        tsv_writer.writerows(self.result_set)
        return Response(tsv_data.getvalue(), mimetype='text/tab-separated-values')

    def to_xml(self):
        root = ET.Element('data')
        for row in self.result_set:
            item = ET.SubElement(root, 'item')
            for key, value in row.items():
                sub_element = ET.SubElement(item, key)
                sub_element.text = str(value)
        xml_data = ET.tostring(root, encoding='unicode', method='xml')
        return Response(xml_data, mimetype='application/xml')

    def to_yaml(self):
        yaml_data = yaml.dump(self.result_set, default_flow_style=False)
        return Response(yaml_data, mimetype='application/x-yaml')

    def to_xlsx(self):
        wb = Workbook()
        ws = wb.active
        ws.append(list(self.result_set[0].keys()))
        for row in self.result_set:
            ws.append(list(row.values()))
        excel_data = BytesIO()
        wb.save(excel_data)
        return Response(
            excel_data.getvalue(),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={'Content-Disposition': 'attachment;filename=result.xlsx'}
        )

def execute_sql(sql):
    try:
        connection = mysql.connector.connect(
            host="localhost",
            user="admin",
            password="password",
            database="streaming_etl_db"
        )

        if connection.is_connected():
            cursor = connection.cursor(dictionary=True)
            cursor.execute(sql)
            result_set = cursor.fetchall()
            return ResultSetDTO(result_set)
    except mysql.connector.Error as error:
        print("Error while connecting to MySQL", error)
        return {"error": "Error while connecting to MySQL", "status": 500}
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()

@app.route('/view_file_content', methods=['GET'])
def view_file_content():
    filename = request.args.get('filename')

    if not filename:
        return jsonify({'error': 'Filename is missing'}), 400

    if not os.path.exists(filename):
        return jsonify({'error': 'File not found'}), 404

    with open(filename, 'r') as f:
        content = f.read()

    return jsonify({'content': content}), 200

@app.route('/save_sql_to_file', methods=['POST'])
def save_sql_to_file():
    data = request.get_json()
    sql_query = data.get('sql')
    filename = data.get('filename')

    if not sql_query:
        return jsonify({'error': 'SQL query is missing'}), 400

    if not filename:
        # Generate a unique filename using a UUID if the filename is not provided
        filename = f"{str(uuid.uuid4())}.sql"

    # Append the current date and time as a prefix to the filename
    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{now}_{filename}"

    # Save the SQL query to a file
    with open(filename, 'w') as f:
        f.write(sql_query)

    # Return a success message with the filename
    return jsonify({'message': 'SQL query saved successfully', 'filename': filename}), 200

@app.route('/execute_sql', methods=['POST'])
def execute_sql_endpoint():
    data = request.get_json()
    sql_query = data.get('sql')

    if not sql_query:
        return jsonify({'error': 'SQL query is missing'}), 400

    result_set_dto = execute_sql(sql_query)

    if isinstance(result_set_dto, dict):
        return jsonify(result_set_dto), result_set_dto.get("status", 500)

    if result_set_dto.result_set:
        output_format = request.args.get('format', 'json')
        if output_format == 'csv':
            return result_set_dto.to_csv()
        elif output_format == 'tsv':
            return result_set_dto.to_tsv()
        elif output_format == 'xml':
            return result_set_dto.to_xml()
        elif output_format == 'yaml':
            return result_set_dto.to_yaml()
        elif output_format == 'xlsx':
            return result_set_dto.to_xlsx()
        else:
            return jsonify(result_set_dto.result_set)
    else:
        return jsonify({'message': 'No results returned'})

@app.route('/execute_sql_with_parameters_from_file', methods=['POST'])
def execute_sql_with_parameters_from_file():
    data = request.get_json()
    filename = data.get('filename')
    placeholders = data.get('placeholders', {})  # Placeholder values as a dictionary

    if not filename:
        return jsonify({'error': 'Filename is missing'}), 400

    if not os.path.exists(filename):
        return jsonify({'error': 'File not found'}), 404

    with open(filename, 'r') as f:
        sql_query = f.read()

    # Print placeholder key and value pairs
    print("Placeholder key-value pairs:")
    for key, value in placeholders.items():
        print(f"{key}: {value}")

    # Replace placeholder text in the SQL query with provided parameter values
    for key, value in placeholders.items():
        placeholder = f"{{{key}}}"
        print(f"Replacing '{placeholder}' with '{str(value)}'")  # Debug print statement
        sql_query = sql_query.replace(placeholder, str(value))

    print("\nFormed SQL query with placeholder replacements:")
    print(sql_query)  # Print the formed SQL query

    result_set_dto = execute_sql(sql_query)

    if isinstance(result_set_dto, dict):
        return jsonify(result_set_dto), result_set_dto.get("status", 500)

    if result_set_dto.result_set:
        output_format = data.get('format')
        if output_format == 'csv':
            return result_set_dto.to_csv()
        elif output_format == 'tsv':
            return result_set_dto.to_tsv()
        elif output_format == 'xml':
            return result_set_dto.to_xml()
        elif output_format == 'yaml':
            return result_set_dto.to_yaml()
        elif output_format == 'xlsx':
            return result_set_dto.to_xlsx()
        else:
            return jsonify(result_set_dto.result_set)
    else:
        return jsonify({'message': 'No results returned'})

@app.route('/execute_sql_from_file', methods=['POST'])
def execute_sql_from_file():
    data = request.get_json()
    filename = data.get('filename')

    if not filename:
        return jsonify({'error': 'Filename is missing'}), 400

    if not os.path.exists(filename):
        return jsonify({'error': 'File not found'}), 404

    with open(filename, 'r') as f:
        sql_query = f.read()

    result_set_dto = execute_sql(sql_query)

    if isinstance(result_set_dto, dict):
        return jsonify(result_set_dto), result_set_dto.get("status", 500)

    if result_set_dto.result_set:
        output_format = data.get('format')
        if output_format == 'csv':
            return result_set_dto.to_csv()
        elif output_format == 'tsv':
            return result_set_dto.to_tsv()
        elif output_format == 'xml':
            return result_set_dto.to_xml()
        elif output_format == 'yaml':
            return result_set_dto.to_yaml()
        elif output_format == 'xlsx':
            return result_set_dto.to_xlsx()
        else:
            return jsonify(result_set_dto.result_set)
    else:
        return jsonify({'message': 'No results returned'})

if __name__ == '__main__':
    app.run(debug=True)
