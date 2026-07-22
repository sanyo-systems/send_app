import logging
import socket
import threading
import time

TEXT_REGISTER_ADDRESS = 0x1F42
TEXT_REGISTER_COUNT = 0x0F
TEXT_BYTE_LENGTH = 30
GROUP_REGISTER_ADDRESS = 0x1F40
GROUP_REGISTER_COUNT = 0x02
CONFIRM_COIL_ADDRESS = 0x0013

_ip_lock_map = {}
_ip_lock_map_guard = threading.Lock()


def normalize_recorder_text(text):
    normalized = str(text).replace("～", "~")
    return normalized.translate(str.maketrans("０１２３４５６７８９", "0123456789"))


def connect_recorder(ip, port, timeout=3):
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.settimeout(timeout)
    client.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    client.connect((ip, port))
    return client


def build_sendbytes(text):
    text = normalize_recorder_text(text)
    packet = bytearray(43)
    packet[0] = 0
    packet[1] = 0
    packet[2] = 0
    packet[3] = 0
    packet[4] = 0
    packet[5] = 0x25
    packet[6] = 0x01
    packet[7] = 0x10
    packet[8] = (TEXT_REGISTER_ADDRESS >> 8) & 0xFF
    packet[9] = TEXT_REGISTER_ADDRESS & 0xFF
    packet[10] = 0x00
    packet[11] = TEXT_REGISTER_COUNT
    packet[12] = TEXT_BYTE_LENGTH

    text_bytes = text.encode("shift_jis")
    if len(text_bytes) > TEXT_BYTE_LENGTH:
        raise ValueError("comment too long (max 30 bytes)")

    for i, value in enumerate(text_bytes):
        packet[13 + i] = value

    return packet


def build_sendbytes2(group_no):
    packet = bytearray(17)
    packet[0] = 0
    packet[1] = 0
    packet[2] = 0
    packet[3] = 0
    packet[4] = 0
    packet[5] = 0x0B
    packet[6] = 0x01
    packet[7] = 0x10
    packet[8] = (GROUP_REGISTER_ADDRESS >> 8) & 0xFF
    packet[9] = GROUP_REGISTER_ADDRESS & 0xFF
    packet[10] = 0x00
    packet[11] = GROUP_REGISTER_COUNT
    packet[12] = 0x04
    packet[13] = 0x00
    packet[14] = group_no
    packet[15] = 0x00
    packet[16] = 0x01
    return packet


def build_sendbytes3():
    packet = bytearray(12)
    packet[0] = 0
    packet[1] = 0
    packet[2] = 0
    packet[3] = 0
    packet[4] = 0
    packet[5] = 0x06
    packet[6] = 0x01
    packet[7] = 0x05
    packet[8] = (CONFIRM_COIL_ADDRESS >> 8) & 0xFF
    packet[9] = CONFIRM_COIL_ADDRESS & 0xFF
    packet[10] = 0xFF
    packet[11] = 0x00
    return packet


def build_read_text_packet():
    packet = bytearray(12)
    packet[0] = 0
    packet[1] = 0
    packet[2] = 0
    packet[3] = 0
    packet[4] = 0
    packet[5] = 0x06
    packet[6] = 0x01
    packet[7] = 0x03
    packet[8] = (TEXT_REGISTER_ADDRESS >> 8) & 0xFF
    packet[9] = TEXT_REGISTER_ADDRESS & 0xFF
    packet[10] = 0x00
    packet[11] = TEXT_REGISTER_COUNT
    return packet


def decode_marker_text_bytes(raw_bytes):
    return raw_bytes.rstrip(b"\x00").decode("shift_jis", errors="ignore").strip()


def get_ip_lock(ip_address):
    with _ip_lock_map_guard:
        lock = _ip_lock_map.get(ip_address)
        if lock is None:
            lock = threading.Lock()
            _ip_lock_map[ip_address] = lock
        return lock


