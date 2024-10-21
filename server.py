import sys
import asyncio
import json
import aiohttp
import time
from settings import PORTS, neighbors, API_KEY, clients





async def query_google_places(places_key, query_location, search_radius: float, max_results):
    search_radius_meters = int(search_radius * 1000)
    places_url = f"https://maps.googleapis.com/maps/api/place/nearbysearch/json?key={places_key}&location={query_location}&radius={search_radius_meters}"
    await log_activity(f"Initiating Google Places fetch: {places_url}")
    async with aiohttp.ClientSession() as web_session:
        return await fetch_response(web_session, places_url, max_results)

async def fetch_response(web_session, request_url, result_limit):
    async with web_session.get(request_url) as web_response:
        parsed_response = await web_response.json()
        truncated_results = truncate_results(parsed_response, result_limit)
        return truncated_results

def truncate_results(response_data, limit):
    response_data['results'] = response_data['results'][:int(limit)]
    return response_data

async def log_activity(message):
    log_message = f"Google Places API request: {message}"
    await record_activity(log_message)


async def process_whatsat_request(client_writer, command_args):
    log_identifier = 'WHATSAT Request Handled'
    await log_event(log_identifier)
    
    if len(command_args) != 4:
        raise InvalidCommandException("Invalid number of arguments.")
    
    client_key = command_args[1]
    probe_radius = float(command_args[2])
    info_limit = int(command_args[3])
    
    if client_key not in clients:
        raise InvalidCommandException("Client not recognized.")
    
    if info_limit > 20:
        raise InvalidCommandException("Information limit exceeds bounds.")
    
    client_record = clients[client_key]
    host_server = client_record['server_identifier']
    client_lat = client_record['latitude']
    client_lon = client_record['longitude']
    latitude_corrected = client_lat[1:] if client_lat[0] == '+' else client_lat
    longitude_corrected = client_lon[1:] if client_lon[0] == '+' else client_lon

    location_data = await query_google_places(API_KEY, f"{latitude_corrected},{longitude_corrected}", probe_radius, info_limit)
    location_data_json = json.dumps(location_data, indent=4).replace("\n\n", "\n").rstrip("\n")
    
    temporal_difference = client_record['time_difference']
    composed_location = f"{client_lat}{client_lon}"
    at_response = f"AT {host_server} {temporal_difference} {client_key} {composed_location} {client_record['cmd_time']}"
    full_response = f"{at_response}\n{location_data_json}\n\n"
    
    await reply_to_client(client_writer, full_response)

async def log_event(action_detail):
    # Assuming record_activity is already defined and adds a timestamp
    await record_activity(f"Action Logged: {action_detail}")

async def reply_to_client(comms_writer, reply_text):
    # Encode the reply text to bytes and ensure it's sent to the client
    comms_writer.write(reply_text.encode('utf-8'))
    await comms_writer.drain()  # Confirm all outgoing data is transmitted
    
    # Attempt to close the communication channel gracefully
    try:
        comms_writer.write_eof()  # Signifies the end of the reply
    except Exception as error:
        # Log any error during the closing phase (Define `log_error` based on your logging mechanism)
        await record_activity(f"Closing writer error: {error}")
    finally:
        # Ensure the writer is closed properly
        if not comms_writer.is_closing():
            comms_writer.close()
        await comms_writer.wait_closed()


# Ensure InvalidCommandException is defined
class InvalidCommandException(Exception):
    """Exception for invalid commands."""
    pass

# Note: The function query_google_places is assumed to be refactored as described in the previous step.

 

async def process_iamat_command(responder, command_details, current_time):
    log_message = 'Processing IAMAT command'
    await log_activity(log_message)
    
    if len(command_details) != 4:
        await log_activity("IAMAT command format error")
        raise InvalidCommandException

    user_identifier = command_details[1]
    user_location = command_details[2]
    user_timestamp = float(command_details[3])
    time_offset = calculate_time_offset(current_time, user_timestamp)

    response_message = compose_at_response(server_identifier, time_offset, user_identifier, user_location, user_timestamp)
    await finalize_client_communication(responder, response_message)

    latitude, longitude = extract_coordinates(user_location)
    update_client_record(user_identifier, server_identifier, latitude, longitude, time_offset, user_timestamp)

    await log_activity(f"Updated records for {user_identifier}")
    await distribute_update(user_identifier)

async def process_at_command(responder, command_parameters):
    log_message = 'Processing AT command'
    await log_activity(log_message)
    
    if len(command_parameters) != 6:
        await log_activity("AT command format error")
        raise InvalidCommandException

    origin_server = command_parameters[1]
    time_difference = command_parameters[2]
    client_key = command_parameters[3]
    user_coords = command_parameters[4]
    timestamp_of_command = float(command_parameters[5])

    latitude, longitude = [part.strip(',') for part in extract_coordinates(user_coords)]
    if should_update_client_info(client_key, timestamp_of_command):
        update_client_record(client_key, origin_server, latitude, longitude, time_difference, timestamp_of_command)
        await log_activity(f"Client {client_key} info updated from AT command")
        await distribute_update(client_key)

def calculate_time_offset(server_current_time, client_sent_time):
    offset = server_current_time - client_sent_time
    return f"+{offset:.9f}" if offset >= 0 else f"{offset:.9f}"

def compose_at_response(server_identifier, offset, client_id, location, timestamp):
    return f"AT {server_identifier} {offset} {client_id} {location} {timestamp}"

