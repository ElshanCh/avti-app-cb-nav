from flask import Flask, request
from dotenv import load_dotenv
import os
from utils import APIHandler,process_data,convert_timestamp_columns,convert_dataframe_to_json,get_trip
from flask_cors import CORS

load_dotenv('./env')
app = Flask(__name__)
api_key = os.getenv("api_key") 
CORS(app)

@app.route('/beta/cb-journey/skedgo/',methods=['GET', 'POST'])
def index():

    params = request.get_json()
    # params["bestOnly"] = "true"
    try:
        # Existing code
        # print(params)
        handler = APIHandler(api_key)
        j_data = handler.make_api_request(params)

        joined_df = process_data(j_data)    
        joined_df = convert_timestamp_columns(joined_df)
        json_data = convert_dataframe_to_json(joined_df)
        # print(json_data)

    except Exception as e:
        json_data = {}  # Empty json_data
        print("Error:", e)

    return json_data


@app.route('/trip/',methods=['GET', 'POST'])
def trip():
    params = request.get_json()
    return get_trip(api_key,params["trip_id"])

if __name__ == '__main__':
    app.run()


