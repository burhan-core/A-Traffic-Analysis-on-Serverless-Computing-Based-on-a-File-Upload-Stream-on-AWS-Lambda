import json
import boto3
import base64
import subprocess
import time
import os
import socket

s3 = boto3.client('s3')
BUCKET_NAME = os.environ.get('BUCKET_NAME', '')

def lambda_handler(event, context):
    start_time = time.time()

    metadata = collect_metadata()

    body = event.get('body', 'hello')
    if event.get('isBase64Encoded', False):
        file_content = base64.b64decode(body)
    else:
        file_content = body.encode('utf-8') if isinstance(body, str) else body

    file_key = f"uploads/{context.aws_request_id}.txt"

    try:
        s3.put_object(Bucket=BUCKET_NAME, Key=file_key, Body=file_content)
        upload_status = "success"
    except Exception as e:
        upload_status = f"error: {str(e)}"

    end_time = time.time()
    processing_time_ms = round((end_time - start_time) * 1000, 2)

    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({
            'requestId':       context.aws_request_id,
            'functionName':    context.function_name,
            'memoryLimitMB':   context.memory_limit_in_mb,
            'remainingTimeMs': context.get_remaining_time_in_millis(),
            'processingTimeMs': processing_time_ms,
            'uploadStatus':    upload_status,
            'fileKey':         file_key,
            'metadata':        metadata
        })
    }


def collect_metadata():
    info = {}

    # CPU model + count
    try:
        cpu = subprocess.check_output(['cat', '/proc/cpuinfo'], timeout=2).decode()
        for line in cpu.split('\n'):
            if 'model name' in line:
                info['cpu_model'] = line.split(':', 1)[1].strip()
                break
        info['cpu_count'] = cpu.count('processor\t:')
    except Exception as e:
        info['cpu_error'] = str(e)

    # Memory stats
    try:
        mem = subprocess.check_output(['cat', '/proc/meminfo'], timeout=2).decode()
        for line in mem.split('\n'):
            for key in ['MemTotal', 'MemFree', 'MemAvailable', 'Cached']:
                if line.startswith(key + ':'):
                    info[key] = line.split(':', 1)[1].strip()
    except Exception as e:
        info['mem_error'] = str(e)

    # VM uptime in seconds
    try:
        uptime_raw = subprocess.check_output(['cat', '/proc/uptime'], timeout=2).decode()
        info['vm_uptime_seconds'] = float(uptime_raw.split()[0])
    except Exception as e:
        info['uptime_error'] = str(e)

    # Container hostname and private IP
    try:
        info['hostname']   = socket.gethostname()
        info['private_ip'] = socket.gethostbyname(socket.gethostname())
    except Exception as e:
        info['ip_error'] = str(e)

    return info
