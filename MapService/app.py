from flask import Flask,request
import websocket
import time
import threading
from utils import *
import os
from dotenv import load_dotenv
load_dotenv('./env')
from flask_cors import cross_origin


MY_ACCESS_TOKEN_GEOPS = os.getenv('MY_ACCESS_TOKEN_GEOPS')
MY_ACCESS_TOKEN_FLUCTUO = os.getenv('MY_ACCESS_TOKEN_FLUCTUO')
print(MY_ACCESS_TOKEN_GEOPS)

socket = f"wss://api.geops.io/tracker-ws/v1/?key={MY_ACCESS_TOKEN_GEOPS}"


app = Flask(__name__)





@app.route('/publictransportfull/', methods=['GET', 'POST'])
@cross_origin()
def get_full_vehicle_data():
    
    data = request.get_json()

    b = data['bbox']
    z = data['zoom']

    bb = [float(value) for value in b.split(',')]
    bb_epsg_4326 = [bb[1], bb[0], bb[3], bb[2]]

    bb_epsg_3857 = ["null", "null", "null", "null"]
    bb_epsg_3857[1], bb_epsg_3857[0] = convert_coordinates(bb[0], bb[1], from_crs='EPSG:4326', to_crs='EPSG:3857')
    bb_epsg_3857[3], bb_epsg_3857[2] = convert_coordinates(bb[2], bb[3], from_crs='EPSG:4326', to_crs='EPSG:3857')
    BBOX = f"BBOX {' '.join(str(int(value)) for value in bb_epsg_3857)} {z}"
    print(BBOX)

    log_list = []

    def on_open(ws):
        ws.send(BBOX)

    def on_message(ws, message):
        log_list.append(message)

    def on_close(ws, code, reason):
        print("WebSocket connection closed")

    def close_websocket(ws):
        time.sleep(2)
        ws.close()

    ws = websocket.WebSocketApp(socket, on_open=on_open, on_message=on_message, on_close=on_close)
    ws_thread = threading.Thread(target=ws.run_forever)
    ws_thread.start()

    close_thread = threading.Thread(target=close_websocket, args=(ws,))
    close_thread.start()

    close_thread.join()
    print(log_list)
    log_processor = LogProcessor(log_list, MY_ACCESS_TOKEN_GEOPS)
    df = log_processor.process_logs()
    if df.empty:
        json_data={}
        print("DataFrame is empty")
    else:
        # Group by 'content.properties.line.name' and sort by 'content.properties.timestamp'
        sorted_df = df.groupby(df['content.properties.line.name']).apply(lambda x: x.sort_values('content.properties.timestamp', ascending=False))
        # Select only the first row for each group
        result = sorted_df.groupby(sorted_df['content.properties.line.name']).head(1)
        # Reset the index
        result = result.reset_index(drop=True)
        
        df = log_processor.fetch_journey_data(result)
        columns = ['content.geometry.coordinates', 'geometry.geometries.LineString', 'geometry.geometries.MultiPoint']
        # Convert the coordinates in the specified columns
        df = log_processor.convert_dataframe_coordinates(df, columns)
        json_data = log_processor.to_json(df)
        json_data=json.dumps(json_data)
        # Save the JSON data to a file
        with open('public_transport.json', 'w') as file:
            json.dump(json_data, file)
    return json_data





@app.route('/beta/cb-realtime/publictransport/', methods=['GET', 'POST'])
@cross_origin()
def get_vehicle_data():
    
    data = request.get_json()

    b = data['bbox']
    z = data['zoom']

    bb = [float(value) for value in b.split(',')]
    bb_epsg_4326 = [bb[1], bb[0], bb[3], bb[2]]

    bb_epsg_3857 = ["null", "null", "null", "null"]
    bb_epsg_3857[1], bb_epsg_3857[0] = convert_coordinates(bb[0], bb[1], from_crs='EPSG:4326', to_crs='EPSG:3857')
    bb_epsg_3857[3], bb_epsg_3857[2] = convert_coordinates(bb[2], bb[3], from_crs='EPSG:4326', to_crs='EPSG:3857')
    BBOX = f"BBOX {' '.join(str(int(value)) for value in bb_epsg_3857)} {z}"
    print(BBOX)

    log_list = []

    def on_open(ws):
        ws.send(BBOX)

    def on_message(ws, message):
        log_list.append(message)

    def on_close(ws, code, reason):
        print("WebSocket connection closed")

    def close_websocket(ws):
        time.sleep(2)
        ws.close()

    ws = websocket.WebSocketApp(socket, on_open=on_open, on_message=on_message, on_close=on_close)
    ws_thread = threading.Thread(target=ws.run_forever)
    ws_thread.start()

    close_thread = threading.Thread(target=close_websocket, args=(ws,))
    close_thread.start()

    close_thread.join()
    # print(log_list)
    log_processor = LogProcessor(log_list, MY_ACCESS_TOKEN_GEOPS)
    df = log_processor.process_logs()
    if df.empty:
        json_data={}
        print("DataFrame is empty")
    else:
        # Group by 'content.properties.line.name' and sort by 'content.properties.timestamp'
        sorted_df = df.groupby(df['content.properties.line.name']).apply(lambda x: x.sort_values('content.properties.timestamp', ascending=False))
        # Select only the first row for each group
        result = sorted_df.groupby(sorted_df['content.properties.line.name']).head(1)
        # Reset the index
        result = result.reset_index(drop=True)
        columns = ['content.geometry.coordinates']
        # Convert the coordinates in the specified columns
        result = log_processor.convert_dataframe_coordinates(result, columns)

        json_data = log_processor.to_json(result)
        json_data=json.dumps(json_data)
        # # Save the JSON data to a file
        # with open('public_transport.json', 'w') as file:
        #     json.dump(json_data, file)
    return json_data





@app.route('/beta/cb-realtime/privatetransport/', methods=['GET', 'POST'])
@cross_origin()
def private_transport():
    variables = request.get_json()
    # set the endpoint URL and access token
    url = r"https://flow-api.fluctuo.com/v1?access_token={}".format(MY_ACCESS_TOKEN_FLUCTUO)

    # define the GraphQL query and variables
    query = """
        query ($lat: Float!, $lng: Float!) {
    vehicles (lat: $lat, lng: $lng) {
        id  
        type
        publicId
        provider {
        slug
        }
        lat
        lng
        propulsion
        battery
        attributes
        ... on Station {
        isVirtual
        availableVehicles
        availableStands
        stationVehicleDetails {
            vehicleType
            propulsion
            availableVehicles
        }
        vehicles {
            id
            publicId
            type
            propulsion
            battery
        }
        }


    }
    }
    """
    # variables = {
    #     "lat": 45.486460, 
    #     "lng": 9.125737
    # }

    # set the request headers
    headers = {
        # "Authorization": "Bearer " + access_token,
        "content-type": "application/json"
    }

    # send the POST request to the endpoint
    response = requests.post(url, headers=headers, json={
        "query": query,
        "variables": variables
    })
    
    # with open('private_transport.json', 'w') as file:
    #     json.dump(response.json(), file)
    # print the response
    return response.json()

if __name__ == '__main__':
    app.run()


45.127055490565446,7.714534030655944,45.126979435153345,7.7150101377565266
