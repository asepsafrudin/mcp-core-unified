#!/home/aseps/MCP/mcp-unified/venv/bin/python3
import sys
import subprocess
import threading

SERVER_SCRIPT = "/home/aseps/MCP/mcp-unified/mcp_server.py"

proc = subprocess.Popen(
    [sys.executable, "-u", SERVER_SCRIPT] + sys.argv[1:],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    bufsize=0  # Unbuffered
)

def pipe_stream(stream, out_stream, filter_rpc=False):
    while True:
        line = stream.readline()
        if not line:
            break
        decoded_line = line.decode('utf-8', errors='replace')
        
        if filter_rpc:
            if '"jsonrpc":"2.0"' in decoded_line or '"jsonrpc": "2.0"' in decoded_line:
                out_stream.write(line)
                out_stream.flush()
            else:
                sys.stderr.buffer.write(line)
                sys.stderr.buffer.flush()
        else:
            out_stream.write(line)
            out_stream.flush()

# Thread for stdout (filtered)
t1 = threading.Thread(target=pipe_stream, args=(proc.stdout, sys.stdout.buffer, True))
# Thread for stderr (direct)
t2 = threading.Thread(target=pipe_stream, args=(proc.stderr, sys.stderr.buffer, False))

t1.start()
t2.start()

proc.wait()
t1.join()
t2.join()
sys.exit(proc.returncode)