def send_packet(sock, packet):
    sock.sendall(packet)
    try:
        response = sock.recv(1024)
    except socket.timeout:
        raise Exception("Recorder response timeout")

    if len(response) < 9:
        raise Exception("Modbus response too short")

    func = response[7]
    if func != packet[7] and not (func & 0x80):
        raise Exception("Unexpected function code")

    if func & 0x80:
        if len(response) <= 8:
            raise Exception("Modbus exception response too short")
        exc = response[8]
        raise Exception(f"Modbus error {exc}")

    return response


def read_marker_text(sock):
    response = send_packet(sock, build_read_text_packet())
    byte_count = int(response[8])
    if len(response) < 9 + byte_count:
        raise Exception("Marker read response length mismatch")

    raw = bytes(response[9:9 + byte_count])
    return decode_marker_text_bytes(raw)


def send_marker_text(ip_address, port, text, group_no, wait_time):
    expected_text = normalize_recorder_text(text)
    ip_lock = get_ip_lock(ip_address)

    logging.info(f"MARKER_LOCK_WAIT ip={ip_address} group={group_no}")
    with ip_lock:
        logging.info(f"MARKER_LOCK_ACQUIRED ip={ip_address} group={group_no}")
        client = connect_recorder(ip_address, port)

        try:
            logging.info(f"MARKER_SEND_STEP phase=text_write ip={ip_address} group={group_no} text={expected_text}")
            response = send_packet(client, build_sendbytes(text))
            logging.info(
                f"MARKER_SEND_RESPONSE phase=text_write ip={ip_address} group={group_no} "
                f"func=0x{response[7]:02X} bytes={len(response)}"
            )

            time.sleep(0.001 * wait_time)
            write_readback = read_marker_text(client)
            logging.info(f"MARKER_READBACK phase=after_text_write ip={ip_address} value={write_readback}")
            if write_readback != expected_text:
                raise Exception(
                    f"Marker readback mismatch after text write expected={expected_text} actual={write_readback}"
                )

            logging.info(f"MARKER_SEND_STEP phase=group_write ip={ip_address} group={group_no}")
            response = send_packet(client, build_sendbytes2(group_no))
            logging.info(
                f"MARKER_SEND_RESPONSE phase=group_write ip={ip_address} group={group_no} "
                f"func=0x{response[7]:02X} bytes={len(response)}"
            )

            time.sleep(0.001 * wait_time)
            logging.info(f"MARKER_SEND_STEP phase=confirm ip={ip_address} group={group_no}")
            response = send_packet(client, build_sendbytes3())
            logging.info(
                f"MARKER_SEND_RESPONSE phase=confirm ip={ip_address} group={group_no} "
                f"func=0x{response[7]:02X} bytes={len(response)}"
            )

            time.sleep(0.001 * wait_time)
            final_readback = read_marker_text(client)
            logging.info(f"MARKER_READBACK phase=after_confirm ip={ip_address} value={final_readback}")
            if final_readback != expected_text:
                raise Exception(
                    f"Marker readback mismatch after confirm expected={expected_text} actual={final_readback}"
                )
        finally:
            try:
                client.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            client.close()
            logging.info(f"MARKER_LOCK_RELEASED ip={ip_address} group={group_no}")


def send_with_retry(ip, port, text, group_no, wait_time, retry=3):
    for i in range(retry):
        try:
            send_marker_text(ip, port, text, group_no, wait_time)
            logging.info(f"MARKER_SEND_VERIFIED ip={ip} group={group_no} text={text}")
            logging.info(f"{ip} SEND OK : {text}")
            return True
        except socket.timeout:
            logging.warning(f"{ip} TIMEOUT")
        except Exception as e:
            logging.error(f"{ip} ERROR : {e}")

        if i < retry - 1:
            wait = 2 ** i
            logging.warning(f"retry {i+1}/{retry} wait {wait}s")
            time.sleep(wait)
        else:
            logging.error(f"{ip} SEND FAILED after {retry} retries")
            return False
