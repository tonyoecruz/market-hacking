
with open(r"c:\temp\Magic\Github\Hack Market\market-hacking\app.py", 'rb') as f:
    lines = f.readlines()
    for i, line in enumerate(lines):
        if 2380 <= i+1 <= 2390:
            print(f"Line {i+1}: {line.hex()}")
