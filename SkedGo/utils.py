import requests
import json
import numpy as np
import pandas as pd
import polyline
import datetime
import pandas as pd

def filter_highest_weighted_score(group):
    highest_score = group["weightedScore"].max()
    return group[group["weightedScore"] == highest_score]


def process_data(j_data):
    groups_df = pd.DataFrame(j_data['groups'])
    groups_df = groups_df.explode("trips")
    groups_df['group'] = groups_df.index
    groups_df = groups_df.reset_index()
    groups_df = groups_df[['group', 'trips']]

    trips_df = pd.json_normalize(groups_df['trips'])
    trips_df = trips_df[["id","segments","depart","arrive","weightedScore"]]
    trips_df = trips_df.rename(columns={"id": "trip_id"})

    groups_df = pd.concat([groups_df.drop('trips', axis=1), trips_df], axis=1)
    groups_df = groups_df.explode("segments").reset_index()

    filtered_df = groups_df.groupby("group").apply(filter_highest_weighted_score).reset_index(drop=True)
    groups_df = filtered_df.copy()

    normalized_segments = pd.json_normalize(groups_df['segments'])
    normalized_segments = normalized_segments.add_prefix('segments.')

    groups_df = pd.concat([groups_df.drop(['index','segments'], axis=1), normalized_segments], axis=1)

    segmentTemplates_df = pd.json_normalize(j_data['segmentTemplates'])
    segmentTemplates_df = decode_polyline(segmentTemplates_df)

    joined_df = groups_df.merge(segmentTemplates_df,
                                left_on='segments.segmentTemplateHashCode',
                                right_on='segments.hashCode',
                                how='left')

    return joined_df


def decode_polyline(segmentTemplates_df):
    try:
        for i, value in enumerate(segmentTemplates_df["streets"]):
            if value is not np.nan:
                for item in value:
                    encoded_waypoints = item['encodedWaypoints']
                    decoded_waypoints = polyline.decode(encoded_waypoints)
                    item['encodedWaypoints'] = decoded_waypoints
    except:
        pass

    try:
        for i, value in enumerate(segmentTemplates_df["shapes"]):
            if value is not np.nan:
                for item in value:
                    encoded_waypoints = item['encodedWaypoints']
                    decoded_waypoints = polyline.decode(encoded_waypoints)
                    item['encodedWaypoints'] = decoded_waypoints
    except:
        pass

    segmentTemplates_df = segmentTemplates_df.add_prefix('segments.')
    return segmentTemplates_df


def datetime_to_timestamp(datetime_str):
    # Parse the datetime string
    dt = datetime.datetime.strptime(datetime_str, "%Y-%m-%dT%H:%M:%S")

    # Convert the datetime to UTC
    dt_utc = dt.astimezone(datetime.timezone.utc)

    # Calculate the timestamp in seconds
    timestamp = int(dt_utc.timestamp())

    return timestamp


def convert_timestamp_columns(df):
    try:
        # Find the timezone
        timezone = df['segments.from.timezone'][df['segments.from.timezone'].first_valid_index()]

        # Convert 'depart' column
        try:
            df['depart'] = pd.to_datetime(df['depart'], unit='s').dt.tz_localize('UTC').dt.tz_convert(timezone).dt.strftime('%Y-%m-%d %H:%M:%S')
        except Exception as e:
            print(f"An error occurred during 'depart' column conversion: {str(e)}")

        # Convert 'arrive' column
        try:
            df['arrive'] = pd.to_datetime(df['arrive'], unit='s').dt.tz_localize('UTC').dt.tz_convert(timezone).dt.strftime('%Y-%m-%d %H:%M:%S')
        except Exception as e:
            print(f"An error occurred during 'arrive' column conversion: {str(e)}")

        # Convert 'segments.endTime' column
        try:
            df['segments.endTime'] = pd.to_datetime(df['segments.endTime'], unit='s').dt.tz_localize('UTC').dt.tz_convert(timezone).dt.strftime('%Y-%m-%d %H:%M:%S')
        except Exception as e:
            print(f"An error occurred during 'segments.endTime' column conversion: {str(e)}")

        # Convert 'segments.startTime' column
        try:
            df['segments.startTime'] = pd.to_datetime(df['segments.startTime'], unit='s').dt.tz_localize('UTC').dt.tz_convert(timezone).dt.strftime('%Y-%m-%d %H:%M:%S')
        except Exception as e:
            print(f"An error occurred during 'segments.startTime' column conversion: {str(e)}")

    except Exception as e:
        print(f"An error occurred during timestamp conversion: {str(e)}")

    return df

def create_nested_dict( row, column_name, value):
        if '.' in column_name:
            main_node, subnodes = column_name.split('.', 1)
            if main_node not in row:
                row[main_node] = {}
            create_nested_dict(row[main_node], subnodes, value)
        else:
            row[column_name] = value

def to_json(df):
        json_list = []
        for _, row in df.iterrows():
            json_obj = {}
            for column_name, value in row.items():
                create_nested_dict(json_obj, column_name, value)
            json_list.append(json_obj)

        return json_list

class NpEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super(NpEncoder, self).default(obj)