def extract_coordinates(location_str):
    separator_index = max(location_str.find('+', 1), location_str.find('-', 1))
    return location_str[:separator_index], location_str[separator_index:]

def update_client_record(client_id, server, lat, lon, time_diff, cmd_time):
    clients[client_id] = {
        'server_identifier': server,
        'latitude': lat,
        'longitude': lon,
        'time_difference': time_diff,
        'cmd_time': cmd_time
    }

def should_update_client_info(client_id, new_timestamp):
    return client_id not in clients or float(clients[client_id]['cmd_time']) < new_timestamp

async def log_activity(activity_detail):
    # Assuming a generic logging function exists
    await record_activity(activity_detail)

async def finalize_client_communication(client_stream, message):
    # Prepares the message for transmission by encoding
    encoded_message = message.encode('utf-8')

    # Tries to send the encoded message, awaits to ensure it's fully sent
    try:
        client_stream.write(encoded_message)
        await client_stream.drain()  # Ensures the message is completely sent before proceeding
    except Exception as communication_error:
        await record_error(f"Error during message sending: {communication_error}")
    finally:
        # Attempt to close the communication stream safely
        try:
            client_stream.close()
            await client_stream.wait_closed()  # Waits until the stream is confirmed closed
        except Exception as closure_error:
            await record_error(f"Stream closure error: {closure_error}")

async def record_error(error_msg):
    # Function to log errors, adapt to your current logging mechanism
    print(f"Error: {error_msg}")  # Placeholder for actual logging


# Assuming the distribute_update function is correctly defined elsewhere and propagates updates as required




    
async def distribute_update(client_id):
    if client_id not in clients:
        await record_activity(f'Error: Client {client_id} not found for update distribution.')
        raise InvalidCommandException
    client_data = clients[client_id]
    update_msg = f"AT {client_data['server_identifier']} {client_data['time_difference']} {client_id} {client_data['latitude']},{client_data['longitude']} {client_data['cmd_time']}"
    for neighbor in neighbors[client_data['server_identifier']]:
        try:
            await send_update_to_neighbor(update_msg, PORTS[neighbor])
        except ConnectionRefusedError:
            await record_activity(f'Failed to connect and send update to neighbor {neighbor}.')

async def send_update_to_neighbor(message, port):
    _, writer = await asyncio.open_connection('127.0.0.1', port)
    await reply_to_client(writer, message)

    
    

def parse_coordinates(coordinate_str):
    for idx, char in enumerate(coordinate_str[1:], start=1):
        if char in "+-":
            return [coordinate_str[:idx], coordinate_str[idx:]]
    return [coordinate_str, ""]  # Fallback in case of unexpected format

    
async def manage_client_interaction(data_reader, data_writer):
    interaction_timestamp = time.time()
    await record_activity("New client interaction initiated")

    received_data = await data_reader.read(1024)
    decoded_command = received_data.decode().strip()

    if not decoded_command:
        data_writer.close()
        await data_writer.wait_closed()
        return

    await record_activity(f"Command received: {decoded_command}")
    command_elements = decoded_command.split()

    try:
        command_type = command_elements[0]
        match command_type:
            case 'IAMAT':
                await process_iamat_command(data_writer, command_elements, interaction_timestamp)
            case 'WHATSAT':
                await process_whatsat_request(data_writer, command_elements)
            case 'AT':
                await process_at_command(data_writer, command_elements)
            case _:
                raise InvalidCommandException
    except InvalidCommandException:
        error_response = f"? {decoded_command}"
        await record_activity("Invalid or unrecognized command")
        await finalize_client_communication(data_writer, error_response)
    except Exception as general_error:
        await record_activity(f"Error handling command: {general_error}")
    finally:
        data_writer.close()
        await data_writer.wait_closed()

# Assume process_iamat_command, execute_whatsat, and execute_at are refactored versions of process_iamat_command, process_whatsat_request, and process_at_command.


class InvalidCommandException(Exception):
    pass


async def dispatch_message(channel, text):
    encoded_text = text.encode('utf-8')
    channel.write(encoded_text)
    await channel.drain()  # Ensure all data is sent before closing
    try:
        channel.write_eof()  # Signal the end of the message
    except Exception as e:
        await log_event(f"Failed to close channel properly: {e}")
    finally:
        await channel.wait_closed()  # Make sure the writer is closed properly


async def main():
    if len(sys.argv) != 2:
        exit()

    global server_identifier
    server_identifier = sys.argv[1]

    if server_identifier not in PORTS:

        exit()
	
    log = server_identifier + "_log.txt"
    global logFile
    open(log, "w").close()

    server = await asyncio.start_server(manage_client_interaction, '127.0.0.1', PORTS[server_identifier])

    addrs = ', '.join(str(sock.getsockname()) for sock in server.sockets)
    await record_activity(f'Serving on {addrs}')

    async with server:
        await server.serve_forever()
	
	
async def record_activity(activity):
    log_path = f"{server_identifier}_activity_record.log"
    try:
        # Opening the file in append mode and writing the activity message
        with open(log_path, "a", encoding="utf-8") as activity_log:
            activity_log.write(f"{activity}\n")
    except Exception as e:
        # In case of an error, print to stderr or handle it as per your logging framework
        print(f"Error logging activity: {e}", file=sys.stderr)



if __name__ == '__main__':
    # print(split_latlong('+34.068930-118.445127'))
    asyncio.run(main())
