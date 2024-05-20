import json
import pandas as pd
import requests
import pyproj
import asyncio
import aiohttp
import concurrent.futures


def convert_coordinates(x, y, from_crs='EPSG:3857', to_crs='EPSG:4326'):
    # Define the input and output coordinate reference systems (CRS)
    crs_from = pyproj.CRS(from_crs)
    crs_to = pyproj.CRS(to_crs)

    # Create a transformer object to perform the conversion
    transformer = pyproj.Transformer.from_crs(crs_from, crs_to, always_xy=True)

    # Perform the coordinate transformation
    lon, lat = transformer.transform(x, y)

    # Return the converted coordinates as a tuple
    return lat,lon

def find_bounding_box_center(bbox):
    """
    Finds the center coordinates of a bounding box.

    Args:
        bbox (list): List of coordinates representing the bounding box in the format [latitude1, longitude1, latitude2, longitude2].

    Returns:
        dict: The center latitude and longitude coordinates as a tuple.

    """
    assert len(bbox) == 4, "Bounding box should contain exactly four coordinates."

    # Split the bbox coordinates into latitude (Y) and longitude (X) values
    latitudes = bbox[::2]  # Extract the latitude values from the bbox list
    longitudes = bbox[1::2]  # Extract the longitude values from the bbox list

    # Calculate the average of the latitude values
    center_latitude = sum(latitudes) / len(latitudes)

    # Calculate the average of the longitude values
    center_longitude = sum(longitudes) / len(longitudes)

    # Return the center coordinates as a tuple
    return  {"lat": center_latitude, "lng": center_longitude}

def get_vehicle_data(variables):
    """
    Fetches vehicle data from the API using GraphQL query.

    Args:
        variables (dict): Dictionary containing 'lat' and 'lng' coordinates.
        access_token (str): Access token for API authentication.

    Returns:
        dict: Response JSON containing vehicle data.
    """
    access_token = "i41nEp9J2zScKshxtL9SbhfxrBpzCIhv"
    # Set the endpoint URL and access token
    url = r"https://flow-api.fluctuo.com/v1?access_token={}".format(access_token)

    # Define the GraphQL query
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

    # Set the request headers
    headers = {
        "content-type": "application/json"
    }

    # Send the POST request to the endpoint
    response = requests.post(url, headers=headers, json={
        "query": query,
        "variables": variables
    })

    # Return the response JSON
    return response.json()