def create_new_frame(joined_df, arrive_col, depart_col, prefix=''):
    # Convert the 'arrive' and 'depart' columns to datetime data type
    joined_df[arrive_col] = pd.to_datetime(joined_df[arrive_col])
    joined_df[depart_col] = pd.to_datetime(joined_df[depart_col])

    # Create a new DataFrame by concatenating all columns
    newframe = pd.concat([
        joined_df,
        (joined_df[arrive_col] - joined_df[depart_col]).dt.total_seconds() / 60
    ], axis=1)

    # Assign appropriate column names
    new_column_name = prefix + 'duration'
    newframe.columns = [*joined_df.columns, new_column_name]

    # Convert column types
    newframe[new_column_name] = newframe[new_column_name].astype(int)
    newframe[arrive_col] = newframe[arrive_col].astype(str)
    newframe[depart_col] = newframe[depart_col].astype(str)

    return newframe

def convert_dataframe_to_json(joined_df):
    # Grouping and converting to JSON
    joined_df = joined_df.fillna("nan")
    joined_df = create_new_frame(joined_df, arrive_col='arrive', depart_col='depart', prefix='')
    joined_df = create_new_frame(joined_df, arrive_col='segments.endTime', depart_col='segments.startTime', prefix='segments.')
    
    # Grouping and converting to JSON
    grouped = joined_df.groupby(['group', 'trip_id'])
    
    # Grouping and converting to JSON
    grouped = joined_df.groupby(['group', 'trip_id', 'depart', 'arrive','duration', 'weightedScore'])


    result = []
    for key, group in grouped:
        group_data = group.drop(columns=['group', 'trip_id', 'depart', 'arrive','duration', 'weightedScore'])
        group_data = group_data.groupby(['segments.id'])
        segments=[]
        for i, seg in group_data:
            seg_data = seg.drop(columns=["segments.id"])
            j_d=to_json(seg_data)[0]['segments']
            seg_json = {
                "segment_id": i[0],
                "segment_data": j_d
            }
            segments.append(seg_json)
        
        # Sort the list of dictionaries by "startTime"
        segments_sorted = sorted(segments, key=lambda x: x['segment_data']['startTime'])

        group_dict = {
            "group": key[0],
            "trip_id": key[1],
            "depart": key[2],
            "arrive": key[3],
            "duration": key[4],
            "weightedScore": key[5],
            "segments": segments_sorted
        }
        result.append(group_dict)

    return json.dumps(result, cls=NpEncoder,indent=4)

def get_trip(api_key, trip_id):
    url = f"https://api.tripgo.com/v1/trip/{trip_id}"
    headers = {"X-TripGo-Key": api_key}
    headers["Content-Type"] = "application/json"

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        try:
            return response.json()
        except json.JSONDecodeError:
            print("Error: Invalid JSON response.")
            return None
    else:
        print(f"Error: Request failed with status code {response.status_code}.")
        return None

class APIHandler:
    def __init__(self,api_key):
        self.api_key = api_key

    def make_api_request(self, params):
        api_url = self._build_api_url(params)
        # print(api_url)
        response = self._send_api_request(api_url)
        json_data = None

        if response.status_code == 200:
            j_data = json.loads(response.text)
            # json_data = self._process_response(j_data)
        else:
            print("Error:", response.status_code, response.text)

        return j_data
    
    def _modify_params(self, params):
        wp_string = "(1,1,1,1)" # Set the default value of wp_string
        if "wp" in params: # Check if there is "wp" node in params
            wp_list = params["wp"] # Get the value of "wp" node, which should be a list
            for i, value in enumerate(wp_list): # Loop over the elements of the list
                if value == "CHEAPEST": # Check if the element is CHEAPEST
                    wp_string = "(2," + wp_string[3:] # Substitute the second character of wp_string with "2"
                elif value == "ECOFRIENDLY": # Check if the element is ECOFRIENDLY
                    wp_string = wp_string[:3] + "2" + wp_string[4:] # Substitute the fourth character of wp_string with "2"
                elif value == "FASTEST": # Check if the element is FASTEST
                    wp_string = wp_string[:5] + "2" + wp_string[6:] # Substitute the sixth character of wp_string with "2"
                elif value == "SHORTEST": # Check if the element is SHORTEST
                    wp_string = wp_string[:7] + "2)" # Substitute the eighth character of wp_string with "2"
            params["wp"] = wp_string # Substitute the value of "wp" node in params with wp_string

        if "arriveBefore" in params:
            params["arriveBefore"] = datetime_to_timestamp(params["arriveBefore"])

        return params # Return the modified params
    
    def _build_api_url(self, params):
        base_url = "https://api.tripgo.com/v1/routing.json?v=11"
        url_params = []
        params = self._modify_params(params)
        for key, value in params.items():
            if key == "modes":
                for item in value:
                    url_params.append(f"modes={item}")
            else:
                url_params.append(f"{key}={value}")

        url = base_url + "&" + "&".join(url_params)
        print(url)
        return url

    def _send_api_request(self, api_url):
        return requests.get(api_url, headers={"X-TripGo-Key": self.api_key})