class LogProcessor:
    def __init__(self, log_list, access_token):
        self.log_list = log_list
        self.access_token = access_token
        self.valid_lines = []

    def create_nested_dict(self, row, column_name, value):
        if '.' in column_name:
            main_node, subnodes = column_name.split('.', 1)
            if main_node not in row:
                row[main_node] = {}
            self.create_nested_dict(row[main_node], subnodes, value)
        else:
            row[column_name] = value
        

    def process_logs(self):
        # columns = ['content.geometry.type', 'content.geometry.coordinates', 'content.properties.bounds',
        #             'content.properties.gen_range', 'content.properties.tenant', 'content.properties.type',
        #             'content.properties.time_intervals', 'content.properties.train_id',
        #             'content.properties.event_timestamp', 'content.properties.line.id',
        #             'content.properties.line.name', 'content.properties.line.color',
        #             'content.properties.line.text_color', 'content.properties.line.stroke',
        #             'content.properties.timestamp', 'content.properties.state',
        #             'content.properties.route_identifier', 'content.properties.delay']
        for line in self.log_list:
            try:
                data = json.loads(line)
                if data["source"] == "trajectory":
                    self.valid_lines.append(data)
            except json.JSONDecodeError:
                continue
        try:
            df = pd.json_normalize(self.valid_lines)
            # df = df[columns]
            
        except Exception as e:
            print(f"Error occurred during data normalization: {e}")
            # df = pd.DataFrame(columns=columns)

        return df
    
    def extract_geometries(self,row):
        line_string = None
        multi_point = None
        
        for geom in row['geometry.geometries']:
            # print(geom)
            if geom['type'] == 'LineString':
                line_string = geom['coordinates']
            elif geom['type'] == 'MultiPoint':
                multi_point = geom['coordinates']
        # print(multi_point)
        # print(line_string)
        return pd.Series({'geometry.geometries.LineString': line_string, 
                        'geometry.geometries.MultiPoint': multi_point})

    def convert_dataframe_coordinates(self, df, columns):
        try:
            # Iterate over the specified columns
            for column in columns:
                # Apply the conversion function to each value in the column
                df[column] = df[column].apply(lambda coordinates: [
                    convert_coordinates(x, y) for x, y in coordinates
                ])

            return df
        except Exception as e:
            print(f"Error occurred during converting dataframe coordinates: {e}")
            return df
    
    import pyproj




    def fetch_journey_data(self,df):
        base_url = "https://api.geops.io/tracker-http/v1/journeys/"
        columns = ["properties.publisher", "properties.publisherUrl", "properties.operator", "properties.operatorUrl",
                "properties.train_id", "geometry.geometries"]
        df_to_fill = pd.DataFrame(columns=columns)

        for train_id in df['content.properties.train_id']:
            try:
                url = f"{base_url}{train_id}/"
                headers = {
                    'accept': 'application/json',
                    'Authorization': self.access_token
                }
                response = requests.get(url, headers=headers)

                if response.status_code == 200:
                    data = response.json()
                    df_full = pd.json_normalize(data)
                    df_features = pd.json_normalize(df_full.explode(["features"])["features"])
                    merged_df = pd.merge(df_full[["properties.publisher", "properties.publisherUrl", "properties.operator",
                                                "properties.operatorUrl", "properties.train_id"]],
                                        df_features[["geometry.geometries", "properties.train_id"]],
                                        on="properties.train_id")
                    df_to_fill = pd.concat([df_to_fill, merged_df], ignore_index=True)
                else:
                    print(f"Error: {response.status_code} - {response.text}")
            except Exception as e:
                print(f"Error occurred during fetching journey data: {e}")

        try:
            df = pd.merge(df, df_to_fill, left_on='content.properties.train_id',
                                right_on='properties.train_id')
            df[['geometry.geometries.LineString', 'geometry.geometries.MultiPoint']] = df.apply(self.extract_geometries, axis=1)
            df.drop(['properties.train_id','geometry.geometries'], axis=1, inplace=True)
        except Exception as e:
            print(f"Error occurred during merging and processing journey data: {e}")

        return df
    
    
    # def fetch_journey_data(self,df):
    #     base_url = "https://api.geops.io/tracker-http/v1/journeys/"
    #     columns = ["properties.publisher", "properties.publisherUrl", "properties.operator", "properties.operatorUrl",
    #                "properties.train_id", "geometry.geometries"]
    #     df_to_fill = pd.DataFrame(columns=columns)

    #     for train_id in df['content.properties.train_id']:
    #         url = f"{base_url}{train_id}/"
    #         headers = {
    #             'accept': 'application/json',
    #             'Authorization': self.access_token
    #         }
    #         response = requests.get(url, headers=headers)

    #         if response.status_code == 200:
    #             data = response.json()
    #             df_full = pd.json_normalize(data)
    #             df_features = pd.json_normalize(df_full.explode(["features"])["features"])
    #             merged_df = pd.merge(df_full[["properties.publisher", "properties.publisherUrl", "properties.operator",
    #                                           "properties.operatorUrl", "properties.train_id"]],
    #                                  df_features[["geometry.geometries", "properties.train_id"]],
    #                                  on="properties.train_id")
    #             df_to_fill = pd.concat([df_to_fill, merged_df], ignore_index=True)
    #         else:
    #             print(f"Error: {response.status_code} - {response.text}")

    #     df = pd.merge(df, df_to_fill, left_on='content.properties.train_id',
    #                          right_on='properties.train_id')
    #     df[['geometry.geometries.LineString', 'geometry.geometries.MultiPoint']] = df.apply(self.extract_geometries, axis=1)
    #     df.drop(['properties.train_id','geometry.geometries'], axis=1, inplace=True)
    #     return df

    def to_json(self,df):
        json_list = []
        for _, row in df.iterrows():
            json_obj = {}
            for column_name, value in row.items():
                self.create_nested_dict(json_obj, column_name, value)
            json_list.append(json_obj)

        return json_list

